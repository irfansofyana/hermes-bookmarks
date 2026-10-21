"""Durable SQLite queue, fenced by active generation, token, and live lease."""
import json
import math
import time
from uuid import uuid4
from .storage import Storage
from .errors import NotFoundError, ValidationError
from .labels import validate_text
from .tags import normalize_tags, merge_generated


def validate_settings(settings):
    allowed = {'provider','model','owner_profile'}
    if not isinstance(settings, dict) or set(settings)-allowed:
        raise ValueError('Invalid enrichment settings; credentials are never accepted.')
    for value in settings.values():
        if not isinstance(value,str) or not value.strip() or len(value)>300:
            raise ValueError('Invalid route')
        try: validate_text(value)
        except ValidationError: raise ValueError('Invalid route') from None
    return json.dumps(settings, sort_keys=True)


def validate_result(result):
    if not isinstance(result,dict): raise ValueError('Invalid result')
    summary=result.get('summary'); tags=result.get('tags')
    if not isinstance(summary,str) or not summary.strip() or len(summary)>16000: raise ValueError('Invalid summary')
    if not isinstance(tags,list): raise ValueError('Invalid tags')
    try:
        validate_text(summary)
        labels=normalize_tags(tags)
        for key in ('provider','model','coverage'):
            validate_text(result.get(key),max_chars=300)
    except ValidationError:
        raise ValueError('Invalid result') from None
    return {'summary':summary,'tags':[display for display,_ in labels]}


def active(connection, job):
    return connection.execute('''SELECT 1 FROM items WHERE id=?
        AND enrichment_job_id=? AND enrichment_generation=?''',
        (job['item_id'],job['id'],job['generation'])).fetchone() is not None


def update_status(connection, job, state):
    connection.execute('''UPDATE items SET enrichment_status=? WHERE id=?
        AND enrichment_job_id=? AND enrichment_generation=?''',
        (state,job['item_id'],job['id'],job['generation']))


class JobQueue:
    def __init__(self, data_root): self.storage=Storage(data_root)

    def configure_route(self,settings):
        encoded=validate_settings(settings)
        if not all(settings.get(k) for k in ('provider','model','owner_profile')): raise ValueError('Complete route required')
        with self.storage._transaction(write=True) as c:
            existing=c.execute("SELECT value FROM library_config WHERE key='enrichment_route'").fetchone()
            if existing and existing['value']!=encoded: raise ValueError('Library route already configured; explicit settings change required')
            c.execute("INSERT INTO library_config(key,value) VALUES('enrichment_route',?) ON CONFLICT DO NOTHING",(encoded,))

    def route(self):
        with self.storage._transaction() as c:
            row=c.execute("SELECT value FROM library_config WHERE key='enrichment_route'").fetchone()
            return json.loads(row['value']) if row else {}

    def enqueue(self,item_id,revision,settings):
        encoded=validate_settings(settings)
        if type(revision) is not int or not 1<=revision<=2**63-1: raise ValueError('Invalid revision')
        with self.storage._transaction(write=True) as c:
            item=c.execute('SELECT * FROM items WHERE id=?',(item_id,)).fetchone()
            if item is None: raise NotFoundError()
            if item['kind']!='link': raise ValueError('Image enrichment is not configured')
            if item['revision']!=revision: raise ValueError('Revision changed')
            job=c.execute('SELECT * FROM jobs WHERE item_id=? AND revision=?',(item_id,revision)).fetchone()
            if job is not None:
                if job['settings']!=encoded: raise ValueError('Existing job uses different settings')
                # Reuse is never permission to resurrect cancelled or superseded work.
                return job['id']
            generation=item['enrichment_generation']+1; job_id=str(uuid4())
            c.execute('INSERT INTO jobs(id,item_id,revision,generation,settings) VALUES(?,?,?,?,?)',
                      (job_id,item_id,revision,generation,encoded))
            c.execute("UPDATE items SET enrichment_status='pending',enrichment_job_id=?,enrichment_generation=? WHERE id=?",(job_id,generation,item_id))
            return job_id

    def claim(self,worker_id,now=None,lease_seconds=120):
        if not isinstance(worker_id,str) or not worker_id or not 1<=lease_seconds<=600: raise ValueError('Invalid claim')
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            if not math.isfinite(now): raise ValueError('Invalid claim')
            row=c.execute("SELECT * FROM jobs WHERE state='pending' AND attempts<3 ORDER BY rowid LIMIT 1").fetchone()
            if row is None: return None
            token=str(uuid4())
            c.execute("UPDATE jobs SET state='running',worker=?,token=?,expires=?,attempts=attempts+1 WHERE id=?",(worker_id,token,now+lease_seconds,row['id']))
            update_status(c,row,'running')
            job=dict(c.execute('SELECT * FROM jobs WHERE id=?',(row['id'],)).fetchone())
            job['settings']=json.loads(job['settings'])
            return job

    def recover_expired(self,now=None):
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            rows=c.execute("SELECT * FROM jobs WHERE state='running' AND expires<=?",(now,)).fetchall()
            for row in rows:
                state='failed' if row['attempts']>=3 else 'pending'
                c.execute('UPDATE jobs SET state=?,worker=NULL,token=NULL,expires=NULL,error=? WHERE id=?',(state,'lease_expired',row['id']))
                update_status(c,row,state)
            return len(rows)

    def complete(self,job_id,worker_id,result,*,token,now=None):
        values=validate_result(result)
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            job=c.execute("SELECT * FROM jobs WHERE id=? AND state='running' AND worker=? AND token=? AND expires>?",(job_id,worker_id,token,now)).fetchone()
            if job is None: return False
            applied=active(c,job)
            if applied:
                merge_generated(c,job['item_id'],values['tags'])
                c.execute("""UPDATE items SET summary=?,enrichment_status='succeeded',revision=revision+1,updated_at=?
                    WHERE id=? AND enrichment_job_id=? AND enrichment_generation=?""",
                    (values['summary'],now,job['item_id'],job_id,job['generation']))
            provenance={key:result[key] for key in ('provider','model','coverage')}
            c.execute('UPDATE jobs SET state=?,error=?,result=?,worker=NULL,token=NULL,expires=NULL WHERE id=?',
                ('succeeded' if applied else 'failed',None if applied else 'generation_conflict',json.dumps(provenance) if applied else None,job_id))
            return applied

    def fail(self,job_id,worker_id,code,*,token,now=None):
        # Error codes only: publisher/provider exception strings may contain secrets.
        if code not in {'provider_failed','extraction_failed','invalid_result','configuration_required'}: code='provider_failed'
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            job=c.execute("SELECT * FROM jobs WHERE id=? AND state='running' AND worker=? AND token=? AND expires>?",(job_id,worker_id,token,now)).fetchone()
            if job is None: return False
            applied=active(c,job)
            state='failed' if not applied or job['attempts']>=3 or code=='configuration_required' else 'pending'
            c.execute('UPDATE jobs SET state=?,error=?,worker=NULL,token=NULL,expires=NULL WHERE id=?',
                      (state,code if applied else 'generation_conflict',job_id))
            update_status(c,job,state)
            return applied

    def cancel(self,job_id):
        with self.storage._transaction(write=True) as c:
            job=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if job is None: raise NotFoundError()
            if job['state'] in ('pending','running'):
                c.execute("UPDATE jobs SET state='cancelled',token=NULL,worker=NULL,expires=NULL WHERE id=?",(job_id,))
                update_status(c,job,'cancelled')

    def get(self,job_id):
        with self.storage._transaction() as c:
            row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row is None: raise NotFoundError()
            data=dict(row); data['settings']=json.loads(data['settings']); return data

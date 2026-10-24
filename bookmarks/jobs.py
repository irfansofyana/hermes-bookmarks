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


def validate_result(result, fields=None):
    fields=['summary','tags'] if fields is None else fields
    if type(result) is not dict or set(result)-{'summary','tags','provider','model','coverage'}: raise ValueError('Invalid result')
    if set(fields)-set(result): raise ValueError('Missing generated field')
    values={}
    try:
        if 'summary' in fields:
            summary=result['summary'];validate_text(summary,max_chars=16000,nonempty=True)
            if not summary.strip(): raise ValidationError()
            values['summary']=summary
        if 'tags' in fields: values['tags']=[display for display,_ in normalize_tags(result['tags'])]
        for key in ('provider','model','coverage'): validate_text(result.get(key),max_chars=300,nonempty=True)
    except (ValidationError,TypeError): raise ValueError('Invalid result') from None
    return values


def active(connection, job):
    return connection.execute('''SELECT 1 FROM items WHERE id=?
        AND deleted_at IS NULL AND enrichment_job_id=? AND enrichment_generation=?''',
        (job['item_id'],job['id'],job['generation'])).fetchone() is not None


def update_status(connection, job, state):
    connection.execute('''UPDATE items SET enrichment_status=? WHERE id=?
        AND deleted_at IS NULL AND enrichment_job_id=? AND enrichment_generation=?''',
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
            from .settings import seed_route
            seed_route(c,settings)

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
            if item['deleted_at'] is not None: raise ValueError('Item is trashed')
            if item['kind']!='link': raise ValueError('Image enrichment is not configured')
            if item['revision']!=revision: raise ValueError('Revision changed')
            job=c.execute('SELECT * FROM jobs WHERE item_id=? AND revision=? ORDER BY generation DESC LIMIT 1',(item_id,revision)).fetchone()
            if job is not None:
                if job['settings']==encoded:
                    # Legacy reuse never resurrects cancelled or superseded work.
                    return job['id']
                if 'version' not in json.loads(job['settings']):
                    raise ValueError('Existing job uses different settings')
                # Internal legacy wrapper can supersede a new-format fixture job;
                # production requests use receipt/active-job conflict checks instead.
            generation=item['enrichment_generation']+1; job_id=str(uuid4())
            c.execute('INSERT INTO jobs(id,item_id,revision,generation,settings,summary_revision) VALUES(?,?,?,?,?,?)',
                      (job_id,item_id,revision,generation,encoded,item['summary_revision']))
            c.execute("UPDATE items SET enrichment_status='pending',enrichment_job_id=?,enrichment_generation=? WHERE id=?",(job_id,generation,item_id))
            return job_id

    def claim(self,worker_id,now=None,lease_seconds=120):
        if not isinstance(worker_id,str) or not worker_id or not 1<=lease_seconds<=600: raise ValueError('Invalid claim')
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            if not math.isfinite(now): raise ValueError('Invalid claim')
            from .settings import read_settings
            if read_settings(c)['settings']['paused']: return None
            row=c.execute("""SELECT j.* FROM jobs j JOIN items i ON i.id=j.item_id
                WHERE j.state='pending' AND j.attempts<3 AND i.deleted_at IS NULL
                AND i.enrichment_job_id=j.id AND i.enrichment_generation=j.generation
                ORDER BY j.rowid LIMIT 1""").fetchone()
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

    def complete(self,job_id,worker_id,result,*,token,now=None,extracted_text=None):
        from .enrichment_options import normalize_snapshot
        from .settings import encoded
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            job=c.execute("SELECT * FROM jobs WHERE id=? AND state='running' AND worker=? AND token=? AND expires>?",(job_id,worker_id,token,now)).fetchone()
            if job is None: return False
            snap=normalize_snapshot(json.loads(job['settings']))
            if snap['version']==1 and job['summary_revision'] is not None:snap['summary_revision']=job['summary_revision']
            values=validate_result(result,snap['fields'])
            item=c.execute('SELECT * FROM items WHERE id=?',(job['item_id'],)).fetchone()
            owned=active(c,job) and item is not None and item['primary_asset_id']==snap['primary_asset_id']
            applied=[];conflicted=[];error=None
            if owned:
                if 'tags' in values:
                    merge_generated(c,job['item_id'],values['tags']);applied.append('tags')
                if 'summary' in values:
                    if item['summary_revision']!=snap['summary_revision']:
                        conflicted.append('summary');error='manual_summary_conflict'
                    else:
                        c.execute("UPDATE items SET summary=?,summary_source='generated',summary_revision=summary_revision+1 WHERE id=?",(values['summary'],job['item_id']))
                        applied.insert(0,'summary')
                if extracted_text is not None and snap['options']['retain_extracted_text']:
                    validate_text(extracted_text,max_chars=30000)
                    if result['coverage']!='extracted_text': raise ValueError('Invalid retained coverage')
                    c.execute('UPDATE items SET extracted_text=? WHERE id=?',(extracted_text,job['item_id']))
            else:
                conflicted=list(snap['fields']);error='generation_conflict'
            info={**{key:result[key] for key in ('provider','model','coverage')},'applied_fields':applied,'conflicted_fields':conflicted}
            state='failed' if error else 'succeeded'
            if owned:
                c.execute('UPDATE items SET generated_provenance=?,revision=revision+1,updated_at=? WHERE id=?',(encoded(info),now,job['item_id']))
                update_status(c,job,state)
            c.execute('UPDATE jobs SET state=?,error=?,result=?,worker=NULL,token=NULL,expires=NULL WHERE id=?',(state,error,encoded(info),job_id))
            return owned and not conflicted

    def fail(self,job_id,worker_id,code,*,token,now=None):
        # Error codes only: publisher/provider exception strings may contain secrets.
        terminal={'invalid_result','configuration_required','trust_denied','asset_unavailable','generation_conflict'}
        if code not in terminal|{'provider_failed','extraction_failed'}: code='provider_failed'
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            job=c.execute("SELECT * FROM jobs WHERE id=? AND state='running' AND worker=? AND token=? AND expires>?",(job_id,worker_id,token,now)).fetchone()
            if job is None: return False
            applied=active(c,job)
            state='failed' if not applied or job['attempts']>=3 or code in terminal else 'pending'
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

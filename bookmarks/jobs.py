"""Durable SQLite queue. Completion is fenced by a fresh token AND lease."""
import json
import math
import time
from uuid import uuid4
from .storage import Storage
from .errors import NotFoundError


def validate_settings(settings):
    allowed = {'provider','model','owner_profile'}
    if not isinstance(settings, dict) or set(settings)-allowed:
        raise ValueError('Invalid enrichment settings; credentials are never accepted.')
    for key,value in settings.items():
        if key.startswith('auto_'):
            if type(value) is not bool: raise ValueError('Invalid toggle')
        elif not isinstance(value,str) or not value.strip() or len(value)>300:
            raise ValueError('Invalid route')
    return json.dumps(settings, sort_keys=True)


def validate_result(result):
    if not isinstance(result,dict): raise ValueError('Invalid result')
    summary=result.get('summary'); tags=result.get('tags')
    if not isinstance(summary,str) or not summary.strip() or len(summary)>16000: raise ValueError('Invalid summary')
    if not isinstance(tags,list) or len(tags)>20 or any(not isinstance(t,str) or not t.strip() or len(t)>80 for t in tags): raise ValueError('Invalid tags')
    for key in ('provider','model','coverage'):
        if not isinstance(result.get(key),str) or len(result[key])>300: raise ValueError('Missing provenance')
    return {'summary':summary,'tags':list(dict.fromkeys(tags))}


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
        if type(revision) is not int or revision<1: raise ValueError('Invalid revision')
        with self.storage._transaction(write=True) as c:
            item=c.execute('SELECT revision FROM items WHERE id=?',(item_id,)).fetchone()
            if item is None: raise NotFoundError()
            if item['revision']!=revision: raise ValueError('Revision changed')
            c.execute('INSERT INTO jobs(id,item_id,revision,settings) VALUES(?,?,?,?) ON CONFLICT(item_id,revision) DO NOTHING',
                      (str(uuid4()),item_id,revision,encoded))
            job=c.execute('SELECT * FROM jobs WHERE item_id=? AND revision=?',(item_id,revision)).fetchone()
            if job['settings']!=encoded: raise ValueError('Existing job uses different settings')
            if job['state']=='pending': c.execute("UPDATE items SET enrichment_status='pending',enrichment_job_id=? WHERE id=?",(job['id'],item_id))
            return job['id']

    def claim(self,worker_id,now=None,lease_seconds=120):
        now=time.time() if now is None else now
        if not isinstance(worker_id,str) or not worker_id or not math.isfinite(now) or not 1<=lease_seconds<=600: raise ValueError('Invalid claim')
        with self.storage._transaction(write=True) as c:
            row=c.execute("SELECT * FROM jobs WHERE state='pending' AND attempts<3 ORDER BY rowid LIMIT 1").fetchone()
            if row is None: return None
            token=str(uuid4())
            c.execute("UPDATE jobs SET state='running',worker=?,token=?,expires=?,attempts=attempts+1 WHERE id=?",(worker_id,token,now+lease_seconds,row['id']))
            c.execute("UPDATE items SET enrichment_status='running' WHERE id=? AND revision=?",(row['item_id'],row['revision']))
            job=dict(c.execute('SELECT * FROM jobs WHERE id=?',(row['id'],)).fetchone())
            job['settings']=json.loads(job['settings'])
            return job

    def recover_expired(self,now=None):
        now=time.time() if now is None else now
        with self.storage._transaction(write=True) as c:
            rows=c.execute("SELECT * FROM jobs WHERE state='running' AND expires<=?",(now,)).fetchall()
            for row in rows:
                state='failed' if row['attempts']>=3 else 'pending'
                c.execute('UPDATE jobs SET state=?,worker=NULL,token=NULL,expires=NULL,error=? WHERE id=?',(state,'lease_expired',row['id']))
                c.execute('UPDATE items SET enrichment_status=? WHERE id=? AND revision=?',(state,row['item_id'],row['revision']))
            return len(rows)

    def complete(self,job_id,worker_id,result,*,token,now=None):
        values=validate_result(result)
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            job=c.execute("SELECT * FROM jobs WHERE id=? AND state='running' AND worker=? AND token=? AND expires>?",(job_id,worker_id,token,now)).fetchone()
            if job is None: return False
            applied=c.execute("UPDATE items SET summary=?, tags=?, enrichment_status='succeeded', revision=revision+1 WHERE id=? AND revision=?",
                              (values['summary'],json.dumps(values['tags']),job['item_id'],job['revision'])).rowcount
            metadata = {k: result[k] for k in ('provider','model','coverage')}
            c.execute('UPDATE jobs SET state=?, error=?,result=?,worker=NULL,token=NULL,expires=NULL WHERE id=?',('succeeded' if applied else 'failed',None if applied else 'revision_conflict',json.dumps(metadata) if applied else None,job_id))
            return bool(applied)

    def fail(self,job_id,worker_id,code,*,token,now=None):
        # Error codes only: publisher/provider exception strings can contain secrets.
        if code not in {'provider_failed','extraction_failed','invalid_result','configuration_required'}: code='provider_failed'
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            job=c.execute("SELECT * FROM jobs WHERE id=? AND state='running' AND worker=? AND token=? AND expires>?",(job_id,worker_id,token,now)).fetchone()
            if job is None: return False
            state='failed' if job['attempts']>=3 or code=='configuration_required' else 'pending'
            c.execute('UPDATE jobs SET state=?,error=?,worker=NULL,token=NULL,expires=NULL WHERE id=?',(state,code,job_id))
            c.execute('UPDATE items SET enrichment_status=? WHERE id=? AND revision=?',(state,job['item_id'],job['revision']))
            return True

    def cancel(self,job_id):
        with self.storage._transaction(write=True) as c:
            job=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if job is None: raise NotFoundError()
            if job['state'] in ('pending','running'):
                c.execute("UPDATE jobs SET state='cancelled',token=NULL,worker=NULL,expires=NULL WHERE id=?",(job_id,))
                c.execute("UPDATE items SET enrichment_status='cancelled' WHERE id=? AND revision=?",(job['item_id'],job['revision']))

    def get(self,job_id):
        with self.storage._transaction() as c:
            row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row is None: raise NotFoundError()
            data=dict(row); data['settings']=json.loads(data['settings']); return data

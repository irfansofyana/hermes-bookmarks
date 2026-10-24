"""Lease-fenced, per-row atomic import. Each method owns one SQLite transaction."""
import asyncio
import json
import math
import time
from uuid import uuid4
from ..errors import ValidationError
from ..labels import validate_text
from ..enrichment import _retry_storage_call
from .apply import apply_record

class ImportQueue:
    def __init__(self,storage):self.storage=storage
    def recover_expired(self,now=None):
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            c.execute("UPDATE import_jobs SET state='pending',worker=NULL,token=NULL,expires=NULL WHERE state='running' AND expires<=?",(now,))
    def claim(self,worker,now=None,lease_seconds=120):
        validate_text(worker,max_chars=100,nonempty=True)
        if type(lease_seconds) is not int or not 1<=lease_seconds<=120:raise ValidationError()
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            if not math.isfinite(now):raise ValidationError()
            row=c.execute("SELECT id FROM import_jobs WHERE state='pending' AND cancel_requested=0 ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:return None
            c.execute("UPDATE import_jobs SET state='running',worker=?,token=?,expires=? WHERE id=?",(worker,uuid4().hex,now+lease_seconds,row['id']))
            return dict(c.execute('SELECT * FROM import_jobs WHERE id=?',(row['id'],)).fetchone())
    def step(self,claim,now=None):
        if claim is None:return False
        with self.storage._transaction(write=True) as c:
            now=time.time() if now is None else now
            row=c.execute("SELECT * FROM import_jobs WHERE id=? AND state='running' AND cancel_requested=0 AND worker=? AND token=? AND expires>?",(claim['id'],claim['worker'],claim['token'],now)).fetchone()
            if row is None:return False
            preview=c.execute('SELECT payload FROM import_previews WHERE id=?',(row['preview_id'],)).fetchone()
            index=row['cursor'];staged=json.loads(preview['payload'])[index]
            settings=json.loads(row['settings']) if row['settings'] is not None else None
            outcome,item_id,error,warnings=apply_record(self.storage,c,staged,row,index,settings)
            c.execute('INSERT INTO import_results VALUES(?,?,?,?,?,?)',(row['id'],index,outcome,item_id,error,json.dumps(warnings)))
            # outcome is a closed internal enum; never supplied SQL identifiers.
            column={'imported':'imported','skipped':'skipped','failed':'failed'}[outcome]
            c.execute('UPDATE import_jobs SET cursor=cursor+1,'+column+'='+column+"+1,state=CASE WHEN cursor+1=total THEN 'succeeded' ELSE 'running' END,expires=? WHERE id=?",(now+120,row['id']))
            if index+1==row['total']:c.execute('UPDATE import_jobs SET worker=NULL,token=NULL,expires=NULL WHERE id=?',(row['id'],))
            return True

async def run_imports(queue,*,poll_seconds=1):
    worker=uuid4().hex
    while True:
        await _retry_storage_call(queue.recover_expired)
        claim=await _retry_storage_call(queue.claim,worker)
        if claim:
            while await _retry_storage_call(queue.step,claim):
                await asyncio.sleep(0)  # Allow cancellation between committed rows.
        else:await asyncio.sleep(poll_seconds)

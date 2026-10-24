"""Immutable staging and idempotent job admission. Never fetches or runs a model."""
import hashlib
import json
import re
import time
from uuid import uuid4
from ..errors import BookmarkError,ValidationError,ConflictError,NotFoundError,ConfigurationError
from ..items import validate_operation_key
from ..labels import validate_text
from ..queries import pagination
from .records import encoded,bounded_records,record,options as validate_options


def job(c,job_id,limit=50,offset=0):
    pagination(limit,offset);validate_text(job_id,max_chars=100,nonempty=True)
    row=c.execute('SELECT * FROM import_jobs WHERE id=?',(job_id,)).fetchone()
    if row is None:raise NotFoundError()
    rows=c.execute('SELECT * FROM import_results WHERE job_id=? ORDER BY row_index LIMIT ? OFFSET ?',
                   (job_id,limit,min(offset,2**63-1))).fetchall()
    return {**{key:row[key] for key in ('id','state','total','imported','skipped','failed','error','created_at')},
        'kind':'import','processed':row['cursor'],'remaining':row['total']-row['cursor'],
        'limit':limit,'offset':offset,'rows':[{'index':r['row_index'],'outcome':r['outcome'],'item_id':r['item_id'],
                    'error_code':r['error'],'warnings':json.loads(r['warnings'])} for r in rows]}


class ImportStore:
    def __init__(self,storage):self.storage=storage
    def preview(self,records=None,html=None,options=None):
        if (records is None)==(html is None):raise ValidationError()
        if html is not None:
            from .html import parse_bookmarks
            records=parse_bookmarks(html)
        bounded_records(records);opts=validate_options(options)
        staged=[];rows=[];seen=set();counts={'total':len(records),'valid':0,'invalid':0,'duplicate_in_batch':0,'existing':0}
        with self.storage._transaction(write=True) as c:
            for index,value in enumerate(records):
                try:
                    source_warnings=value.pop('_html_warnings',[]) if html is not None and isinstance(value,dict) else []
                    clean,warnings=record(c,value)
                    warnings+=source_warnings
                    if clean['url'] in seen:status='duplicate_in_batch'
                    elif c.execute('SELECT 1 FROM items WHERE url=?',(clean['url'],)).fetchone():status='existing'
                    else:status='valid'
                    seen.add(clean['url']);counts[status]+=1
                    staged.append({'record':clean,'warnings':warnings,'error_code':None})
                    rows.append({'index':index,'status':status,'warnings':warnings,'error_code':None})
                except BookmarkError as error:
                    counts['invalid']+=1;staged.append({'record':None,'warnings':[],'error_code':error.code})
                    rows.append({'index':index,'status':'invalid','warnings':[],'error_code':error.code})
            payload=encoded(staged);digest=hashlib.sha256(encoded({'rows':staged,'options':opts}).encode()).hexdigest()
            key=uuid4().hex;now=time.time()
            report={**counts,'rows':rows,'options':opts,'preview_id':key,'input_digest':digest,'expires_at':now+86400}
            c.execute('INSERT INTO import_previews VALUES(?,?,?,?,?,?,?)',(key,digest,payload,encoded(opts),encoded(report),now,now+86400))
            return report
    def start(self,preview_id,input_digest,request_id):
        validate_text(preview_id,max_chars=100,nonempty=True);validate_operation_key(request_id)
        if not isinstance(input_digest,str) or not re.fullmatch('[a-f0-9]{64}',input_digest):raise ValidationError()
        with self.storage._transaction(write=True) as c:
            prior=c.execute('SELECT * FROM import_jobs WHERE request_id=?',(request_id,)).fetchone()
            if prior is not None:
                if prior['preview_id']!=preview_id or prior['digest']!=input_digest:raise ConflictError()
                return job(c,prior['id'])
            preview=c.execute('SELECT * FROM import_previews WHERE id=?',(preview_id,)).fetchone()
            if preview is None:raise NotFoundError()
            if preview['digest']!=input_digest or preview['expires_at']<=time.time():raise ConflictError()
            opts=json.loads(preview['options']);settings=None
            if opts['enrich']:
                from ..settings import read_settings,snapshot_settings
                value=read_settings(c)
                if not value['route_ready']:raise ConfigurationError()
                snapshot={**snapshot_settings(c),'fields':['summary','tags'],'primary_asset_id':None,'summary_revision':0}
                settings=encoded(snapshot)
            key=uuid4().hex;total=json.loads(preview['report'])['total']
            c.execute('''INSERT INTO import_jobs(id,preview_id,request_id,digest,total,settings,created_at)
                VALUES(?,?,?,?,?,?,?)''',(key,preview_id,request_id,input_digest,total,settings,time.time()))
            return job(c,key)
    def get(self,job_id,limit=50,offset=0):
        with self.storage._transaction() as c:return job(c,job_id,limit,offset)
    def request_get(self,request_id):
        validate_operation_key(request_id)
        with self.storage._transaction() as c:
            row=c.execute('SELECT id FROM import_jobs WHERE request_id=?',(request_id,)).fetchone()
            if row is None:raise NotFoundError()
            return job(c,row['id'])
    def cancel(self,job_id):
        with self.storage._transaction(write=True) as c:
            current=job(c,job_id)
            if current['state'] in ('pending','running'):
                c.execute("UPDATE import_jobs SET state='cancelled',cancel_requested=1,worker=NULL,token=NULL,expires=NULL WHERE id=?",(job_id,))
            return job(c,job_id)

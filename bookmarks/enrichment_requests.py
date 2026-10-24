"""Atomic enrichment admission and public-safe receipts over caller transactions."""
import hashlib
import json
from uuid import uuid4
from .errors import ConflictError, NotFoundError, ValidationError
from .items import load, validate_operation_key
from .collections import revision
from .settings import read_settings, snapshot_settings, encoded
from .enrichment_options import fields_list, normalize_snapshot


def public_job(c,job_id):
    row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if row is None: raise NotFoundError()
    snapshot=normalize_snapshot(json.loads(row['settings']))
    info=json.loads(row['result']) if row['result'] else {}
    return {**{key:row[key] for key in ('id','item_id','revision','generation','state','attempts')},
        'error_code':row['error'],'fields':snapshot['fields'],'settings_revision':snapshot['settings_revision'],
        'provider':info.get('provider'),'model':info.get('model'),'coverage':info.get('coverage'),
        'applied_fields':info.get('applied_fields',[]),'conflicted_fields':info.get('conflicted_fields',[])}


def insert_job(c,item,snapshot,request_id=None):
    snapshot=normalize_snapshot(snapshot)
    job_id=str(uuid4())
    maximum=c.execute('SELECT max(generation) FROM jobs WHERE item_id=?',(item['id'],)).fetchone()[0] or 0
    generation=max(item['enrichment_generation'],maximum)+1
    if generation>2**63-1: raise ConflictError()
    ready=all(snapshot['route'].get(k) for k in ('provider','model','owner_profile'))
    state='pending' if ready else 'failed';error=None if ready else 'configuration_required'
    c.execute('''INSERT INTO jobs(id,item_id,revision,generation,settings,state,error,request_id,
        fields,settings_revision,primary_asset_id,summary_revision) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
        (job_id,item['id'],item['revision'],generation,encoded(snapshot),state,error,request_id,
         encoded(snapshot['fields']),snapshot['settings_revision'],snapshot['primary_asset_id'],snapshot['summary_revision']))
    c.execute('UPDATE items SET enrichment_job_id=?,enrichment_generation=?,enrichment_status=? WHERE id=?',
        (job_id,generation,state,item['id']))
    return job_id,generation


def has_active_job(c,item):
    # Admission and claims agree on pointer/generation ownership. Inactive
    # migrated history stays intact but can neither execute nor block a retry.
    return c.execute("SELECT 1 FROM jobs WHERE item_id=? AND id=? AND generation=? AND state IN ('pending','running')",
        (item['id'],item['enrichment_job_id'],item['enrichment_generation'])).fetchone() is not None


def admit_automatic(c,item_id,settings_snapshot=None):
    item=load(c,item_id)
    if item['deleted_at'] is not None: return None
    snap=snapshot_settings(c) if settings_snapshot is None else normalize_snapshot(settings_snapshot)
    options=snap['options']
    if item['kind']=='image' and not options['image_analysis']:return None
    fields=[]
    if options['automatic_summary'] and item['summary_source'] not in {'manual','legacy'}:fields.append('summary')
    if options['automatic_tags']:fields.append('tags')
    if not fields:return None
    if has_active_job(c,item):return None
    # Import snapshots are captured at start, while per-item ownership is captured now.
    snap={**snap,'version':2,'fields':fields,'primary_asset_id':item['primary_asset_id'],
          'summary_revision':item['summary_revision']}
    if snap['settings_revision'] is None: snap['settings_revision']=read_settings(c)['revision']
    return insert_job(c,item,snap)[0]


class EnrichmentRequests:
    def __init__(self,storage):self.storage=storage

    def enrich(self,item_id,expected_revision,request_id,fields):
        revision(expected_revision);validate_operation_key(request_id);fields=fields_list(fields)
        from .labels import validate_text
        validate_text(item_id,max_chars=100,nonempty=True)
        digest=hashlib.sha256(encoded({'item_id':item_id,'expected_revision':expected_revision,'fields':fields}).encode()).hexdigest()
        with self.storage._transaction(write=True) as c:
            prior=c.execute('SELECT * FROM enrichment_requests WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                if prior['payload_hash']!=digest:raise ConflictError()
                receipt=json.loads(prior['receipt'])
                return {'receipt':receipt,'job':public_job(c,receipt['job_id'])}
            item=load(c,item_id,expected_revision)
            if item['deleted_at'] is not None:raise ConflictError(item['revision'])
            if has_active_job(c,item):raise ConflictError(item['revision'])
            snap=snapshot_settings(c)
            if item['kind']=='image' and not snap['options']['image_analysis']:raise ValidationError()
            snap={**snap,'fields':fields,'primary_asset_id':item['primary_asset_id'],'summary_revision':item['summary_revision']}
            job_id,generation=insert_job(c,item,snap,request_id)
            receipt={'request_id':request_id,'item_id':item_id,'accepted_revision':expected_revision,
                'job_id':job_id,'generation':generation,'fields':fields,'settings_revision':snap['settings_revision']}
            c.execute('INSERT INTO enrichment_requests VALUES(?,?,?)',(request_id,digest,encoded(receipt)))
            return {'receipt':receipt,'job':public_job(c,job_id)}

    def request_get(self,request_id):
        validate_operation_key(request_id)
        with self.storage._transaction() as c:
            row=c.execute('SELECT receipt FROM enrichment_requests WHERE request_id=?',(request_id,)).fetchone()
            if row is None:raise NotFoundError()
            receipt=json.loads(row['receipt'])
            return {'receipt':receipt,'job':public_job(c,receipt['job_id'])}

    def get(self,job_id):
        from .labels import validate_text
        validate_text(job_id,max_chars=100,nonempty=True)
        with self.storage._transaction() as c:return public_job(c,job_id)

    def cancel(self,job_id):
        from .jobs import update_status
        from .labels import validate_text
        validate_text(job_id,max_chars=100,nonempty=True)
        with self.storage._transaction(write=True) as c:
            job=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if job is None:raise NotFoundError()
            if job['state'] in ('pending','running'):
                c.execute("UPDATE jobs SET state='cancelled',token=NULL,worker=NULL,expires=NULL WHERE id=?",(job_id,))
                update_status(c,job,'cancelled')
            return public_job(c,job_id)

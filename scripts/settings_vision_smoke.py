#!/usr/bin/env python3
"""Actual authenticated scratch-host checks; no installation or model calls.

Only run against a fresh synthetic source library. Pauses processing before
admission; cancel/status/receipt checks do not pretend to verify inference.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from portability_smoke import API

PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYPgPAAEDAQAIicLsAAAAAElFTkSuQmCC'


def run(api,output,target=None):
    checks=[]
    def good(name,value):
        checks.append({'check':name,'ok':bool(value)})
        if not value:raise AssertionError(name)
    good('unauthenticated_settings_read_denied',api.request('/settings',auth=False)[0] in (401,403))
    good('unauthenticated_settings_write_denied',api.request('/settings',{},auth=False)[0] in (401,403))
    good('source_is_fresh_synthetic_library',api.call('/counts')['all']==0)
    original=api.call('/settings')
    saved=api.call('/settings',{'expected_revision':original['revision'],'changes':{
        'automatic_tags':False,'automatic_summary':False,'image_analysis':False,'paused':True,
        'summary_language':'Indonesian','summary_length':'short','guidance':'Synthetic verification only'}})
    good('settings_save_readback_exact',api.call('/settings')==saved)
    good('stale_settings_revision_conflicts',api.request('/settings',{'expected_revision':original['revision'],'changes':{'guidance':'stale'}})[0]==409)
    good('owner_cannot_be_changed',api.request('/settings',{'expected_revision':saved['revision'],'changes':{'owner_profile':'other'}})[0]==400)
    link=api.call('/items',{'url':'https://example.org/synthetic-settings-check','title':'Synthetic library settings check','notes':'Keep personal fixture notes','operation_key':str(uuid4())})
    good('automatic_processing_independently_disabled',link['enrichment_job_id'] is None)
    params={'expected_revision':link['revision'],'request_id':str(uuid4()),'fields':['summary']}
    first=api.call('/items/'+link['id']+'/enrich',params)
    good('enrichment_receipt_is_durable',api.call('/enrichment/requests/'+params['request_id'])['receipt']==first['receipt'])
    status=api.call('/enrichment/jobs/'+first['job']['id'])
    good('public_job_omits_lease_source_and_credentials',not set(status)&{'token','worker','settings','extracted_text','content_base64'})
    good('pause_prevents_claim_or_missing_route_fails_without_provider',status['state'] in ('pending','failed') and status['attempts']==0)
    stopped=api.call('/enrichment/jobs/'+status['id']+'/cancel',{})
    good('cancel_is_idempotent',api.call('/enrichment/jobs/'+status['id']+'/cancel',{})==stopped)
    link=api.call('/items/'+link['id']+'/update',{'expected_revision':link['revision'],'changes':{'summary':'Manually reviewed fixture summary'}})
    good('manual_summary_is_protected',link['summary_source']=='manual' and link['summary_revision']>0 and link['notes']=='Keep personal fixture notes')
    cleared=api.call('/items/'+link['id']+'/source/clear',{'expected_revision':link['revision']})
    good('source_clear_does_not_erase_notes_or_summary',cleared['notes']==link['notes'] and cleared['summary']==link['summary'])
    asset=api.call('/assets/base64',{'content_base64':PNG,'mime_type':'image/png'})
    image=api.call('/items',{'kind':'image','primary_asset_id':asset['id'],'title':'Synthetic blue pixel','operation_key':str(uuid4())})
    image_params={'expected_revision':image['revision'],'request_id':str(uuid4()),'fields':['tags','summary']}
    good('image_analysis_requires_library_opt_in',api.request('/items/'+image['id']+'/enrich',image_params)[0]==400)
    saved=api.call('/settings',{'expected_revision':saved['revision'],'changes':{'image_analysis':True}})
    image_job=api.call('/items/'+image['id']+'/enrich',image_params)
    good('opted_in_image_has_distinct_accepted_job',image_job['job']['id']!=first['job']['id'])
    good('field_order_is_canonical',image_job['receipt']['fields']==['summary','tags'])
    api.call('/enrichment/jobs/'+image_job['job']['id']+'/cancel',{})
    artifact=api.call('/exports',{'request_id':str(uuid4())})
    good('new_full_backup_is_version_two',artifact['format_version']==2)
    chunks=[];offset=0
    while offset<artifact['size']:
        row=api.call('/exports/'+artifact['id']+'?offset='+str(offset))
        chunks.append(base64.b64decode(row['content_base64']));offset=row['next_offset']
    bundle=b''.join(chunks)
    good('full_backup_integrity',len(bundle)==artifact['size'] and hashlib.sha256(bundle).hexdigest()==artifact['digest'])
    if target:
        target_settings=target.call('/settings');target_identity=target.call('/library/identity')
        good('target_fresh',target.call('/counts')['all']==0)
        upload=target.call('/backups/uploads',{'size':len(bundle),'digest':artifact['digest'],'request_id':str(uuid4())})
        for start in range(0,len(bundle),32768):target.call('/backups/uploads/'+upload['id']+'/chunks',{'offset':start,'content_base64':base64.b64encode(bundle[start:start+32768]).decode()})
        preview=target.call('/backups/preview',{'upload_id':upload['id']})
        target.call('/backups/restore',{'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':str(uuid4())})
        after=target.call('/settings')
        good('restored_settings_remain_inert',after['settings']==target_settings['settings'] and after['restored_intent']['image_analysis'] is True)
        good('target_identity_preserved',target.call('/library/identity')==target_identity)
        good('manual_summary_and_asset_restored',target.call('/items/'+link['id'])['summary_source']=='manual' and target.asset(asset['id'])==api.asset(asset['id']))
    report={'ok':True,'actual_authenticated_host':True,'provider_calls':False,'checks':checks,
        'settings':saved,'link_id':link['id'],'image_id':image['id'],'request_ids':[params['request_id'],image_params['request_id']],
        'receipt':first['receipt'],'image_receipt':image_job['receipt'],'artifact_id':artifact['id']}
    Path(output).write_text(json.dumps(report,indent=2));print(json.dumps({'ok':True,'checks':len(checks),'provider_calls':False}));return report


def reopen(api,previous,output):
    before=json.loads(Path(previous).read_text())
    assert api.call('/settings')==before['settings']
    assert api.call('/enrichment/requests/'+before['request_ids'][0])['receipt']==before['receipt']
    assert api.call('/enrichment/requests/'+before['request_ids'][1])['receipt']==before['image_receipt']
    link=api.call('/items/'+before['link_id']);assert link['summary_source']=='manual' and link['summary']=='Manually reviewed fixture summary'
    Path(output).write_text(json.dumps({'ok':True,'actual_restart_readback':True,'settings_receipts_and_summary_match':True,'provider_calls':False},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('origin');p.add_argument('token_file');p.add_argument('output');p.add_argument('--allow-write',action='store_true')
    p.add_argument('--target-origin');p.add_argument('--target-token-file');p.add_argument('--reopen')
    a=p.parse_args();api=API(a.origin,a.token_file)
    if a.reopen:reopen(api,a.reopen,a.output)
    else:
        if not a.allow_write:p.error('--allow-write is required for synthetic fixture mutation')
        target=API(a.target_origin,a.target_token_file) if a.target_origin and a.target_token_file else None
        run(api,a.output,target)

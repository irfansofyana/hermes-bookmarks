#!/usr/bin/env python3
"""Synthetic-only acceptance setup. NEVER a provider success test.

Import uses actual authenticated HTTP. Retained-body setup requires the owned
server STOPPED; it completes a real queue row with explicitly synthetic data.
"""
import json,sys,time,argparse
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from portability_smoke import API

TITLE='Synthetic retained source check'
BODY='Retained synthetic article body — not a real publisher fetch.'


def imported(api,output):
    preview=api.call('/imports/preview',{'records':[{'url':'https://example.org/synthetic-retained-fixture','title':TITLE,'notes':'Imported fixture notes stay','source_text':'Imported fixture source must stay','imported_summary':'Imported fixture summary stays','source_id':'synthetic-source','provenance':{'source':'Synthetic acceptance fixture','locator':'fixture row'}}]})
    job=api.call('/imports/start',{'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':str(uuid4())})
    deadline=time.monotonic()+30;status=job
    while time.monotonic()<deadline:
        status=api.call('/imports/'+job['id'])
        if status['state'] in ('succeeded','failed','cancelled'):break
        time.sleep(.1)
    assert status['state']=='succeeded' and status['imported']==1,status
    item=next(row for row in api.call('/items')['items'] if row['title']==TITLE)
    assert item['imported_sources'][0]['source_text']=='Imported fixture source must stay'
    Path(output).write_text(json.dumps({'ok':True,'actual_http_import':True,'synthetic':True,'item_id':item['id'],'import_job_id':job['id'],'provider_calls':False},indent=2))


def retained(root,previous,fixture,output):
    root=Path(root).resolve()
    assert any(part.startswith('bookmarks-portability-host-') for part in root.parts)
    from bookmarks.service import BookmarkService
    from bookmarks.jobs import JobQueue
    service=BookmarkService(root);original=service.settings_get()
    service.settings_update(original['revision'],{'paused':False,'retain_extracted_text':True})
    identity=json.loads(Path(fixture).read_text())['item_id'];item=service.get(identity)
    accepted=service.enrich(identity,item['revision'],str(uuid4()),['tags'])
    queue=JobQueue(root);claim=queue.claim('synthetic-acceptance-seed')
    assert claim and claim['id']==accepted['job']['id']
    assert queue.complete(claim['id'],'synthetic-acceptance-seed',{'tags':['Synthetic fixture'],'provider':'synthetic-fixture-NOT-inference','model':'synthetic-fixture-NOT-inference','coverage':'extracted_text'},token=claim['token'],extracted_text=BODY)
    before=service.settings_get()
    final=service.settings_update(before['revision'],{k:v for k,v in original['settings'].items() if k!='owner_profile'})
    assert service.get(identity)['extracted_text']==BODY and final['settings']['paused'] is True
    snapshot=json.loads(Path(previous).read_text());snapshot['settings']=final;snapshot['retained_item_id']=identity
    snapshot['setup_disclosure']='Retained body is an explicit synthetic queue fixture, NOT model output or publisher extraction. Server stopped during queue setup.'
    Path(output).write_text(json.dumps(snapshot,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['import','retained']);p.add_argument('args',nargs='+');p.add_argument('--allow-write',action='store_true');a=p.parse_args()
    if not a.allow_write:p.error('--allow-write required')
    if a.mode=='import':imported(API(a.args[0],a.args[1]),a.args[2])
    else:retained(*a.args)

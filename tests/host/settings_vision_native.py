#!/usr/bin/env python3
"""Real registered tools in a disposable synthetic HOME; no inference."""
import argparse,base64,hashlib,json,os
from pathlib import Path
from uuid import uuid4


def run(archive,output):
    from hermes_cli.plugins import get_plugin_manager
    from model_tools import handle_function_call
    home=Path(os.environ['HERMES_HOME']).resolve()
    assert any(part.startswith('bookmarks-portability-host-') for part in home.parts)
    get_plugin_manager().discover_and_load();exercised=[]
    def call(name,params):
        envelope=json.loads(handle_function_call(name,params))
        assert envelope.get('ok'),(name,envelope.get('error',{}).get('code'))
        exercised.append(name);return envelope['result']
    cfg=call('bookmark_settings_get',{})
    cfg=call('bookmark_settings_update',{'expected_revision':cfg['revision'],'changes':{'automatic_summary':False,'automatic_tags':False,'paused':True}})
    # An actual previous-writer ZIP, not a v2 payload passed to a lenient reader.
    content=Path(archive).read_bytes();digest=hashlib.sha256(content).hexdigest()
    upload=call('bookmark_backup_upload_create',{'size':len(content),'digest':digest,'request_id':str(uuid4())})
    for offset in range(0,len(content),32768):call('bookmark_backup_upload_chunk',{'upload_id':upload['id'],'offset':offset,'content_base64':base64.b64encode(content[offset:offset+32768]).decode()})
    preview=call('bookmark_backup_preview',{'upload_id':upload['id']});assert preview['format_version']==1
    result=call('bookmark_backup_restore',{'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':str(uuid4())});assert result['state']=='succeeded'
    after=call('bookmark_settings_get',{});assert after['settings']==cfg['settings'] and after['restored_intent'] is not None
    rows=call('bookmark_search',{})['items'];item=next(row for row in rows if row['kind']=='link' and row['deleted_at'] is None)
    request={'item_id':item['id'],'expected_revision':item['revision'],'request_id':str(uuid4()),'fields':['tags']}
    admitted=call('bookmark_enrich',request)
    assert call('bookmark_enrichment_request_get',{'request_id':request['request_id']})['receipt']==admitted['receipt']
    status=call('bookmark_enrichment_get',{'job_id':admitted['job']['id']});assert status['state']=='pending' and status['attempts']==0
    stopped=call('bookmark_enrichment_cancel',{'job_id':status['id']});assert stopped['state']=='cancelled'
    current=call('bookmark_get',{'item_id':item['id']})
    cleared=call('bookmark_source_clear',{'item_id':item['id'],'expected_revision':current['revision']})
    assert cleared['notes']==current['notes'] and cleared['imported_sources']==current['imported_sources']
    expected={'bookmark_settings_get','bookmark_settings_update','bookmark_enrich','bookmark_enrichment_request_get','bookmark_enrichment_get','bookmark_enrichment_cancel','bookmark_source_clear'}
    assert expected<=set(exercised)
    report={'ok':True,'actual_native_registry':True,'synthetic':True,'provider_calls':False,'new_operations':sorted(expected),'tools_exercised':sorted(set(exercised)),'v1_restore_inert':True,'restored_counts':result['counts']}
    Path(output).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('output');p.add_argument('--allow-write',action='store_true');a=p.parse_args()
    if not a.allow_write:p.error('--allow-write required for synthetic scratch state')
    run(a.archive,a.output)

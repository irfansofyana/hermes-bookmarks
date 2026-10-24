#!/usr/bin/env python3
"""Actual loopback Hermes import/trash checks using synthetic records only.

Requires --allow-write for mutation mode. --reopen reads saved evidence after an
operator-owned disposable restart; it never configures or restarts a service.
Owner API activation can resume previously accepted work. Do not use a personal
library. Credentials and response bodies are never written to the report.
"""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def run(base,token,*,allow_write=False,reopen=None):
    url=urllib.parse.urlsplit(base)
    if url.hostname!='127.0.0.1' or url.scheme!='http' or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:raise ValueError('Explicit credential-free loopback origin required')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    prefix='/api/plugins/hermes-bookmarks';checks=[]
    def req(path,body=None,auth=True):
        headers={'Accept':'application/json'}
        if auth:headers['X-Hermes-Session-Token']=token
        if body is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(base.rstrip('/')+prefix+path,headers=headers,data=None if body is None else json.dumps(body).encode(),method='GET' if body is None else 'POST')
        try:response=opener.open(request,timeout=20)
        except urllib.error.HTTPError as error:response=error
        with response:
            content=response.read(4*1024*1024+1)
            if len(content)>4*1024*1024:raise ValueError('Response too large')
            return response.status,json.loads(content)
    def good(name,condition):
        checks.append({'check':name,'ok':bool(condition)})
        if not condition:raise AssertionError(name)
    def api(path,body=None):
        status,payload=req(path,body);good('http_'+path.split('?')[0],status==200 and payload.get('ok') is True);return payload['result']
    def wait(jid):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            result=api('/imports/'+jid)
            if result['state'] not in ('pending','running'):return result
            time.sleep(.15)
        raise TimeoutError('Import did not reach terminal status')
    good('unauthorized_import_read',req('/imports/missing',auth=False)[0] in (401,403))
    good('unauthorized_import_write',req('/imports/preview',{'records':[]},auth=False)[0] in (401,403))
    if reopen:
        previous=json.loads(Path(reopen).read_text());j=wait(previous['job_id']);item=api('/items/'+previous['item_id'])
        good('restart_report_persists',j['imported']==2 and j['skipped']==1 and j['failed']==1)
        good('restart_notes_provenance_persist',item['notes']=='Synthetic imported **notes**' and item['imported_sources'][0]['source_id']=='fixture-1')
        return {'ok':True,'actual_host':True,'mode':'reopen','checks':checks,'job_id':j['id'],'item_id':item['id'],'provider_calls':False}
    if not allow_write:raise ValueError('Synthetic write mode requires --allow-write')
    source='https://example.org/synthetic-import-'+uuid4().hex
    records=[{'url':source,'title':'Synthetic imported bookmark','notes':'Synthetic imported **notes**','tags':['ImportQA'],'collection_path':['Synthetic imports','Nested'],'source_id':'fixture-1','imported_summary':'Source-provided synthetic summary','source_text':'Synthetic retained source text'}, {'url':source}, {'url':'javascript:invalid'}, {'url':source+'/second'}]
    preview=api('/imports/preview',{'records':records})
    good('preview_reconciles',preview['total']==4 and preview['valid']==2 and preview['invalid']==1 and preview['duplicate_in_batch']==1)
    good('preview_no_item_writes',api('/items?query='+urllib.parse.quote(source))['total']==0)
    rid=str(uuid4());params={'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':rid}
    accepted=api('/imports/start',params);again=api('/imports/start',params)
    good('idempotent_start',accepted['id']==again['id'])
    good('readonly_request_lookup',api('/imports/requests/'+rid)['id']==accepted['id'])
    job=wait(accepted['id']);good('exact_terminal_counts',(job['total'],job['processed'],job['remaining'],job['imported'],job['skipped'],job['failed'])==(4,4,0,2,1,1))
    item=api('/items/'+next(row['item_id'] for row in job['rows'] if row['index']==0))
    good('import_provenance_not_generated',item['summary']=='' and item['imported_sources'][0]['imported_summary']=='Source-provided synthetic summary')
    trashed=api('/items/'+item['id']+'/trash',{'expected_revision':item['revision']})
    good('trash_excluded',api('/items?query='+urllib.parse.quote(source))['total']==1)
    restored=api('/items/'+item['id']+'/restore',{'expected_revision':trashed['revision']})
    good('restore_keeps_notes',restored['notes']==item['notes'])
    html='<DL><DT><H3>Synthetic HTML</H3><DL><DT><A HREF="'+source+'/html">Synthetic HTML link</A><DD>Source description</DL></DL>'
    hp=api('/imports/preview',{'html':html});hj=api('/imports/start',{'preview_id':hp['preview_id'],'input_digest':hp['input_digest'],'request_id':str(uuid4())})
    good('actual_html_import',wait(hj['id'])['imported']==1)
    batch=[{'url':source+'/cancel/'+str(i)} for i in range(100)]
    cp=api('/imports/preview',{'records':batch});cj=api('/imports/start',{'preview_id':cp['preview_id'],'input_digest':cp['input_digest'],'request_id':str(uuid4())})
    cancelled=api('/imports/'+cj['id']+'/cancel',{})
    good('cancel_reconciles',cancelled['state']=='cancelled' and cancelled['processed']+cancelled['remaining']==cancelled['total'])
    good('cancel_stops_progress',api('/imports/'+cj['id'])['processed']==cancelled['processed'])
    return {'ok':True,'actual_host':True,'mode':'synthetic_write','checks':checks,'job_id':job['id'],'item_id':item['id'],'html_job_id':hj['id'],'cancel_processed':cancelled['processed'],'cancel_remaining':cancelled['remaining'],'provider_calls':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-url',required=True);p.add_argument('--token-file',type=Path,required=True);p.add_argument('--allow-write',action='store_true');p.add_argument('--reopen',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=run(a.base_url,a.token_file.read_text().strip(),allow_write=a.allow_write,reopen=a.reopen)
    a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()

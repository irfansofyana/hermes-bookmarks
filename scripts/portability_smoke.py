#!/usr/bin/env python3
"""Real authenticated loopback source/empty-target portability verification.

Requires two disposable Hermes homes/libraries explicitly prepared by operator.
Never configures/restarts services and never prints tokens or raw library data.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None

class API:
 def __init__(self,origin,token_file):
  url=urllib.parse.urlsplit(origin)
  if url.scheme!='http' or url.hostname!='127.0.0.1' or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:raise ValueError('Explicit credential-free loopback origin required')
  self.origin=origin.rstrip('/')+'/api/plugins/hermes-bookmarks';self.token=Path(token_file).read_text().strip();self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 def request(self,route,body=None,auth=True):
  headers={'Accept':'application/json'}
  if auth:headers['X-Hermes-Session-Token']=self.token
  if body is not None:headers['Content-Type']='application/json'
  req=urllib.request.Request(self.origin+route,data=None if body is None else json.dumps(body).encode(),headers=headers,method='GET' if body is None else 'POST')
  try:response=self.opener.open(req,timeout=120)
  except urllib.error.HTTPError as error:response=error
  with response:
   raw=response.read(200000)
   if len(raw)>=200000:raise ValueError('Unexpected unbounded response')
   return response.status,json.loads(raw)
 def call(self,route,body=None):
  status,payload=self.request(route,body)
  if status!=200 or payload.get('ok') is not True:raise AssertionError((route,status,payload.get('error',{}).get('code')))
  return payload['result']

def run(source,target,output):
 checks=[]
 def good(name,condition):
  checks.append({'check':name,'ok':bool(condition)})
  if not condition:raise AssertionError(name)
 for api in [source,target]:good('unauthorized_export_and_restore_rejected',api.request('/exports/requests/'+str(uuid4()),auth=False)[0] in (401,403) and api.request('/backups/restore',{},auth=False)[0] in (401,403))
 identity=target.call('/library/identity');good('target_initially_empty',target.call('/counts')['all']==0 and target.call('/collections')['total']==0)
 rid=str(uuid4());artifact=source.call('/exports',{'format':'bundle','request_id':rid});good('artifact_ready',artifact['state']=='ready');good('export_receipt_idempotent',source.call('/exports',{'format':'bundle','request_id':rid})==artifact);good('export_lookup',source.call('/exports/requests/'+rid)==artifact)
 parts=[];offset=0
 while offset<artifact['size']:
  chunk=source.call('/exports/'+artifact['id']+'?offset='+str(offset));data=base64.b64decode(chunk['content_base64']);good('bounded_download_chunk',0<len(data)<=32768);parts.append(data);offset=chunk['next_offset']
 content=b''.join(parts);good('full_download_integrity',len(content)==artifact['size'] and hashlib.sha256(content).hexdigest()==artifact['digest'])
 upload_id=str(uuid4());params={'size':len(content),'digest':artifact['digest'],'request_id':upload_id};upload=target.call('/backups/uploads',params)
 for offset in range(0,len(content),32768):
  params_chunk={'offset':offset,'content_base64':base64.b64encode(content[offset:offset+32768]).decode()};got=target.call('/backups/uploads/'+upload['id']+'/chunks',params_chunk);good('upload_exact_offset',got['offset']==offset+len(content[offset:offset+32768]))
 good('upload_resume_lookup',target.call('/backups/uploads',params)['offset']==len(content))
 preview=target.call('/backups/preview',{'upload_id':upload['id']});good('preview_no_content_mutation',target.call('/counts')['all']==0)
 request=str(uuid4());params={'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':request};restored=target.call('/backups/restore',params);good('restore_succeeded',restored['state']=='succeeded');good('restore_idempotent',target.call('/backups/restore',params)==restored);good('restore_lookup',target.call('/backups/requests/'+request)==restored);good('target_identity_preserved',target.call('/library/identity')==identity)
 # Compare every bounded item page and supported content projection, including Trash.
 compared=0
 for view in ['all','trash']:
  offset=0
  while True:
   route='/items?view='+view+'&limit=100&offset='+str(offset);a=source.call(route);b=target.call(route);good('item_page_counts_'+view,a['total']==b['total'])
   by_id={row['id']:row for row in b['items']}
   for row in a['items']:
    actual=by_id[row['id']]
    fields=['id','url','title','notes','description','summary','tags','tag_details','attachments','imported_sources','kind','collection_id','favorite','read_later','revision','deleted_at','created_at','updated_at']
    good('exact_saved_item_projection',all(row.get(key)==actual.get(key) for key in fields));compared+=1
    for asset in row['attachments']:
     left=source.call('/assets/'+asset['asset_id']+'/preview');right=target.call('/assets/'+asset['asset_id']+'/preview');good('owned_asset_preview_bytes',left==right)
   offset+=100
   if offset>=a['total']:break
 good('restored_nonempty_target_rejects_new_preview',target.request('/backups/preview',{'upload_id':upload['id']})[0]==409)
 html=source.call('/exports',{'format':'html','request_id':str(uuid4())});good('html_explicitly_lossy',bool(html['limitations']) and html['state']=='ready')
 report={'ok':True,'actual_authenticated_hosts':True,'provider_calls':False,'checks':checks,'compared_items':compared,'artifact_id':artifact['id'],'archive_size':len(content),'archive_digest':artifact['digest'],'restore_request_id':request,'restore_id':restored['id'],'target_identity':identity['library_id']}
 Path(output).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--source-token-file',required=True);p.add_argument('--target',required=True);p.add_argument('--target-token-file',required=True);p.add_argument('--output',required=True);p.add_argument('--allow-write',action='store_true');a=p.parse_args()
 if not a.allow_write:p.error('Synthetic verification requires --allow-write')
 run(API(a.source,a.source_token_file),API(a.target,a.target_token_file),a.output)

#!/usr/bin/env python3
"""Exercise real Hermes native registry in two disposable fixture homes only."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4


def run(mode,exchange):
 from hermes_cli.plugins import get_plugin_manager
 from model_tools import handle_function_call
 home=Path(os.environ['HERMES_HOME']).resolve();assert any(part.startswith('bookmarks-portability-host-') for part in home.parts)
 manager=get_plugin_manager();manager.discover_and_load();exercised=[]
 def call(name,params):
  envelope=json.loads(handle_function_call(name,params))
  if not envelope.get('ok'):raise AssertionError((name,envelope.get('error',{}).get('code')))
  exercised.append(name);return envelope['result']
 exchange=Path(exchange)
 if mode=='source':
  request=str(uuid4());artifact=call('bookmark_export_create',{'request_id':request});assert call('bookmark_export_get',{'request_id':request})==artifact;parts=[];offset=0
  while offset<artifact['size']:
   chunk=call('bookmark_export_read',{'artifact_id':artifact['id'],'offset':offset});raw=base64.b64decode(chunk['content_base64']);assert len(raw)<=32768;parts.append(raw);offset=chunk['next_offset']
  content=b''.join(parts);assert hashlib.sha256(content).hexdigest()==artifact['digest'];exchange.write_bytes(content)
  report={'ok':True,'actual_native_registry':True,'mode':mode,'tools_exercised':sorted(set(exercised)),'size':len(content),'digest':artifact['digest'],'provider_calls':False}
 else:
  content=exchange.read_bytes();digest=hashlib.sha256(content).hexdigest();params={'size':len(content),'digest':digest,'request_id':str(uuid4())};upload=call('bookmark_backup_upload_create',params)
  for offset in range(0,len(content),32768):call('bookmark_backup_upload_chunk',{'upload_id':upload['id'],'offset':offset,'content_base64':base64.b64encode(content[offset:offset+32768]).decode()})
  preview=call('bookmark_backup_preview',{'upload_id':upload['id']});params={'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':str(uuid4())};result=call('bookmark_backup_restore',params);assert result['state']=='succeeded';assert call('bookmark_backup_restore_get',{'request_id':params['request_id']})==result;assert call('bookmark_backup_restore',params)==result
  report={'ok':True,'actual_native_registry':True,'mode':mode,'tools_exercised':sorted(set(exercised)),'counts':result['counts'],'restore_id':result['id'],'provider_calls':False}
 path=exchange.parent/('native-'+mode+'.json');path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['source','target']);p.add_argument('exchange',type=Path);p.add_argument('--allow-write',action='store_true');a=p.parse_args()
 if not a.allow_write:p.error('--allow-write required for synthetic native verification')
 run(a.mode,a.exchange)

#!/usr/bin/env python3
"""Real backend smoke checks; read-only unless explicitly allowed synthetic writes.

No SDK mocks, direct model invocation, configuration changes or host restarts.
GET-only checks may activate the owner's backend and resume already queued work;
use a disposable home with enrichment disabled for charge-free checks. Never
prints credentials or response bodies. Use a disposable home for --allow-write.
"""
import argparse
import base64
from io import BytesIO
import ipaddress
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl): return None


class _CheckFailed(Exception): pass


def run_smoke(base_url,token,*,allow_write=False,allow_remote=False,timeout=10,item_id=None,asset_id=None):
    url=urllib.parse.urlsplit(base_url)
    if url.scheme not in ('http','https') or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use a credential-free HTTP(S) backend origin')
    try: loopback=ipaddress.ip_address(url.hostname).is_loopback
    except ValueError: loopback=url.hostname=='localhost'
    if not loopback and not allow_remote: raise ValueError('Remote hosts require --allow-remote')
    if url.path not in ('','/'): raise ValueError('Supply the backend origin without a path')
    base_url=base_url.rstrip('/')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
    checks=[]; report={'ok':False,'checks':checks,'synthetic_writes':bool(allow_write)}
    prefix='/api/plugins/hermes-bookmarks'
    current='backend_status'
    def request(path,method='GET',body=None,authenticated=True):
        headers={'Accept':'application/json'}
        if authenticated and token: headers['X-Hermes-Session-Token']=token
        data=None
        if body is not None:
            data=json.dumps(body).encode(); headers['Content-Type']='application/json'
        req=urllib.request.Request(base_url+path,data=data,headers=headers,method=method)
        try: response=opener.open(req,timeout=timeout)
        except urllib.error.HTTPError as error: response=error
        with response:
            content=response.read(1024*1024+1)
            if len(content)>1024*1024: raise ValueError('Smoke response exceeds 1 MiB')
            return response.status,response.headers,content
    def check(name,condition,status):
        nonlocal current
        current=name
        checks.append({'name':name,'ok':bool(condition),'http_status':status})
        if not condition: raise _CheckFailed()
    try:
        status,_,body=request('/api/status',authenticated=False)
        check('backend_status',status==200 and isinstance(json.loads(body),dict),status)
        payload=json.loads(body)
        if isinstance(payload.get('version'),str): report['backend_version']=payload['version']
        current='plugin_health'
        status,_,body=request(prefix+'/health')
        check(current,status==200 and json.loads(body).get('ok') is True,status)
        health=json.loads(body)
        report['health_observation']={key:health[key] for key in ('library_configured','enrichment_startups') if key in health}
        current='unauthorized_items'
        status,_,_=request(prefix+'/items',authenticated=False)
        check(current,status in (401,403),status)
        current='library_read'
        status,_,body=request(prefix+'/items')
        check(current,status==200 and json.loads(body).get('ok') is True,status)
        if allow_write:
            current='capture'
            capture={'url':'https://example.org/hermes-bookmarks-smoke/'+uuid4().hex,'title':'Synthetic host smoke bookmark'}
            status,_,body=request(prefix+'/items','POST',capture)
            check(current,status==200 and json.loads(body).get('ok') is True,status)
            item_id=json.loads(body)['result']['id']; report['item_id']=item_id
            status,_,body=request(prefix+'/items','POST',capture)
            check('duplicate_save',status==200 and json.loads(body)['result']['id']==item_id,status)
            current='unauthorized_capture'
            status,_,_=request(prefix+'/items','POST',capture,authenticated=False)
            check(current,status in (401,403),status)
            from PIL import Image
            image=BytesIO(); Image.new('RGB',(2,2),'blue').save(image,format='PNG')
            current='asset_upload'
            status,_,body=request(prefix+'/assets/base64','POST',{'mime_type':'image/png','content_base64':base64.b64encode(image.getvalue()).decode('ascii')})
            check(current,status==200 and json.loads(body).get('ok') is True,status)
            metadata=json.loads(body)['result']; asset_id=metadata['id']; report['asset_id']=asset_id
            check('asset_dimensions',(metadata['width'],metadata['height'])==(2,2) and 'path' not in metadata,status)
        if item_id:
            current='saved_item_read'
            status,_,body=request(prefix+'/items/'+urllib.parse.quote(item_id,safe=''))
            check(current,status==200 and json.loads(body)['result']['id']==item_id,status)
        if asset_id:
            import re
            if not re.fullmatch('[a-f0-9]{32}',asset_id): raise ValueError('Invalid owned asset ID')
            current='unauthorized_asset'
            status,_,_=request(prefix+'/assets/'+asset_id,authenticated=False)
            check(current,status in (401,403),status)
            current='asset_download'
            status,headers,body=request(prefix+'/assets/'+asset_id)
            check(current,status==200 and headers.get_content_type()=='image/png' and headers.get('X-Content-Type-Options')=='nosniff',status)
            from PIL import Image
            with Image.open(BytesIO(body)) as image: check('decoded_asset',image.size==(2,2),status)
            current='asset_preview'
            status,_,body=request(prefix+'/assets/'+asset_id+'/preview')
            preview=json.loads(body)['result']
            check(current,status==200 and preview['mime_type']=='image/jpeg',status)
            with Image.open(BytesIO(base64.b64decode(preview['content_base64'],validate=True))) as image:
                check('decoded_preview',image.size==(2,2),status)
        report['ok']=True
    except _CheckFailed: pass
    except Exception as error:
        checks.append({'name':current,'ok':False,'error_kind':type(error).__name__})
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--token-file',type=Path,required=True)
    parser.add_argument('--allow-write',action='store_true',help='Create only synthetic fixture bookmarks/images in a disposable host')
    parser.add_argument('--allow-remote',action='store_true')
    parser.add_argument('--item-id'); parser.add_argument('--asset-id')
    args=parser.parse_args()
    try:
        report=run_smoke(args.base_url,args.token_file.read_text().strip(),allow_write=args.allow_write,allow_remote=args.allow_remote,item_id=args.item_id,asset_id=args.asset_id)
    except (OSError,ValueError) as error:
        report={'ok':False,'checks':[],'error_kind':type(error).__name__}
    print(json.dumps(report,indent=2))
    return 0 if report['ok'] else 1


if __name__=='__main__': raise SystemExit(main())

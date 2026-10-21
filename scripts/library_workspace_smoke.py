#!/usr/bin/env python3
"""Authenticated real-host library checks; synthetic writes require --allow-write.

Use only a disposable home with enrichment unconfigured: any owner API entry can
resume accepted jobs. No credential/config discovery, inference, redirects or
service restarts. Output contains check names and fixture IDs, never auth/body.
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
from uuid import UUID,uuid4


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def run_smoke(base_url,token,*,allow_write=False,operation_key=None,timeout=15):
    origin=urllib.parse.urlsplit(base_url)
    if origin.scheme not in ('http','https') or origin.username or origin.password or origin.path not in ('','/') or origin.query or origin.fragment:
        raise ValueError('Use a credential-free loopback HTTP(S) origin without a path.')
    try:loopback=ipaddress.ip_address(origin.hostname).is_loopback
    except ValueError:loopback=origin.hostname=='localhost'
    if not loopback:raise ValueError('This synthetic smoke probe is loopback only.')
    if operation_key is not None:
        if str(UUID(operation_key))!=operation_key:raise ValueError('Invalid capture operation key.')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    prefix=base_url.rstrip('/')+'/api/plugins/hermes-bookmarks'
    report={'ok':False,'synthetic_writes':bool(allow_write),'checks':[]}
    def request(path,method='GET',body=None,auth='valid'):
        headers={'Accept':'application/json'}
        if auth!='none':headers['X-Hermes-Session-Token']=token if auth=='valid' else 'invalid-synthetic-token'
        data=json.dumps(body).encode() if body is not None else None
        if data is not None:headers['Content-Type']='application/json'
        try:response=opener.open(urllib.request.Request(prefix+path,headers=headers,data=data,method=method),timeout=timeout)
        except urllib.error.HTTPError as error:response=error
        with response:
            raw=response.read(1024*1024+1)
            if len(raw)>1024*1024:raise ValueError('Oversized response.')
            try:payload=json.loads(raw)
            except (ValueError,UnicodeDecodeError):payload={}
            return response.status,payload
    def check(name,condition):
        report['checks'].append({'name':name,'ok':bool(condition)})
        if not condition:raise AssertionError(name)
    def success(path,method='GET',body=None):
        status,payload=request(path,method,body)
        check(method+' '+path.split('?')[0],status==200 and payload.get('ok') is True)
        return payload
    try:
        for auth in ('none','invalid'):
            status,_=request('/items',auth=auth);check(auth+' GET denied',status in (401,403))
            status,_=request('/items','POST',{'url':'https://example.org/unauthorized'},auth);check(auth+' POST denied',status in (401,403))
        library=success('/library/identity')['result'];check('library identity',bool(library.get('library_id')))
        report['library_id']=library['library_id']
        if allow_write:
            from PIL import Image
            image=BytesIO();Image.new('RGB',(8,8),'teal').save(image,format='PNG')
            asset=success('/assets/base64','POST',{'mime_type':'image/png','content_base64':base64.b64encode(image.getvalue()).decode()})['result']
            name='Synthetic workspace '+uuid4().hex[:12]
            collection=success('/collections','POST',{'name':name,'parent_id':None})['result']
            child=success('/collections','POST',{'name':'Child','parent_id':collection['id']})['result']
            operation_key=str(uuid4())
            body={'kind':'link','url':'https://example.org/'+name.replace(' ','-'),'title':name,'notes':'Synthetic note','description':'Synthetic description','collection_id':child['id'],'tags':['WorkspaceTest','Reading'],'attachment_ids':[asset['id']],'operation_key':operation_key}
            created=success('/items','POST',body)
            item=created['result'];report.update(item_id=item['id'],asset_id=asset['id'],collection_id=collection['id'],operation_key=operation_key)
            check('capture retained all metadata',item['notes']=='Synthetic note' and item['description']=='Synthetic description' and item['attachments'][0]['asset_id']==asset['id'])
            replay=success('/items','POST',body);check('same-key replay',replay['result']['id']==item['id'] and replay['receipt']==created['receipt'])
            item=success('/items/'+item['id'])['result']
            changed=success('/items/'+item['id']+'/update','POST',{'expected_revision':item['revision'],'changes':{'notes':'Synthetic edited note','favorite':True,'add_tags':['Edited']}})['result']
            check('revision-safe edit',changed['notes']=='Synthetic edited note' and changed['favorite'] is True)
            status,payload=request('/items/'+item['id']+'/update','POST',{'expected_revision':item['revision'],'changes':{'notes':'Stale data'}})
            check('stale revision rejects atomically',status==409 and payload.get('error',{}).get('code')=='conflict')
            found=success('/items?'+urllib.parse.urlencode([('query',name),('collection_id',collection['id']),('tag','WorkspaceTest'),('tag','Edited')]))['result']
            check('descendant and repeated-tag AND query',found['total']==1 and found['items'][0]['id']==item['id'])
            counts=success('/counts')['result'];check('snapshot counts',counts['favorites']>=1 and counts['all']>=1)
            standalone=success('/items','POST',{'kind':'image','primary_asset_id':asset['id'],'title':'Synthetic owned image','operation_key':str(uuid4())})['result']
            check('standalone image has no URL and honest status',standalone['url'] is None and standalone['kind']=='image' and standalone['enrichment_status']=='not_configured')
            report['image_item_id']=standalone['id']
        if operation_key:
            receipt=success('/captures/'+operation_key)['result'];item=receipt['item']
            report.update(item_id=item['id'],operation_key=operation_key)
            check('receipt preserves accepted identity',receipt['receipt']['item_id']==item['id'])
            fresh=success('/items/'+item['id'])['result']
            check('readback preserves edited note and owned association',fresh['notes']=='Synthetic edited note' and bool(fresh['attachments']))
            report['asset_id']=fresh['attachments'][0]['asset_id']
            preview=success('/assets/'+report['asset_id']+'/preview')['result'];check('authenticated preview',bool(base64.b64decode(preview['content_base64'],validate=True)))
        report['ok']=True
    except Exception as error:
        report['error_kind']=type(error).__name__
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--token-file',required=True,type=Path)
    parser.add_argument('--allow-write',action='store_true');parser.add_argument('--operation-key');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:report=run_smoke(args.base_url,args.token_file.read_text().strip(),allow_write=args.allow_write,operation_key=args.operation_key)
    except (ValueError,OSError):report={'ok':False,'checks':[],'error_kind':'invalid_configuration'}
    text=json.dumps(report,indent=2)
    if args.output:args.output.write_text(text)
    print(text);return 0 if report['ok'] else 1


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Exact read-only synthetic-host snapshot/restart readback, including bytes."""
import argparse,base64,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.portability_smoke import API


def run(origin,token_file,output,compare=None):
    api=API(origin,token_file);page=api.call('/items?limit=100')
    assert page['total']==len(page['items'])<=100,'Synthetic snapshot must include every active item'
    items=sorted((api.call('/items/'+row['id']) for row in page['items']),key=lambda row:row['id'])
    asset_ids={row['primary_asset_id'] for row in items if row['primary_asset_id']}
    asset_ids.update(asset['asset_id'] for row in items for asset in row['attachments'])
    assets={}
    for identity in sorted(asset_ids):
        content,mime=api.asset(identity)
        assert len(content)<=10000,'Only tiny synthetic assets belong in public evidence'
        assets[identity]={'mime_type':mime,'size':len(content),'sha256':hashlib.sha256(content).hexdigest(),'content_base64':base64.b64encode(content).decode()}
    fingerprint={'identity':api.call('/library/identity'),'settings':api.call('/settings'),'counts':api.call('/counts'),'items':items,'assets':assets}
    if compare:assert fingerprint==json.loads(Path(compare).read_text())['fingerprint'],'Restart changed exact settings/content/identity/binary bytes'
    report={'ok':True,'actual_authenticated_host':True,'read_only':True,'synthetic':True,'after_restart':bool(compare),'fingerprint':fingerprint}
    Path(output).write_text(json.dumps(report,indent=2));print(json.dumps({'ok':True,'after_restart':bool(compare),'items':len(items),'assets':len(assets)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('origin');p.add_argument('token_file');p.add_argument('output');p.add_argument('--compare');a=p.parse_args();run(a.origin,a.token_file,a.output,a.compare)

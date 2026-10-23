"""Seed public service-produced synthetic content; no providers or user files."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from bookmarks.service import BookmarkService
from bookmarks.assets import AssetStore
from bookmarks.imports.runner import ImportQueue
from bookmarks.tags import merge_generated


def seed(root):
 s=BookmarkService(root);image=AssetStore(root).store_image((Path(__file__).parents[1]/'tests/fixtures/tiny.png').read_bytes(),'image/png')
 folder=s.collection_create('Synthetic Café 🌏');nested=s.collection_create('Nested',folder['id']);s.collection_create('Empty synthetic folder')
 link=s.capture(url='https://example.org/portability-qa',title='Synthetic saved reading',notes='## Saved context\n\nSynthetic **notes**, not a generated summary.\n\n- [ ] Read carefully',description='A synthetic description',tags=['Manual','Café'],collection_id=nested['id'],favorite=True,read_later=True,attachment_ids=[image['id']])['item']
 with s._storage._transaction(write=True) as c:
  merge_generated(c,link['id'],['Generated','Suppressed']);c.execute('UPDATE items SET summary=? WHERE id=?',('Previously saved synthetic summary',link['id']))
 s.update(link['id'],link['revision'],{'remove_tags':['Suppressed']})
 s.capture(kind='image',primary_asset_id=image['id'],operation_key=str(uuid4()),title='Synthetic image item',notes='Saved standalone-image context')
 trash=s.save_link('https://example.org/portability-trash','Synthetic trashed reading');s.trash(trash['id'],trash['revision'])
 p=s.import_preview(records=[{'url':'https://example.org/portability-import','title':'Synthetic source-provenance item','source_id':'qa-origin-1','source_text':'Retained source needle Ω','imported_summary':'Imported, not generated','provenance':{'source':'Synthetic fixture','locator':'row 1'}}]);s.import_start(p['preview_id'],p['input_digest'],str(uuid4()));q=ImportQueue(s._storage);claim=q.claim('synthetic-seed')
 while q.step(claim):pass
 return {'synthetic':True,'library_id':s.identity()['library_id'],'counts':s.counts(),'assets':1,'provider_calls':False}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--allow-write',action='store_true');a=p.parse_args()
 if not a.allow_write:p.error('--allow-write required for synthetic fixture')
 print(json.dumps(seed(a.root),indent=2))

import tempfile
import unittest
from pathlib import Path
from bookmarks.service import BookmarkService
from bookmarks.errors import ValidationError

HTML='''<!DOCTYPE NETSCAPE-Bookmark-file-1><TITLE>Bookmarks</TITLE><DL><p>
<DT><H3>Engineering &amp; Data</H3><DL><p><DT><H3>Backend</H3><DL>
<DT><A HREF="https://example.org/a?keep=1" TAGS="systems,reading" ADD_DATE="10">東京 &amp; API</A><DD>My description
</DL></DL><DT><A HREF="https://example.org/root">Root</A>
<DT><A HREF="javascript:bad">Unsafe</A></DL>'''
class ImportHTMLTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.s=BookmarkService(Path(self.tmp.name))
 def test_nested_entities_dd_and_unsupported_metadata_are_explicit(self):
  from bookmarks.imports.html import parse_bookmarks
  records=parse_bookmarks(HTML)
  self.assertEqual(len(records),3);self.assertEqual(records[0]['collection_path'],['Engineering & Data','Backend'])
  self.assertEqual(records[0]['title'],'東京 & API');self.assertEqual(records[0]['description'],'My description')
  self.assertEqual(records[1]['collection_path'],[])
  p=self.s.import_preview(html=HTML);self.assertEqual((p['total'],p['valid'],p['invalid']),(3,2,1))
  self.assertTrue(p['rows'][0]['warnings']);self.assertEqual(self.s.search()['total'],0)
 def test_tolerates_omitted_dt_a_closers_without_flattening(self):
  from bookmarks.imports.html import parse_bookmarks
  rows=parse_bookmarks('<DL><DT><H3>Folder</H3><DL><DT><A HREF="https://example.org/a">A<DT><A HREF="https://example.org/b">B</DL></DL>')
  self.assertEqual([r['title'] for r in rows],['A','B']);self.assertTrue(all(r['collection_path']==['Folder'] for r in rows))
 def test_rejects_oversize_depth_empty_or_nonbookmark_html(self):
  inputs=['x'*(2*1024*1024+1),'<a href="https://example.org">incidental</a>','<DL></DL>', '<DL>'+''.join('<DT><H3>x</H3><DL>' for _ in range(17))+'<DT><A HREF="https://example.org">x</A>']
  for html in inputs:
   with self.subTest(size=len(html)),self.assertRaises(ValidationError):self.s.import_preview(html=html)
 def test_scripts_icons_and_remote_images_are_not_executed_or_imported(self):
  from bookmarks.imports.html import parse_bookmarks
  rows=parse_bookmarks('<DL><script><A HREF="https://bad.invalid">bad</A></script><DT><A HREF="https://example.org" ICON="data:evil" onclick="bad()">Good</A><img src="https://bad.invalid"></DL>')
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'Good');self.assertNotIn('attachment_ids',rows[0])

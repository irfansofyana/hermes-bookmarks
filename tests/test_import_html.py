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
 def test_rejects_missing_h3_closer_instead_of_losing_title_and_path(self):
  from bookmarks.imports.html import parse_bookmarks
  html='<DL><DT><H3>Folder<DL><DT><A HREF="https://example.org/a">A</A></DL></DL>'
  with self.assertRaises(ValidationError):parse_bookmarks(html)
 def test_folder_dd_never_pollutes_previous_bookmark_description(self):
  from bookmarks.imports.html import parse_bookmarks
  html='''<DL><DT><A HREF="https://example.org/a">A</A><DD>Actual A description
<DT><H3 ADD_DATE="123">Folder</H3><DD>Folder description
<DL><DT><A HREF="https://example.org/b">B</A></DL></DL>'''
  rows=parse_bookmarks(html)
  self.assertEqual([(r['url'],r['title'],r['collection_path'],r.get('description')) for r in rows],[('https://example.org/a','A',[],'Actual A description'),('https://example.org/b','B',['Folder'],None)])
  self.assertTrue(any('html_folder_description_ignored' in r['_html_warnings'] for r in rows))
 def test_unsupported_h3_attributes_are_explicit_without_changing_folder_name(self):
  from bookmarks.imports.html import parse_bookmarks
  rows=parse_bookmarks('<DL><DT><H3 ADD_DATE="123" ICON="data:evil">Folder &amp; Data</H3><DL><DT><A HREF="https://example.org/b">B</A></DL></DL>')
  self.assertEqual([(r['title'],r['collection_path']) for r in rows],[('B',['Folder & Data'])])
  self.assertIn('html_folder_attribute_ignored:add_date',rows[0]['_html_warnings'])
  self.assertIn('html_folder_attribute_ignored:icon',rows[0]['_html_warnings'])
 def test_rejects_other_ambiguous_heading_boundaries(self):
  from bookmarks.imports.html import parse_bookmarks
  for heading in ('<H3>Folder', '<H3>Folder<A HREF="https://example.org/b">B</A></H3>', '<H3>Folder<H3>Other</H3>', '<H3>Folder</H3><DT><A HREF="https://example.org/b">B</A>'):
   with self.subTest(heading=heading),self.assertRaises(ValidationError):
    parse_bookmarks('<DL><DT><A HREF="https://example.org/a">A</A><DT>'+heading+'</DL>')
 def test_folder_dd_before_first_bookmark_is_warned_and_bookmark_dd_is_owned(self):
  from bookmarks.imports.html import parse_bookmarks
  rows=parse_bookmarks('<DL><DT><H3>Folder</H3><DD>Folder only<DL><DT><A HREF="https://example.org/b">B</A><DD>Actual B description</DL><DT><A HREF="https://example.org/c">C</A></DL>')
  self.assertEqual([(r['title'],r['collection_path'],r.get('description')) for r in rows],[('B',['Folder'],'Actual B description'),('C',[],None)])
  self.assertTrue(any('html_folder_description_ignored' in r['_html_warnings'] for r in rows))
 def test_rejects_oversize_depth_empty_or_nonbookmark_html(self):
  inputs=['x'*(2*1024*1024+1),'<a href="https://example.org">incidental</a>','<DL></DL>', '<DL>'+''.join('<DT><H3>x</H3><DL>' for _ in range(17))+'<DT><A HREF="https://example.org">x</A>']
  for html in inputs:
   with self.subTest(size=len(html)),self.assertRaises(ValidationError):self.s.import_preview(html=html)
 def test_scripts_icons_and_remote_images_are_not_executed_or_imported(self):
  from bookmarks.imports.html import parse_bookmarks
  rows=parse_bookmarks('<DL><script><A HREF="https://bad.invalid">bad</A></script><DT><A HREF="https://example.org" ICON="data:evil" onclick="bad()">Good</A><img src="https://bad.invalid"></DL>')
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'Good');self.assertNotIn('attachment_ids',rows[0])

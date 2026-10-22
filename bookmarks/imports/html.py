"""Bounded Netscape bookmark HTML interpretation; never a browser or fetcher."""
from html.parser import HTMLParser
from ..errors import ValidationError
from .records import MAX_BYTES

class BookmarkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[];self.path=[];self.levels=[];self.pending=None;self.folder=None;self.anchor=None;self.description=None;self.ignored=[];self.in_dt=False
        self.dd_owner=None;self.warnings=set()
    def finish_anchor(self):
        if self.anchor is not None:
            self.anchor['title']=self.anchor['title'].strip();self.rows.append(self.anchor);self.dd_owner=self.anchor;self.anchor=None
            if len(self.rows)>500:raise ValidationError()
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):
            self.ignored.append(tag);return
        if self.ignored:return
        # Unlike optional DT/A closers, a heading boundary cannot be inferred
        # without risking loss of both the link title and its collection path.
        if self.folder is not None and tag in ('dt','dl','h3','dd','a'):raise ValidationError()
        if self.pending is not None and tag in ('dt','h3','a'):raise ValidationError()
        if tag in ('dt','dl','h3','dd'):
            self.finish_anchor();self.description=None
        if tag=='dt':self.in_dt=True;self.dd_owner=None
        elif tag=='h3':
            if not self.levels or not self.in_dt:raise ValidationError()
            self.folder='';self.dd_owner='folder'
            self.warnings.update('html_folder_attribute_ignored:'+k for k,_ in attrs)
        elif tag=='dl':
            if len(self.levels)>=17:raise ValidationError()
            added=self.pending is not None
            self.levels.append(added)
            if added:
                self.path.append(self.pending);self.pending=None
                if len(self.path)>16:raise ValidationError()
            self.in_dt=False;self.dd_owner=None
        elif tag=='a' and self.levels and self.in_dt:
            self.finish_anchor();a=dict(attrs)
            self.anchor={'url':a.get('href',''),'title':'','collection_path':list(self.path),'provenance':{'source':'Bookmark HTML','locator':'entry '+str(len(self.rows)+1)}}
            if a.get('tags'):self.anchor['tags']=[t.strip() for t in a['tags'].split(',') if t.strip()]
            unsupported=sorted(k for k,_ in attrs if k not in ('href','tags'))
            self.anchor['_html_warnings']=['html_attribute_ignored:'+k for k in unsupported]+(['html_tags_comma_separated'] if a.get('tags') else [])
            self.in_dt=False
        elif tag=='dd':
            if self.dd_owner=='folder':self.warnings.add('html_folder_description_ignored')
            elif isinstance(self.dd_owner,dict):
                self.description=self.dd_owner;self.description.setdefault('description','')
    def handle_endtag(self,tag):
        if self.ignored:
            if tag==self.ignored[-1]:self.ignored.pop()
            return
        if self.folder is not None and tag in ('dt','dl','dd','a'):raise ValidationError()
        if self.pending is not None and tag=='dl':raise ValidationError()
        if tag=='a':self.finish_anchor()
        elif tag=='h3' and self.folder is not None:self.pending=self.folder.strip();self.folder=None
        elif tag=='dl':
            self.finish_anchor();self.description=None;self.dd_owner=None
            if not self.levels:raise ValidationError()
            if self.levels.pop():self.path.pop()
        elif tag=='dd':self.description=None
    def handle_data(self,data):
        if self.ignored:return
        if self.folder is not None:self.folder+=data
        elif self.anchor is not None:self.anchor['title']+=data
        elif self.description is not None:self.description['description']+=data


def parse_bookmarks(html):
    if not isinstance(html,str):raise ValidationError()
    try:size=len(html.encode('utf-8'))
    except UnicodeError:raise ValidationError() from None
    if size>MAX_BYTES:raise ValidationError()
    parser=BookmarkParser()
    try:parser.feed(html);parser.close();parser.finish_anchor()
    except (ValueError,RecursionError):raise ValidationError() from None
    if not parser.rows or parser.folder is not None or parser.pending is not None:raise ValidationError()
    for row in parser.rows:
        if 'description' in row:row['description']=row['description'].strip()
        # Folder metadata has no record of its own; report document-level loss
        # on returned rows, including when the folder preceded the first link.
        row['_html_warnings'].extend(sorted(parser.warnings))
        if parser.levels:row['_html_warnings'].append('html_unclosed_folder_structure')
    return parser.rows

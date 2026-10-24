"""Validate supplied normalized records, without guessing their extraction completeness."""
import json
from ..errors import ValidationError
from ..items import metadata,require_assets
from ..labels import validate_text,normalize_label
from ..tags import normalize_tags
from ..urls import validate_url

MAX_BYTES=2*1024*1024
FIELDS={'url','title','description','notes','collection_path','tags','attachment_ids','source_id','provenance','imported_summary','source_text'}


def encoded(value):
    try:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError,RecursionError):raise ValidationError() from None


def options(value):
    if value is None:value={}
    if not isinstance(value,dict) or set(value)-{'duplicate_policy','enrich'}:raise ValidationError()
    result={'duplicate_policy':value.get('duplicate_policy','skip_existing'),'enrich':value.get('enrich',False)}
    if result['duplicate_policy']!='skip_existing' or type(result['enrich']) is not bool:raise ValidationError()
    return result


def bounded_records(records):
    if not isinstance(records,list) or not 1<=len(records)<=500:raise ValidationError()
    try:size=len(encoded(records).encode('utf-8'))
    except UnicodeError:raise ValidationError() from None
    if size>MAX_BYTES:raise ValidationError()


def record(connection,value):
    if not isinstance(value,dict):raise ValidationError()
    validate_url(value.get('url'))
    result=metadata({key:value.get(key,default) for key,default in [('title',''),('description',''),('notes',''),('attachment_ids',[])]})
    result['url']=value['url'];require_assets(connection,result['attachment_ids'])
    result['tags']=[label for label,_ in normalize_tags(value.get('tags',[]))]
    path=value.get('collection_path',[])
    if not isinstance(path,list) or len(path)>16:raise ValidationError()
    result['collection_path']=[normalize_label(label,100)[0] for label in path]
    for key,limit in [('source_id',300),('imported_summary',16000),('source_text',30000)]:
        result[key]=value.get(key,'');validate_text(result[key],max_chars=limit)
    provenance=value.get('provenance',{})
    if not isinstance(provenance,dict):raise ValidationError()
    result['provenance']={key:provenance.get(key,'') for key in ('source','locator')}
    for text in result['provenance'].values():validate_text(text,max_chars=300)
    warnings=['unsupported_field:'+key[:100] for key in sorted(set(value)-FIELDS)]
    warnings+=['unsupported_provenance_field:'+key[:100] for key in sorted(set(provenance)-{'source','locator'})]
    return result,warnings

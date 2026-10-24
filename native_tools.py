"""Strict serializable native and HTTP boundary over the shared service."""
import json
import asyncio
import base64
import binascii
import re

if __package__:
    from .bookmarks.errors import BookmarkError, ConflictError, ValidationError
    from .bookmarks.enrichment import _storage_call
    from .runtime import get_service, dispatch, asset_operation, ensure_enrichment, ensure_imports
else:
    from bookmarks.errors import BookmarkError, ConflictError, ValidationError
    from bookmarks.enrichment import _storage_call
    from runtime import get_service, dispatch, asset_operation, ensure_enrichment, ensure_imports


def text(length, *, nullable=False, **kwargs):
    return {'type':['string','null'] if nullable else 'string','maxLength':length,**kwargs}


def object_rule(fields):
    return {'type':'object','properties':fields,'required':[],'additionalProperties':False}


ID=text(100)
COLLECTION=text(100,nullable=True)
ASSET=text(32,pattern='^[a-f0-9]{32}$')
OPERATION=text(36,pattern=r'^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')
TAGS={'type':'array','maxItems':20,'items':text(80)}
ATTACHMENTS={'type':'array','maxItems':10,'items':ASSET,'uniqueItems':True}
REVISION={'type':'integer','minimum':1,'maximum':2**63-1}
PAGING={'limit':{'type':'integer','minimum':1,'maximum':100},'offset':{'type':'integer','minimum':0,'maximum':2**63-1}}
ITEM_CHANGES={'title':text(1000),'description':text(16384),'notes':text(65536),'collection_id':COLLECTION,
    'favorite':{'type':'boolean'},'read_later':{'type':'boolean'},'add_tags':TAGS,'remove_tags':TAGS,'attachment_ids':ATTACHMENTS,'summary':text(16000)}
CAPTURE={key:value for key,value in ITEM_CHANGES.items() if key not in {'add_tags','remove_tags','summary'}}
CAPTURE.update({'kind':{'type':'string','enum':['link','image']},'url':text(8192,nullable=True),
    'tags':TAGS,'primary_asset_id':text(32,nullable=True,pattern='^[a-f0-9]{32}$'),'operation_key':OPERATION})

SETTINGS_CHANGES={'provider':text(300),'model':text(300),'automatic_tags':{'type':'boolean'},
    'automatic_summary':{'type':'boolean'},'image_analysis':{'type':'boolean'},'summary_language':text(80),
    'summary_length':{'type':'string','enum':['short','medium','long']},'preferred_tags':TAGS,
    'guidance':text(2000),'retain_extracted_text':{'type':'boolean'},'paused':{'type':'boolean'}}
GENERATED_FIELDS={'type':'array','maxItems':2,'uniqueItems':True,'items':{'type':'string','enum':['summary','tags']}}

SPECS = {
    'bookmark_attachment_add': ('Store user-provided image bytes as an owned attachment; never reads arbitrary local paths or analyzes it with AI.',
        {'content_base64':text(((10*1024*1024+2)//3)*4),'mime_type':text(50)}, ['content_base64','mime_type']),
    'bookmark_attachment_get': ('Read owned attachment metadata by ID. Returned API reference still requires host authentication.',
        {'asset_id':ASSET}, ['asset_id']),
    'bookmark_save': ('Save a link or owned image with metadata. Eligible saves queue library-configured enrichment; page text or opted-in standalone images may be sent to the library model and incur host retries/charges. Use an operation key to reconcile uncertain writes.',CAPTURE,[]),
    'bookmark_delete': ('Move one item into recoverable trash at its expected revision. Does not delete files.',{'item_id':ID,'expected_revision':REVISION},['item_id','expected_revision']),
    'bookmark_restore': ('Restore one trashed item without triggering inference.',{'item_id':ID,'expected_revision':REVISION},['item_id','expected_revision']),
    'bookmark_get': ('Read full saved detail without fetching a page or calling a model.', {'item_id':ID},['item_id']),
    'bookmark_search': ('Literal search across saved metadata, notes, summaries and tags. All organization predicates combine with AND.',
        {'query':text(2000),**PAGING,'view':{'type':'string','enum':['all','inbox','favorites','read_later','trash']},'collection_id':COLLECTION,'tags':TAGS},[]),
    'bookmark_update': ('Atomically edit saved metadata, notes, tags and image associations at an expected revision. Source is immutable.',
        {'item_id':ID,'expected_revision':REVISION,'changes':object_rule(ITEM_CHANGES)},['item_id','expected_revision','changes']),
    'bookmark_note_update': ('Replace or explicitly append personal Markdown notes at an expected revision. Does not regenerate the AI summary.',
        {'item_id':ID,'expected_revision':REVISION,'text':text(65536),'mode':{'type':'string','enum':['append','replace']}},['item_id','expected_revision','text']),
    'bookmark_capture_status': ('Read an immutable capture receipt and current saved item by operation key; never retries a write.',
        {'operation_key':OPERATION},['operation_key']),
    'bookmark_collection_list': ('Page direct child collections or search the tree with ancestor paths and descendant item counts.',
        {**PAGING,'parent_id':COLLECTION,'query':text(2000)},[]),
    'bookmark_collection_create': ('Create a normalized unique collection, optionally under a parent; depth is limited to 16.',
        {'name':text(100),'parent_id':COLLECTION},['name']),
    'bookmark_collection_update': ('Rename or move a collection at an expected revision; cycles and sibling collisions are rejected.',
        {'collection_id':ID,'expected_revision':REVISION,'changes':object_rule({'name':text(100),'parent_id':COLLECTION})},['collection_id','expected_revision','changes']),
    'bookmark_collection_delete': ('Delete only the named collection; explicitly move items and direct children to its parent or Inbox/root.',
        {'collection_id':ID,'expected_revision':REVISION,'contents_policy':{'type':'string','enum':['move_to_parent','move_to_inbox']}},['collection_id','expected_revision','contents_policy']),
    'bookmark_tag_list': ('Page normalized effective tags with whole-library counts; typing a query does not create tags.',
        {'query':text(2000),**PAGING},[]),
    'bookmark_library_identity': ('Read the configured shared library identity, independent of chat/profile configuration.',{},[]),
    'bookmark_import_preview': ('Stage supplied normalized records or bookmark HTML for review. No source paths, fetching or AI by default. Unknown record fields are reported, not preserved.',
        {'records':{'type':'array','maxItems':500,'items':{'type':'object','properties':{},'additionalProperties':True}},'html':text(2*1024*1024),
         'options':object_rule({'duplicate_policy':{'type':'string','enum':['skip_existing']},'enrich':{'type':'boolean'}})},[]),
    'bookmark_import_start': ('Explicitly start an immutable validated preview. Retry with the same request ID after uncertain acknowledgement.',
        {'preview_id':ID,'input_digest':text(64,pattern='^[a-f0-9]{64}$'),'request_id':OPERATION},['preview_id','input_digest','request_id']),
    'bookmark_import_request_get': ('Read accepted import by request ID without starting or retrying work.',{'request_id':OPERATION},['request_id']),
    'bookmark_job_get': ('Read this plugin import job and exact reconciled progress/results. Does not access chat sessions or enrichment jobs.',{'job_id':ID,**PAGING},['job_id']),
    'bookmark_job_cancel': ('Cancel remaining rows of one import. Already committed records are kept and reported.',{'job_id':ID},['job_id']),
    'bookmark_counts': ('Read whole-library All, Inbox, Favorites and Read later counts.',{},[]),
    'bookmark_export_create': ('Generate an owned HTML export or full content backup. Contains private notes/images; no credentials/chat sessions/queued execution. No model calls.',
        {'format':{'type':'string','enum':['html','bundle']},'include_trash':{'type':'boolean'},'request_id':OPERATION},['request_id']),
    'bookmark_export_get': ('Read export request status without regenerating it. Artifacts expire after 24 hours with lazy cleanup.',{'request_id':OPERATION},['request_id']),
    'bookmark_export_read': ('Read at most 32 KiB of an authenticated library artifact as base64. No server paths; verify full digest before saving.',{'artifact_id':ASSET,'offset':{'type':'integer','minimum':0,'maximum':536870912}},['artifact_id']),
    'bookmark_backup_upload_create': ('Create resumable owned backup staging for explicitly supplied bytes, up to 512 MiB. Does not change library items.',{'size':{'type':'integer','minimum':1,'maximum':536870912},'digest':text(64,pattern='^[a-f0-9]{64}$'),'request_id':OPERATION},['size','digest','request_id']),
    'bookmark_backup_upload_chunk': ('Append at most 32 KiB decoded backup bytes at an exact offset; identical replay is safe. Never reads local paths.',{'upload_id':ASSET,'offset':{'type':'integer','minimum':0,'maximum':536870912},'content_base64':text(43692)},['upload_id','offset','content_base64']),
    'bookmark_backup_preview': ('Validate sealed backup and preview full restore into an empty library only. No item writes or inference.',{'upload_id':ASSET},['upload_id']),
    'bookmark_backup_restore': ('Explicitly restore a validated backup only into an empty library. Atomic commit cannot be undone by closing; no credentials or queued AI replay.',{'preview_id':ASSET,'input_digest':text(64,pattern='^[a-f0-9]{64}$'),'request_id':OPERATION},['preview_id','input_digest','request_id']),
    'bookmark_backup_restore_get': ('Read restore request receipt after uncertain acknowledgement; never starts or retries restoration.',{'request_id':OPERATION},['request_id']),
    'bookmark_settings_get': ('Read nonsecret shared-library AI settings; never starts inference.',{},[]),
    'bookmark_settings_update': ('Update future-job AI settings at an expected settings revision; cannot change owner/credentials. Provider data transfer and host retries may incur charges.',{'expected_revision':REVISION,'changes':object_rule(SETTINGS_CHANGES)},['expected_revision','changes']),
    'bookmark_enrich': ('Deliberately generate selected fields for one reviewed saved item. Replaces requested generated fields, not personal notes/manual tags; image analysis requires library opt-in. May incur provider charges and host retries.',{'item_id':ID,'expected_revision':REVISION,'request_id':OPERATION,'fields':GENERATED_FIELDS},['item_id','expected_revision','request_id','fields']),
    'bookmark_enrichment_request_get': ('Read exact enrichment receipt without replay or activation.',{'request_id':OPERATION},['request_id']),
    'bookmark_enrichment_get': ('Read bounded enrichment status without worker activation or source-body/lease disclosure.',{'job_id':ID},['job_id']),
    'bookmark_enrichment_cancel': ('Cancel application of a pending/running enrichment job. An admitted provider request may continue and incur charges.',{'job_id':ID},['job_id']),
    'bookmark_source_clear': ('Explicitly remove retained extracted article text at expected item revision. Keeps notes/imported sources and does not call a model.',{'item_id':ID,'expected_revision':REVISION},['item_id','expected_revision']),
}


def validate(value, rule):
    kind=rule['type']
    if isinstance(kind,list):
        if value is None and 'null' in kind:
            return
        kind=next((option for option in kind if option!='null'),None)
    types={'string':str,'integer':int,'boolean':bool,'array':list,'object':dict}
    if kind not in types or type(value) is not types[kind]:
        raise ValidationError()
    if 'enum' in rule and value not in rule['enum']:
        raise ValidationError()
    if kind=='string':
        if ('maxLength' in rule and len(value)>rule['maxLength']) or ('pattern' in rule and re.fullmatch(rule['pattern'],value) is None):
            raise ValidationError()
        if '\x00' in value or any('\ud800'<=character<='\udfff' for character in value):
            raise ValidationError()
    elif kind=='integer':
        if not rule.get('minimum',0)<=value<=rule.get('maximum',2**63-1):
            raise ValidationError()
    elif kind=='array':
        if len(value)>rule['maxItems']:
            raise ValidationError()
        for item in value:
            validate(item,rule['items'])
        if rule.get('uniqueItems') and len(set(value))!=len(value):
            raise ValidationError()
    elif kind=='object':
        if (rule.get('additionalProperties',False) is False and set(value)-set(rule['properties'])) or set(rule.get('required',[]))-set(value):
            raise ValidationError()
        for key,item in value.items():
            if key in rule['properties']:validate(item,rule['properties'][key])


def execute(name, params, service_factory=get_service):
    try:
        if not isinstance(name,str) or name not in SPECS:
            raise ValidationError()
        fields,required=SPECS[name][1:]
        validate(params,{'type':'object','properties':fields,'required':required,'additionalProperties':False})
        if name == 'bookmark_attachment_add':
            try: content=base64.b64decode(params['content_base64'],validate=True)
            except (ValueError,binascii.Error): raise ValidationError() from None
            return asset_operation('store_image',content,params['mime_type'])
        if name == 'bookmark_attachment_get':
            payload=asset_operation('get_asset',params['asset_id'])
            if payload['ok']: payload['result']['access_ref']='/api/plugins/hermes-bookmarks/assets/'+params['asset_id']
            return payload
        service=service_factory()
        if name == 'bookmark_save':
            saved=service.capture(**params)
            payload={'ok':True,'result':saved['item']}
            if saved['receipt'] is not None:
                payload['receipt']=saved['receipt']
            return payload
        operations={
            'bookmark_settings_get':service.settings_get,'bookmark_settings_update':service.settings_update,
            'bookmark_enrich':service.enrich,'bookmark_enrichment_request_get':service.enrichment_request_get,
            'bookmark_enrichment_get':service.enrichment_get,'bookmark_enrichment_cancel':service.enrichment_cancel,
            'bookmark_source_clear':service.source_clear,
            'bookmark_export_create':service.export_create,'bookmark_export_get':service.export_get,'bookmark_export_read':service.export_read,
            'bookmark_backup_upload_create':service.backup_upload_create,'bookmark_backup_upload_chunk':service.backup_upload_chunk,
            'bookmark_backup_preview':service.backup_preview,'bookmark_backup_restore':service.backup_restore,'bookmark_backup_restore_get':service.backup_restore_get,
            'bookmark_get':service.get, 'bookmark_delete':service.trash, 'bookmark_restore':service.restore, 'bookmark_search':service.search,
            'bookmark_update':service.update, 'bookmark_note_update':service.note_update,
            'bookmark_capture_status':service.capture_status,
            'bookmark_collection_list':service.collection_list, 'bookmark_collection_create':service.collection_create,
            'bookmark_collection_update':service.collection_update, 'bookmark_collection_delete':service.collection_delete,
            'bookmark_import_preview':service.import_preview,'bookmark_import_start':service.import_start,
            'bookmark_import_request_get':service.import_request_get,'bookmark_job_get':service.import_job_get,'bookmark_job_cancel':service.import_job_cancel,
            'bookmark_tag_list':service.tag_list, 'bookmark_library_identity':service.identity, 'bookmark_counts':service.counts,
        }
        return {'ok':True,'result':operations[name](**params)}
    except BookmarkError as exc:
        error={'code':exc.code,'message':exc.message}
        if isinstance(exc,ConflictError) and type(exc.current_revision) is int and 1<=exc.current_revision<=2**63-1:
            error['current_revision']=exc.current_revision
        return {'ok':False,'error':error}


def _dispatch_import(name, params):
    result=dispatch(name,params)
    enrich=False
    if result['ok']:
        # Admission snapshots a route only for explicit opt-in. Read that
        # durable plugin-owned fact, not caller flags or process-local preview
        # state: retries/request lookup must also work after cold registration.
        # Keep SQLite off the host loop and settings out of the public receipt.
        with get_service()._storage._transaction() as connection:
            row=connection.execute('SELECT settings IS NOT NULL AS enrich FROM import_jobs WHERE id=?',
                                   (result['result']['id'],)).fetchone()
            enrich=row is not None and bool(row['enrich'])
    return result,enrich


def register_tools(ctx):
    for name,(description,fields,required) in SPECS.items():
        async def handler(params,_name=name,**kwargs):
            if _name=='bookmark_import_start':
                result,enrich=await _storage_call(_dispatch_import,_name,params)
                if result['ok']:
                    ensure_imports()
                    if enrich:ensure_enrichment()
            else:
                result=await _storage_call(dispatch,_name,params)
                if result['ok'] and _name in {'bookmark_save','bookmark_settings_update','bookmark_enrich'}:
                    ensure_enrichment()
            return json.dumps(result,ensure_ascii=False)
        ctx.register_tool(name=name,toolset='hermes_bookmarks',
            schema={'name':name,'description':description,'parameters':{
                'type':'object','properties':fields,'required':required,'additionalProperties':False}},
            handler=handler,is_async=True)

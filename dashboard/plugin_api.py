"""Host-authenticated routes; path-loaded module uses explicit plugin bridge.

Direct-router tests do not prove the host's authentication middleware. A cold
API without native plugin registration returns an actionable configuration error.
"""
import sys
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

async def activate_worker():
    bridge=sys.modules.get(BRIDGE_NAME)
    if bridge is not None: bridge.ensure_enrichment()


router = APIRouter(dependencies=[Depends(activate_worker)])
BRIDGE_NAME = 'hermes_bookmarks_runtime_bridge'


def invoke(name, params):
    bridge = sys.modules.get(BRIDGE_NAME)
    if bridge is None:
        payload = {'ok': False, 'error': {'code': 'configuration_error', 'message': 'Enable the native plugin and configure its shared library root.'}}
    else:
        payload = bridge.dispatch(name, params)
    code = payload.get('error', {}).get('code')
    status = 200 if payload['ok'] else {'conflict': 409, 'not_found': 404, 'configuration_error': 503, 'storage_error': 503}.get(code, 400)
    return JSONResponse(payload, status_code=status)


@router.get('/health')
def get_health():
    bridge=sys.modules.get(BRIDGE_NAME)
    status=bridge.get_status() if bridge is not None else {'library_configured':False,'library_ready':False,'enrichment_startups':[]}
    return {'ok': True, 'plugin': 'hermes-bookmarks', 'stage': 'foundation_preview', **status}


def invalid_request(status=400, message='Arguments must have valid types and values; limit is 1–100 and offset is nonnegative.'):
    return JSONResponse({'ok':False,'error':{'code':'invalid_argument','message':message}},status_code=status)


def query_arguments(request, allowed, *, repeated_tags=False):
    params = {}
    for key,value in request.query_params.multi_items():
        if key not in allowed:
            raise ValueError()
        if key=='tag' and repeated_tags:
            params.setdefault('tags',[]).append(value)
        elif key in params:
            raise ValueError()
        else:
            params[key]=value
    for key in ('limit','offset'):
        if key in params:
            value=params[key]
            if not value.isascii() or not value.isdecimal() or len(value)>19 or int(value)>2**63-1:
                raise ValueError()
            params[key]=int(value)
    return params


def query_response(request, name, allowed=(), *, repeated_tags=False, identity=None):
    try:
        params=query_arguments(request,allowed,repeated_tags=repeated_tags)
    except ValueError:
        return invalid_request()
    return invoke(name,{**params,**(identity or {})})


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key]=value
    return result


def invalid_constant(value):
    raise ValueError('Nonfinite JSON constant')


async def metadata_request(request, name, identity=None):
    # Actual streamed byte bound; Content-Length is never an authority.
    if request.query_params:
        return invalid_request()
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>128*1024:
            return invalid_request(413,'Request exceeds 128 KiB.')
        data.extend(chunk)
    import json
    try:
        body=json.loads(data,object_pairs_hook=unique_object,parse_constant=invalid_constant)
    except (ValueError,UnicodeDecodeError,RecursionError):
        return invalid_request()
    if not isinstance(body,dict) or (identity and set(identity)&set(body)):
        return invalid_request()
    return await run_in_threadpool(invoke,name,{**body,**(identity or {})})


@router.get('/library/identity')
def library_identity(request: Request):
    return query_response(request,'bookmark_library_identity')


@router.get('/counts')
def library_counts(request: Request):
    return query_response(request,'bookmark_counts')


@router.get('/items')
def search_items(request: Request):
    return query_response(request,'bookmark_search',{'query','limit','offset','view','collection_id','tag'},repeated_tags=True)


@router.get('/items/{item_id}')
def get_item(item_id: str, request: Request):
    return query_response(request,'bookmark_get',identity={'item_id':item_id})


@router.post('/items')
async def save_item(request: Request):
    return await metadata_request(request,'bookmark_save')


@router.post('/items/{item_id}/update')
async def update_item(item_id: str, request: Request):
    return await metadata_request(request,'bookmark_update',{'item_id':item_id})


@router.post('/items/{item_id}/notes')
async def update_notes(item_id: str, request: Request):
    return await metadata_request(request,'bookmark_note_update',{'item_id':item_id})


@router.get('/captures/{operation_key}')
def capture_status(operation_key: str, request: Request):
    return query_response(request,'bookmark_capture_status',identity={'operation_key':operation_key})


@router.get('/collections')
def collection_list(request: Request):
    return query_response(request,'bookmark_collection_list',{'limit','offset','parent_id','query'})


@router.post('/collections')
async def collection_create(request: Request):
    return await metadata_request(request,'bookmark_collection_create')


@router.post('/collections/{collection_id}/update')
async def collection_update(collection_id: str, request: Request):
    return await metadata_request(request,'bookmark_collection_update',{'collection_id':collection_id})


@router.post('/collections/{collection_id}/delete')
async def collection_delete(collection_id: str, request: Request):
    return await metadata_request(request,'bookmark_collection_delete',{'collection_id':collection_id})


@router.get('/tags')
def tag_list(request: Request):
    return query_response(request,'bookmark_tag_list',{'query','limit','offset'})


def asset_call(operation, *args):
    bridge = sys.modules.get(BRIDGE_NAME)
    if bridge is None:
        return {'ok': False, 'error': {'code': 'configuration_error', 'message': 'Native plugin registration is unavailable.'}}
    return bridge.asset_operation(operation, *args)


def asset_response(payload):
    code = payload.get('error', {}).get('code')
    return JSONResponse(payload, status_code=200 if payload['ok'] else {'not_found':404,'configuration_error':503,'storage_error':503}.get(code,400))


def chat_response(operation, params=None):
    bridge = sys.modules.get(BRIDGE_NAME)
    payload = bridge.chat_operation(operation, params) if bridge else {'ok': False, 'error': {'code': 'configuration_error', 'message': 'Enable the native plugin and configure its shared library root.'}}
    return asset_response(payload)


@router.get('/chat/identity')
def chat_identity():
    return chat_response('identity')


@router.get('/chat/threads')
def chat_threads(request: Request):
    return chat_response('threads', dict(request.query_params))


@router.post('/chat/threads')
async def bind_chat_thread(request: Request):
    import json
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 16384:
            return JSONResponse({'ok': False, 'error': {'code': 'invalid_argument', 'message': 'Request exceeds 16 KiB.'}}, status_code=413)
    try:
        body = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        body = None
    return await run_in_threadpool(chat_response, 'bind', body)


@router.post('/assets/base64')
async def upload_asset_json(request: Request):
    import json
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>14*1024*1024+65536:
            return JSONResponse({'ok':False,'error':{'code':'invalid_argument','message':'Upload exceeds limit.'}},status_code=413)
    try: body=json.loads(data)
    except (ValueError,UnicodeDecodeError): body=None
    return await run_in_threadpool(invoke,'bookmark_attachment_add',body)


@router.post('/assets')
async def upload_asset(request: Request):
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>10*1024*1024+65536:
            return JSONResponse({'ok':False,'error':{'code':'invalid_argument','message':'Upload exceeds limit.'}},status_code=413)
    mime=request.headers.get('content-type','').split(';')[0].strip().lower()
    content=bytes(data)
    if mime=='multipart/form-data':
        async def receive(): return {'type':'http.request','body':bytes(data),'more_body':False}
        replay=Request(request.scope,receive)
        try:
            async with replay.form(max_files=1,max_fields=0) as form:
                if len(form)!=1: raise ValueError('One file required')
                upload=form.get('file')
                if upload is None or not hasattr(upload,'read'): raise ValueError('File required')
                content=await upload.read(10*1024*1024+1)
                mime=upload.content_type
        except (ValueError,TypeError):
            return asset_response({'ok':False,'error':{'code':'invalid_argument','message':'Invalid image upload.'}})
    payload=await run_in_threadpool(asset_call,'store_image',content,mime)
    return asset_response(payload)


@router.get('/assets/{asset_id}/preview')
def preview_asset(asset_id: str):
    return asset_response(asset_call('preview',asset_id))


@router.get('/assets/{asset_id}')
def read_asset(asset_id: str):
    from fastapi.responses import Response
    payload=asset_call('read_asset',asset_id)
    if not payload['ok']: return asset_response(payload)
    content,mime=payload['result']
    return Response(content,media_type=mime,headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})

"""Host-authenticated routes; path-loaded module uses explicit plugin bridge.

Direct-router tests do not prove the host's authentication middleware. A cold
API without native plugin registration returns an actionable configuration error.
"""
import sys
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

router = APIRouter()
BRIDGE_NAME = 'hermes_bookmarks_runtime_bridge'


def invoke(name, params):
    bridge = sys.modules.get(BRIDGE_NAME)
    if bridge is None:
        payload = {'ok': False, 'error': {'code': 'configuration_error', 'message': 'Enable the native plugin and configure its shared library root.'}}
    else:
        payload = bridge.dispatch(name, params)
    code = payload.get('error', {}).get('code')
    status = 200 if payload['ok'] else {'not_found': 404, 'configuration_error': 503, 'storage_error': 503}.get(code, 400)
    return JSONResponse(payload, status_code=status)


@router.get('/health')
def get_health():
    return {'ok': True, 'plugin': 'hermes-bookmarks', 'stage': 'foundation_preview', 'library_ready': False}


@router.get('/items')
def search_items(request: Request):
    params = dict(request.query_params)
    for key in ('limit', 'offset'):
        if key in params:
            value = params[key]
            if not value.isascii() or not value.isdecimal() or len(value) > 18:
                return JSONResponse({'ok': False, 'error': {'code': 'invalid_argument', 'message': 'Pagination requires bounded decimal integers.'}}, status_code=400)
            params[key] = int(value)
    return invoke('bookmark_search', params)


@router.get('/items/{item_id}')
def get_item(item_id: str):
    return invoke('bookmark_get', {'item_id': item_id})


@router.post('/items')
async def save_item(request: Request):
    # Bound before decoding; Content-Length is untrusted and not sufficient.
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 16384:
            return JSONResponse({'ok': False, 'error': {'code': 'invalid_argument', 'message': 'Request exceeds 16 KiB.'}}, status_code=413)
    import json
    try:
        body = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        body = None
    return await run_in_threadpool(invoke, 'bookmark_save', body)

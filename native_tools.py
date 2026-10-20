"""Strict serializable native and HTTP boundary over the shared service."""
import json
import base64
import binascii

if __package__:
    from .bookmarks.errors import BookmarkError, ValidationError
    from .runtime import get_service, dispatch, asset_operation
else:
    from bookmarks.errors import BookmarkError, ValidationError
    from runtime import get_service, dispatch, asset_operation

SPECS = {
    'bookmark_attachment_add': ('Store user-provided image bytes as an owned attachment; never reads arbitrary local paths or analyzes it with AI.',
       {'content_base64':{'type':'string','maxLength':((10*1024*1024+2)//3)*4},'mime_type':{'type':'string','maxLength':50}}, ['content_base64','mime_type']),
    'bookmark_attachment_get': ('Read owned attachment metadata by ID. Returned API reference still requires host authentication.',
       {'asset_id':{'type':'string','maxLength':32}}, ['asset_id']),
    'bookmark_save': ('Save a URL in the shared bookmark library and queue configured AI enrichment. Page text may be sent to the library model and incur provider charges. Processing status is returned separately.',
                      {'url': {'type': 'string', 'maxLength': 8192}, 'title': {'type': 'string', 'maxLength': 1000}}, ['url']),
    'bookmark_get': ('Read a saved bookmark by ID. Does not fetch the page or call a model.',
                     {'item_id': {'type': 'string', 'maxLength': 100}}, ['item_id']),
    'bookmark_search': ('Search saved titles and URLs. Empty query lists bookmarks, with pagination.',
                        {'query': {'type': 'string', 'maxLength': 2000},
                         'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100},
                         'offset': {'type': 'integer', 'minimum': 0}}, []),
}


def execute(name, params, service_factory=get_service):
    try:
        if name not in SPECS or not isinstance(params, dict):
            raise ValidationError()
        fields, required = SPECS[name][1:]
        if set(params) - set(fields) or set(required) - set(params):
            raise ValidationError()
        for key, value in params.items():
            rule = fields[key]
            kind = str if rule['type'] == 'string' else int
            if type(value) is not kind:
                raise ValidationError()
            if kind is str and len(value) > rule['maxLength']:
                raise ValidationError()
            if kind is int and (value < rule.get('minimum', 0) or value > rule.get('maximum', 2**63 - 1)):
                raise ValidationError()
        if name == 'bookmark_attachment_add':
            try: content = base64.b64decode(params['content_base64'], validate=True)
            except (ValueError,binascii.Error): raise ValidationError() from None
            return asset_operation('store_image',content,params['mime_type'])
        if name == 'bookmark_attachment_get':
            payload = asset_operation('get_asset',params['asset_id'])
            if payload['ok']: payload['result']['access_ref'] = '/api/plugins/hermes-bookmarks/assets/' + params['asset_id']
            return payload
        service = service_factory()
        if name == 'bookmark_save':
            result = service.save_link(**params)
        elif name == 'bookmark_get':
            result = service.get(**params)
        else:
            result = service.search(**{'query': '', **params})
        return {'ok': True, 'result': result}
    except BookmarkError as exc:
        return {'ok': False, 'error': {'code': exc.code, 'message': exc.message}}


def register_tools(ctx):
    for name, (description, fields, required) in SPECS.items():
        def handler(params, _name=name, **kwargs):
            return json.dumps(dispatch(_name, params), ensure_ascii=False)
        ctx.register_tool(name=name, toolset='hermes_bookmarks',
                          schema={'name': name, 'description': description, 'parameters': {
                              'type': 'object', 'properties': fields, 'required': required, 'additionalProperties': False}},
                          handler=handler)

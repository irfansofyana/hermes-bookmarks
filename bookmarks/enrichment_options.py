"""Validated immutable execution options; no I/O or current-profile defaults."""
import copy
from .errors import ValidationError
from .settings import DEFAULTS, ROUTE_FIELDS, OPTION_FIELDS, validate_settings
from .labels import validate_text


def fields_list(value):
    if type(value) is not list or not value or any(type(v) is not str or v not in {'summary','tags'} for v in value) or len(set(value))!=len(value):
        raise ValidationError()
    return [v for v in ('summary','tags') if v in value]


def normalize_snapshot(value):
    if type(value) is not dict: raise ValidationError()
    if 'version' not in value:
        if set(value)-ROUTE_FIELDS: raise ValidationError()
        full=validate_settings({**copy.deepcopy(DEFAULTS),**value})
        return {'version':1,'settings_revision':None,'route':{k:full[k] for k in ROUTE_FIELDS},
            'options':{k:copy.deepcopy(full[k]) for k in OPTION_FIELDS},'fields':['summary','tags'],
            'primary_asset_id':None,'summary_revision':0}
    required={'version','settings_revision','route','options','fields','primary_asset_id','summary_revision'}
    if set(value)!=required or type(value['version']) is not int or value['version']!=2: raise ValidationError()
    if type(value['settings_revision']) is not int or not 1<=value['settings_revision']<=2**63-1: raise ValidationError()
    if type(value['route']) is not dict or set(value['route'])!=ROUTE_FIELDS: raise ValidationError()
    if type(value['options']) is not dict or set(value['options'])!=OPTION_FIELDS: raise ValidationError()
    validate_settings({**copy.deepcopy(DEFAULTS),**value['route'],**value['options']})
    fields=fields_list(value['fields'])
    if type(value['summary_revision']) is not int or not 0<=value['summary_revision']<=2**63-1: raise ValidationError()
    asset=value['primary_asset_id']
    if asset is not None:
        import re
        if type(asset) is not str or not re.fullmatch('[a-f0-9]{32}',asset): raise ValidationError()
    return {**copy.deepcopy(value),'fields':fields}

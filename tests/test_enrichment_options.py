import unittest
from bookmarks.enrichment_options import normalize_snapshot,fields_list
from bookmarks.errors import ValidationError
from bookmarks.settings import DEFAULTS,OPTION_FIELDS,ROUTE_FIELDS
from bookmarks.enrichment_input import schema_for

class OptionTests(unittest.TestCase):
    def snapshot(self):
        return {'version':2,'settings_revision':1,'route':{k:DEFAULTS[k] for k in ROUTE_FIELDS},'options':{k:DEFAULTS[k] for k in OPTION_FIELDS},'fields':['summary'],'primary_asset_id':None,'summary_revision':0}
    def test_snapshot_rejects_unknown_fields_and_invalid_nested_values(self):
        for change in ({'token':'secret'},{'version':True},{'settings_revision':0},{'fields':[]},{'summary_revision':-1},{'primary_asset_id':'../x'}):
            with self.subTest(change=change),self.assertRaises(ValidationError):normalize_snapshot({**self.snapshot(),**change})
        snap=self.snapshot();snap['options']={**snap['options'],'image_analysis':1}
        with self.assertRaises(ValidationError):normalize_snapshot(snap)
    def test_requested_schema_has_only_requested_fields(self):
        self.assertEqual(set(schema_for(['tags'])['properties']),{'tags'})
        self.assertEqual(schema_for(['summary'])['required'],['summary'])
        self.assertFalse(schema_for(['summary'])['additionalProperties'])
    def test_legacy_snapshots_do_not_inherit_current_route(self):
        snap=normalize_snapshot({'provider':'old','model':'legacy'})
        self.assertEqual(snap['route']['model'],'legacy');self.assertIsNone(snap['settings_revision'])
        self.assertFalse(snap['options']['retain_extracted_text'])
        self.assertEqual(snap['fields'],['summary','tags'])

if __name__=='__main__':unittest.main()

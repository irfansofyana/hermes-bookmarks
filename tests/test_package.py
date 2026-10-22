"""Package/HTTP tests; the direct router harness does NOT prove host auth."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.IsolatedAsyncioTestCase):
    def test_manifests_match_the_preview_package(self):
        import yaml
        native = yaml.safe_load((ROOT / 'plugin.yaml').read_text())
        dashboard = json.loads((ROOT / 'dashboard/manifest.json').read_text())
        self.assertEqual(native['name'], dashboard['name'])
        self.assertEqual(native['version'], dashboard['version'])
        self.assertEqual(native['provides_tools'], ['bookmark_attachment_add', 'bookmark_attachment_get', 'bookmark_save', 'bookmark_delete', 'bookmark_restore', 'bookmark_get', 'bookmark_search',
            'bookmark_update', 'bookmark_note_update', 'bookmark_capture_status', 'bookmark_collection_list',
            'bookmark_collection_create', 'bookmark_collection_update', 'bookmark_collection_delete', 'bookmark_tag_list',
            'bookmark_library_identity', 'bookmark_counts'])
        self.assertEqual(native['provides_hooks'], [])
        self.assertNotIn('requires_hermes', native)
        self.assertTrue((ROOT / 'dashboard' / dashboard['entry']).is_file())
        self.assertTrue((ROOT / 'dashboard' / dashboard['api']).is_file())

    def test_native_registration_delegates_to_read_only_status_command(self):
        spec = importlib.util.spec_from_file_location(
            'bookmarks_foundation_test', ROOT / '__init__.py',
            submodule_search_locations=[str(ROOT)],
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in list(sys.modules) if n == spec.name or n.startswith(spec.name + '.')])
        spec.loader.exec_module(module)
        commands = []
        tools, cleanups = [], []
        context = SimpleNamespace(register_command=lambda **kwargs: commands.append(kwargs),
                                  register_tool=lambda **kw: tools.append(kw),
                                  get_config=lambda key, default=None: default, on_unload=cleanups.append)
        self.addCleanup(lambda: [f() for f in reversed(cleanups)])
        module.register(context)
        self.assertEqual([t['name'] for t in tools], ['bookmark_attachment_add', 'bookmark_attachment_get', 'bookmark_save', 'bookmark_delete', 'bookmark_restore', 'bookmark_get', 'bookmark_search',
            'bookmark_update', 'bookmark_note_update', 'bookmark_capture_status', 'bookmark_collection_list',
            'bookmark_collection_create', 'bookmark_collection_update', 'bookmark_collection_delete', 'bookmark_tag_list',
            'bookmark_library_identity', 'bookmark_counts'])
        self.assertEqual([c['name'] for c in commands], ['bookmarks-status'])
        payload = json.loads(commands[0]['handler']('', unused_host_keyword=True))
        self.assertEqual(payload['stage'], 'foundation_preview')
        self.assertEqual(payload['plugin'], 'hermes-bookmarks')
        self.assertIs(payload['library_ready'], False)

    async def test_path_loaded_health_is_read_only_foundation_preview(self):
        spec = importlib.util.spec_from_file_location(
            'isolated_dashboard_api_test', ROOT / 'dashboard/plugin_api.py',
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router, prefix='/api/plugins/hermes-bookmarks')
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://synthetic.invalid') as client:
            response = await client.get('/api/plugins/hermes-bookmarks/health')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                'ok': True, 'plugin': 'hermes-bookmarks',
                'stage': 'foundation_preview', 'library_ready': False, 'library_configured': False, 'enrichment_startups': [],
            })
            for method in ('post', 'put', 'patch', 'delete'):
                with self.subTest(method=method):
                    result = await getattr(client, method)('/api/plugins/hermes-bookmarks/health')
                    self.assertEqual(result.status_code, 405)
        self.assertIn(('/items', {'GET'}), [(r.path, r.methods) for r in module.router.routes])

import importlib.util
from pathlib import Path
import unittest


class WorkspaceSmokeSafetyTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('library_workspace_smoke',Path(__file__).parents[1]/'scripts/library_workspace_smoke.py')
        assert spec is not None and spec.loader is not None
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_origin_validation_happens_before_any_network_or_write(self):
        module=self.module()
        for origin in ('file:///etc/passwd','http://user:password@127.0.0.1','http://127.0.0.1/path','http://127.0.0.1?token=x','https://example.org'):
            with self.subTest(origin=origin),self.assertRaises(ValueError):
                module.run_smoke(origin,'synthetic',allow_write=True)

    def test_invalid_readback_identity_is_rejected_before_request(self):
        with self.assertRaises(ValueError):
            self.module().run_smoke('http://127.0.0.1:1','synthetic',operation_key='../bad')


if __name__=='__main__':unittest.main()

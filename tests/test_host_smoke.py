"""Unit tests of smoke-check failure handling; fixture is not a Hermes host."""
import importlib
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


class SmokeTests(unittest.TestCase):
    def test_unavailable_host_fails_without_successful_feature_claims(self):
        smoke=importlib.import_module('scripts.host_smoke')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0)); listener.listen(1)
            result=smoke.run_smoke('http://127.0.0.1:'+str(listener.getsockname()[1]),'synthetic-token',timeout=0.05)
        self.assertFalse(result['ok'])
        self.assertEqual(result['checks'][0]['name'],'backend_status')
        self.assertFalse(result['checks'][0]['ok'])

    def test_read_only_checks_auth_gate_and_never_posts(self):
        smoke=importlib.import_module('scripts.host_smoke')
        requests=[]
        class Fixture(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                requests.append(('GET',self.path))
                authorized=self.path=='/api/status' or self.headers.get('X-Hermes-Session-Token')=='synthetic-token'
                body={'version':'synthetic-fixture'} if self.path=='/api/status' else {'ok':True,'result':{'items':[],'total':0}}
                data=json.dumps(body).encode()
                self.send_response(200 if authorized else 401)
                self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(data)
            def do_POST(self): requests.append(('POST',self.path)); self.send_error(500)
        server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        thread=threading.Thread(target=server.serve_forever); thread.start()
        try:
            result=smoke.run_smoke('http://127.0.0.1:'+str(server.server_port),'synthetic-token')
            self.assertTrue(result['ok'],result)
            self.assertTrue(all(method=='GET' for method,_ in requests))
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_remote_or_credential_url_requires_explicit_scope(self):
        smoke=importlib.import_module('scripts.host_smoke')
        for url in ['https://example.org','http://name:password@127.0.0.1']:
            with self.subTest(url=url):
                with self.assertRaises(ValueError): smoke.run_smoke(url,'synthetic-token')

import unittest
from host_bindings import describe_capabilities

class CapabilityTests(unittest.TestCase):
    def test_unknown_host_fails_closed(self):
        caps = describe_capabilities()
        self.assertIs(caps.get('custom_chat'), False)
        self.assertIn('native_chat_handoff', caps)
        self.assertTrue(all(type(v) is bool for v in caps.values()))
        self.assertFalse(any(caps.values()))

    def test_desktop_requires_mounted_complete_public_handles(self):
        from types import SimpleNamespace as NS
        no_action = lambda *args, **kwargs: self.fail('probe performed an action')
        atom = NS(get=no_action)
        host = NS(
            navigate=no_action, openSession=no_action,
            state=NS(focusedStoredSessionId=atom, focusedSessionOwner=atom),
            composer=NS(getDraft=no_action, insertText=no_action),
        )
        caps = describe_capabilities(host='desktop', renderer=NS(host=host), mounted=True)
        self.assertIs(caps['native_navigation'], True)
        self.assertIs(caps['native_chat_handoff'], True)
        self.assertIs(caps['custom_chat'], False)
        self.assertIs(caps['native_chat_embedding'], False)
        for missing in ('getDraft', 'insertText'):
            composer = NS(getDraft=no_action, insertText=no_action)
            delattr(composer, missing)
            incomplete = NS(**{**vars(host), 'composer': composer})
            with self.subTest(missing=missing):
                self.assertIs(describe_capabilities(host='desktop', renderer=NS(host=incomplete), mounted=True)['native_chat_handoff'], False)
        for kwargs in (
            {'host': 'desktop', 'renderer': NS(host=host)},
            {'host': 'unknown', 'renderer': NS(host=host), 'mounted': True},
            {'host': 'desktop', 'mounted': True},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(any(describe_capabilities(**kwargs).values()))

    def test_transport_and_backend_facades_are_probed_without_executing(self):
        from types import SimpleNamespace as NS
        no_action = lambda *args, **kwargs: self.fail('probe performed an action')
        sdk = NS(fetchJSON=no_action, authedFetch=no_action)
        caps = describe_capabilities(host='dashboard', renderer=sdk, mounted=True)
        self.assertIs(caps['json_transport_surface'], True)
        self.assertIs(caps['binary_transport_surface'], True)
        self.assertIs(caps['native_chat_handoff'], False)
        self.assertIs(caps['native_attachments'], False)
        self.assertIs(caps['shared_storage'], False)
        self.assertFalse(any(describe_capabilities(host='dashboard', renderer=sdk).values()))
        del sdk.authedFetch
        self.assertIs(describe_capabilities(host='dashboard', renderer=sdk, mounted=True)['binary_transport_surface'], False)
        context = NS(llm=NS(complete=no_action, complete_structured=no_action),
                     on_unload=no_action, spawn_task=no_action, register_auxiliary_task=no_action)
        caps = describe_capabilities(host='backend', context=context)
        for key in ('llm_completion_surface', 'llm_vision_input_surface', 'cleanup_surface',
                    'supervised_task_surface', 'auxiliary_task_surface'):
            self.assertIs(caps[key], True, key)
        self.assertIs(caps['native_chat_handoff'], False)
        del context.llm.complete_structured
        self.assertIs(describe_capabilities(host='backend', context=context)['llm_vision_input_surface'], False)
        self.assertFalse(any(describe_capabilities(host='unknown', context=context).values()))
        self.assertTrue(all(type(v) is bool for v in caps.values()))

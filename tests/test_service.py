"""Real SQLite service contracts; TemporaryDirectory honors configured TMPDIR."""
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from bookmarks.errors import BookmarkError, ConfigurationError, NotFoundError, ValidationError
from bookmarks.service import BookmarkService


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bookmarks-service-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_two_instances_share_saved_item(self):
        a = BookmarkService(self.root)
        b = BookmarkService(self.root)
        first = a.save_link("https://example.org/a?version=1", "First")
        second = b.save_link("https://example.org/a?version=1", "Replacement")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(b.get(first["id"])["title"], "First")
        self.assertEqual(b.search("First")["total"], 1)
        self.assertEqual(second, first)

    def test_saved_item_survives_reopening_with_revision_and_honest_status(self):
        first = BookmarkService(self.root).save_link("https://example.org/reopen", "Saved")
        self.assertEqual(str(UUID(first["id"])), first["id"])
        self.assertEqual(first["revision"], 1)
        self.assertEqual(first["enrichment_status"], "not_started")
        self.assertEqual(BookmarkService(self.root).get(first["id"]), first)

    def test_default_title_and_duplicate_do_not_claim_a_new_revision(self):
        service = BookmarkService(self.root)
        first = service.save_link("https://example.org/no-title")
        duplicate = service.save_link(first["url"], "Do not replace")
        self.assertEqual(first["title"], "")
        self.assertEqual(duplicate, first)
        self.assertEqual(service.search("")["total"], 1)

    def test_distinct_explicit_roots_are_independent(self):
        first = BookmarkService(self.root / "one")
        second = BookmarkService(self.root / "two")
        item = first.save_link("https://example.org/one", "Only one")
        self.assertEqual(first.search("")["items"], [item])
        self.assertEqual(second.search(""), {"items": [], "total": 0, "limit": 50, "offset": 0})

    def test_empty_query_lists_in_insertion_order_with_exact_pagination_metadata(self):
        service = BookmarkService(self.root)
        items = [service.save_link(f"https://example.org/{i}", "Common") for i in range(4)]
        self.assertEqual(service.search("", limit=2, offset=1), {
            "items": items[1:3], "total": 4, "limit": 2, "offset": 1,
        })
        self.assertEqual(service.search("   ")["items"], items)
        self.assertEqual(service.search("missing"), {
            "items": [], "total": 0, "limit": 50, "offset": 0,
        })

    def test_search_reads_unicode_title_and_url_without_modifying_items(self):
        service = BookmarkService(self.root)
        item = service.save_link("https://example.org/needletoken", "Café 東京 — naïve")
        self.assertEqual(service.search("東京")["items"], [item])
        self.assertEqual(service.search("needletoken")["items"], [item])
        self.assertEqual(service.get(item["id"]), item)

    def test_missing_item_has_typed_safe_error(self):
        service = BookmarkService(self.root)
        with self.assertRaises(NotFoundError) as caught:
            service.get("unknown-secret-item")
        self.assertIsInstance(caught.exception, BookmarkError)
        self.assertEqual(caught.exception.code, "not_found")
        self.assertTrue(caught.exception.message)
        self.assertEqual(str(caught.exception), caught.exception.message)
        self.assertNotIn("unknown-secret-item", caught.exception.message)

    def test_unresolved_or_relative_root_is_a_configuration_error(self):
        for root in (None, "", str(self.root), Path("relative-library")):
            with self.subTest(root=root), self.assertRaises(ConfigurationError) as caught:
                BookmarkService(root)
            self.assertEqual(caught.exception.code, "configuration_error")

    def test_exact_url_identity_preserves_query_fragment_case_and_encoding(self):
        service = BookmarkService(self.root)
        urls = (
            "https://example.org/a?version=1#part",
            "https://example.org/a?version=2#part",
            "https://example.org/a?version=1#other",
            "https://example.org/a?b=2&a=1",
            "https://example.org/a?a=1&b=2",
            "https://EXAMPLE.org/a?version=1#part",
            "https://example.org:443/a?version=1#part",
            "https://example.org/%61?version=1#part",
        )
        saved = [service.save_link(url) for url in urls]
        self.assertEqual([item["url"] for item in saved], list(urls))
        self.assertEqual(len({item["id"] for item in saved}), 8)
        self.assertEqual(service.search("")["total"], 8)

    def test_supported_http_url_syntax_is_not_a_fetch_or_public_destination_check(self):
        service = BookmarkService(self.root)
        for url in (
            "http://localhost:8080/local", "http://127.0.0.1/local",
            "https://[::1]:443/ipv6", "HTTPS://example.org/path?q=value#fragment",
            "https://例え.jp/東京", "https://example.org/encoded%20space?q=%26",
        ):
            with self.subTest(url=url):
                self.assertEqual(service.save_link(url)["url"], url)

    def test_invalid_urls_have_safe_typed_errors_and_never_save(self):
        service = BookmarkService(self.root)
        invalid = (
            None, 3, "", "example.org/a", "//example.org/a", "http:///missing-host",
            "https://", "file:///private-note", "javascript:alert(1)",
            "https://user:private-secret@example.org/a", "https://@example.org/a",
            " https://example.org/a", "https://example.org/a ",
            "https://exa mple.org/a", "https://example.org/a\n", "https://example.org/\tpath",
            "https://example.org/\x00", "https://example.org/\x7f", "https://example.org/\x85",
            "https://example.org/\u202e", "https://example.org/\ud800",
            "https://example.org:abc/a", "https://example.org:65536/a", "https://example.org:/a",
            "https://[::1/a", "https://[::1]trailing/a", "https://exa\\mple.org/a",
            "https://example..org/a", "https://-example.org/a", "https://example.org/%ZZ",
            "https://example.org/%0a", "https://exa%6dple.org/a",
        )
        for url in invalid:
            with self.subTest(url=repr(url)), self.assertRaises(ValidationError) as caught:
                service.save_link(url)
            self.assertEqual(caught.exception.code, "invalid_url")
            self.assertNotIn("private-secret", str(caught.exception))
        self.assertEqual(service.search("")["total"], 0)

    def test_invalid_numeric_hosts_are_rejected_without_saving(self):
        service = BookmarkService(self.root)
        for url in ('https://256.256.256.256/', 'https://example.123/',
                    'https://99999999999/', 'https://1.2.3.999/',
                    'https://0x7f000001/', 'https://127.1/',
                    'https://0177.0.0.1/'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                service.save_link(url)
        self.assertEqual(service.search('')['total'], 0)
        url = 'https://192.0.2.1/path?keep=1#fragment'
        self.assertEqual(service.save_link(url)['url'], url)

    def test_legacy_numeric_host_remains_readable_after_capture_validation_changes(self):
        service = BookmarkService(self.root)
        with service._storage._transaction(write=True) as c:
            c.execute('INSERT INTO items(id,url,title) VALUES(?,?,?)',
                      ('legacy', 'https://256.256.256.256/', 'Legacy bookmark'))
        item = service.get('legacy')
        self.assertEqual(item['url'], 'https://256.256.256.256/')
        self.assertEqual(service.search('Legacy')['items'], [item])

    def test_url_requires_escaping_for_unsafe_ascii_characters(self):
        service = BookmarkService(self.root)
        for character in ('"', "<", ">", "`", "{", "}", "|", "^"):
            with self.subTest(character=character), self.assertRaises(ValidationError):
                service.save_link("https://example.org/path" + character)
        self.assertEqual(service.search("")["total"], 0)
        self.assertEqual(service.save_link("https://example.org/%3Cpath%3E")["url"],
                         "https://example.org/%3Cpath%3E")

    def test_unusable_path_value_is_a_safe_configuration_error(self):
        with self.assertRaises(ConfigurationError) as caught:
            BookmarkService(self.root / "invalid\x00private-path")
        self.assertNotIn("private-path", str(caught.exception))

    def test_invalid_title_query_or_item_id_is_a_typed_error(self):
        service = BookmarkService(self.root)
        for title in (None, 1, "null\x00title", "surrogate\ud800"):
            with self.subTest(title=repr(title)), self.assertRaises(ValidationError):
                service.save_link("https://example.org/title", title)
        for query in (None, 1, [], "null\x00query", "surrogate\ud800"):
            with self.subTest(query=repr(query)), self.assertRaises(ValidationError):
                service.search(query)
        for item_id in (None, 1, [], "", "null\x00id", "surrogate\ud800"):
            with self.subTest(item_id=repr(item_id)), self.assertRaises(ValidationError):
                service.get(item_id)
        self.assertEqual(service.search("")["total"], 0)

    def test_invalid_pagination_rejects_bool_and_noninteger_values(self):
        service = BookmarkService(self.root)
        for limit in (0, -1, 101, True, False, 1.0, "5", None):
            with self.subTest(limit=limit), self.assertRaises(ValidationError) as caught:
                service.search("", limit=limit)
            self.assertEqual(caught.exception.code, "invalid_argument")
        for offset in (-1, True, False, 1.0, "0", None):
            with self.subTest(offset=offset), self.assertRaises(ValidationError):
                service.search("", offset=offset)

    def test_pagination_bounds_and_oversized_offset_remain_valid(self):
        service = BookmarkService(self.root)
        item = service.save_link("https://example.org/page", "Token")
        self.assertEqual(service.search("Token", limit=1)["items"], [item])
        self.assertEqual(service.search("Token", limit=100)["items"], [item])
        for offset in (1, 10**100):
            with self.subTest(offset=offset):
                self.assertEqual(service.search("Token", offset=offset), {
                    "items": [], "total": 1, "limit": 50, "offset": offset,
                })

    def test_filtered_pagination_uses_total_matches_and_deterministic_order(self):
        service = BookmarkService(self.root)
        expected = []
        for i in range(7):
            title = "Needletitle" if i % 2 == 0 else "Other"
            item = service.save_link(f"https://example.org/paged/{i}", title)
            if i % 2 == 0:
                expected.append(item)
        a = service.search("Needletitle", limit=2)
        b = BookmarkService(self.root).search("Needletitle", limit=2, offset=2)
        self.assertEqual(a["items"] + b["items"], expected)
        self.assertEqual((a["total"], b["total"]), (4, 4))

    def test_fts_operators_quotes_and_sql_punctuation_are_literal_not_executable(self):
        service = BookmarkService(self.root)
        phrase = service.save_link("https://example.org/phrase", 'Alpha OR Beta "quoted"')
        service.save_link("https://example.org/alpha", "Alpha alone")
        service.save_link("https://example.org/beta", "Beta alone")
        injection = service.save_link("https://example.org/sql", "Robert'); DROP TABLE items;--")
        self.assertEqual(service.search("Alpha OR Beta")["items"], [phrase])
        self.assertEqual(service.search('"quoted"')["items"], [phrase])
        self.assertEqual(service.search("Robert'); DROP TABLE items;--")["items"], [injection])
        for query in ("*", '"', "()", "NOT", "title:Alpha", "Alpha NEAR Beta", "x' OR 1=1 --"):
            with self.subTest(query=query):
                self.assertEqual(service.search(query)["total"], 0)
        with self.assertRaises(NotFoundError):
            service.get("' OR 1=1 --")
        self.assertEqual(service.search("")["total"], 4)

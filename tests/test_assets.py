import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from bookmarks.assets import AssetStore


def image_bytes(fmt='PNG',size=(2,2)):
    stream=BytesIO(); Image.new('RGB',size,'blue').save(stream,format=fmt); return stream.getvalue()


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.assets=AssetStore(self.root)
    def test_valid_image_roundtrip_reopen_and_preview(self):
        item=self.assets.store_image(image_bytes(),'image/png')
        self.assertEqual((item['width'],item['height']),(2,2))
        self.assertNotIn('path',item)
        other=AssetStore(self.root)
        content,mime=other.read_asset(item['id'])
        self.assertEqual(mime,'image/png')
        with Image.open(BytesIO(content)) as image: self.assertEqual(image.size,(2,2))
        preview=other.preview(item['id'])
        self.assertTrue(base64.b64decode(preview['content_base64']))
    def test_mime_mismatch_svg_html_truncated_and_byte_limit_rejected(self):
        for content,mime in [(image_bytes(),'image/jpeg'),(b'<svg/>','image/svg+xml'),(b'<html/>','image/png'),(image_bytes()[:20],'image/png'),(b'x'*(10*1024*1024+1),'image/png')]:
            with self.subTest(mime=mime):
                with self.assertRaises(ValueError): self.assets.store_image(content,mime)
        self.assertEqual(list((self.root/'assets').glob('*')),[])
    def test_decoded_dimensions_bounded_before_load(self):
        content=image_bytes(size=(5000,5000))
        with self.assertRaises(ValueError): self.assets.store_image(content,'image/png')
    def test_paths_unknown_ids_and_symlinks_cannot_read_other_files(self):
        for key in ['../secret','/etc/passwd','x'*32,'a'*32]:
            with self.assertRaises((ValueError,LookupError)): self.assets.read_asset(key)
        item=self.assets.store_image(image_bytes(),'image/png')
        asset=self.root/'assets'/(item['id']+'.blob'); asset.unlink()
        asset.symlink_to(self.root/'bookmarks.sqlite3')
        with self.assertRaises(ValueError): self.assets.read_asset(item['id'])

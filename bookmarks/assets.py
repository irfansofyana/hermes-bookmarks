"""Owned image assets. No arbitrary file references or public static mount."""
import base64
from io import BytesIO
from pathlib import Path
import re
import tempfile
import os
from uuid import uuid4
from PIL import Image, ImageOps, UnidentifiedImageError
from .storage import Storage

MAX_BYTES=10*1024*1024
MAX_PIXELS=20_000_000
FORMATS={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}


class AssetStore:
    def __init__(self,data_root):
        self.storage=Storage(data_root)
        self.folder=Path(data_root)/'assets'
        self.folder.mkdir(exist_ok=True)

    def store_image(self,content,declared_type):
        if not isinstance(content,bytes) or not content or len(content)>MAX_BYTES: raise ValueError('Image exceeds limit')
        try:
            with Image.open(BytesIO(content)) as image:
                fmt=image.format
                if fmt not in FORMATS or FORMATS[fmt]!=declared_type: raise ValueError('Unsupported or mismatched image type')
                if image.width*image.height>MAX_PIXELS or getattr(image,'n_frames',1)!=1: raise ValueError('Image dimensions or animation exceed limit')
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image.load()
                normalized=ImageOps.exif_transpose(image)
                # Reencode instead of persisting embedded scripts/EXIF/location metadata.
                normalized=normalized.convert('RGB' if fmt=='JPEG' else 'RGBA')
                normalized.info.clear()
                encoded=BytesIO(); normalized.save(encoded,format=fmt)
                data=encoded.getvalue(); width,height=normalized.size
            if len(data)>MAX_BYTES: raise ValueError('Normalized image exceeds limit')
        except (UnidentifiedImageError,OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning):
            raise ValueError('Invalid image') from None
        asset_id=uuid4().hex
        target=self.folder/(asset_id+'.blob')
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=self.folder,delete=False) as handle:
                temporary=Path(handle.name); handle.write(data); handle.flush(); os.fsync(handle.fileno())
            temporary.replace(target); temporary=None
            with self.storage._transaction(write=True) as c:
                c.execute('INSERT INTO assets VALUES(?,?,?,?,?)',(asset_id,FORMATS[fmt],len(data),width,height))
        except BaseException:
            if temporary is not None: temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
        return {'id':asset_id,'mime_type':FORMATS[fmt],'size':len(data),'width':width,'height':height}

    def get_asset(self,asset_id):
        if not isinstance(asset_id,str) or not re.fullmatch('[a-f0-9]{32}',asset_id): raise ValueError('Invalid asset ID')
        with self.storage._transaction() as c:
            row=c.execute('SELECT * FROM assets WHERE id=?',(asset_id,)).fetchone()
            if row is None: raise LookupError('Asset not found')
            return dict(row)

    def read_asset(self,asset_id):
        metadata=self.get_asset(asset_id)
        path=self.folder/(asset_id+'.blob')
        if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES: raise ValueError('Asset unavailable')
        return path.read_bytes(),metadata['mime_type']

    def preview(self,asset_id):
        content,_=self.read_asset(asset_id)
        with Image.open(BytesIO(content)) as image:
            image.thumbnail((320,320))
            image=image.convert('RGB'); output=BytesIO(); image.save(output,format='JPEG',quality=80)
        return {'id':asset_id,'mime_type':'image/jpeg','content_base64':base64.b64encode(output.getvalue()).decode('ascii')}

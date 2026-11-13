import base64
import io
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from PIL import Image

from backend import gameicons, images, saves
from app import Handler
from sims4_sdk.core.dbpf import ResourceKey
from sims4_sdk.core.images import GameImage
from sims4_sdk.save.artwork import Artwork


def image_bytes(mode, color, fmt):
    out = io.BytesIO()
    Image.new(mode, (4, 4), color).save(out, format=fmt)
    return out.getvalue()


class ImageConversionTests(unittest.TestCase):
    def test_icon_uses_sdk_conversion_and_new_cache(self):
        image = GameImage(ResourceKey(1, 0, 2), image_bytes("RGBA", (4, 8, 12, 64), "PNG"), "PNG")
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(gameicons, "CACHE_DIR", Path(directory)), \
                patch.object(gameicons, "_READY", True), \
                patch.object(gameicons.sdk, "workspace") as workspace, \
                patch.object(GameImage, "to_png", autospec=True, wraps=None, return_value=image.to_png()) as convert:
            workspace.return_value.icon_for.return_value = image
            target = gameicons.icon_path("0001:0000:0002")
            convert.assert_called_once_with(image)
            self.assertTrue(target.name.startswith("sdk_"))
            with Image.open(target) as result:
                self.assertEqual(result.convert("RGBA").getpixel((0, 0)), (4, 8, 12, 64))

    def test_artwork_png_preserves_mask_and_cache_updates(self):
        artwork = Artwork(image_bytes("RGB", (200, 30, 20), "JPEG"), image_bytes("L", 96, "PNG"), "png")
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "source.jpg", Path(directory) / "out.png"
            source.write_bytes(b"source")
            with patch.object(images, "decode_artwork", return_value=artwork) as decode:
                self.assertEqual(images._artwork_png_path(source, target), target)
                self.assertEqual(images._artwork_png_path(source, target), target)
                decode.assert_called_once()
            with Image.open(target) as result:
                self.assertEqual(result.size, (4, 4))
                self.assertEqual(result.getpixel((0, 0))[3], 96)

    def test_save_thumbnail_uses_sdk_png_and_falls_back(self):
        artwork = Artwork(image_bytes("RGB", (10, 20, 30), "JPEG"), image_bytes("L", 64, "PNG"), "png")
        url = saves._artwork_data_url(artwork)
        self.assertTrue(url.startswith("data:image/png;base64,"))
        with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as result:
            self.assertEqual(result.getpixel((0, 0))[3], 64)
        with patch.object(Artwork, "to_png", side_effect=ValueError("bad artwork")):
            self.assertTrue(saves._artwork_data_url(artwork).startswith("data:image/jpeg;base64,"))

    def test_mask_is_used_only_if_png_conversion_fails(self):
        with patch.object(images, "png_path", return_value=Path("converted.png")), \
                patch.object(images, "has_mask", return_value=True):
            self.assertEqual(images.mask_url_if_any("0x0000000000000001", "sim"), "")
        with patch.object(images, "png_path", return_value=None), \
                patch.object(images, "has_mask", return_value=True):
            self.assertIn("image_mask", images.mask_url_if_any("0x0000000000000001", "sim"))

    def test_tray_http_serves_png_and_legacy_jpeg(self):
        artwork = Artwork(image_bytes("RGB", (20, 30, 40), "JPEG"), image_bytes("L", 80, "PNG"), "png")
        instance = "0x0000000000000001"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.sgi"
            source.write_bytes(b"source")
            with patch.object(images, "CACHE_DIR", Path(directory)), \
                    patch.object(images, "_index", return_value={instance: source}), \
                    patch.object(images, "read_artwork", return_value=artwork):
                server = HTTPServer(("127.0.0.1", 0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    url = f"http://127.0.0.1:{server.server_port}/api/tray/image?kind=sim&instance={instance}"
                    with urlopen(url + "&format=png") as response:
                        self.assertEqual(response.headers.get_content_type(), "image/png")
                        with Image.open(io.BytesIO(response.read())) as result:
                            self.assertEqual(result.getpixel((0, 0))[3], 80)
                    with urlopen(url) as response:
                        self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                finally:
                    server.shutdown()
                    thread.join()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()

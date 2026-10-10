import os
import struct
import sys

import pytest
from PIL import Image

from aracmerkezi.tools.clipboard import clipboard_io as cio


def test_dib_bytes_is_a_bmp_without_the_file_header():
    data = cio.dib_bytes(Image.new("RGB", (4, 3), (255, 0, 0)))
    size, width, height = struct.unpack("<Iii", data[:12])
    assert size == 40 and (width, height) == (4, 3)             # BITMAPINFOHEADER


def test_dropfiles_layout(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    blob = cio.dropfiles_bytes([a, b])
    p_files, _x, _y, f_nc, f_wide = struct.unpack("<IiiII", blob[:20])
    assert p_files == 20 and f_nc == 0 and f_wide == 1          # geniş karakter listesi
    names = blob[20:].decode("utf-16-le")
    assert names.endswith("\0\0")
    assert names.split("\0")[:2] == [str(a.resolve()), str(b.resolve())]


def test_sequence_number_is_an_int_on_windows():
    seq = cio.sequence_number()
    assert (isinstance(seq, int) and seq > 0) if sys.platform == "win32" else seq is None


@pytest.mark.skipif(sys.platform != "win32" or not os.environ.get("LUMORA_TEST_CLIPBOARD"),
                    reason="Gerçek panonun içeriğini değiştirir; LUMORA_TEST_CLIPBOARD=1 ile açılır")
def test_real_clipboard_roundtrip_for_image_and_files(tmp_path):
    f1, f2 = tmp_path / "bir.txt", tmp_path / "iki.txt"
    f1.write_text("1")
    f2.write_text("2")
    cio.set_image(Image.new("RGB", (30, 20), (10, 120, 200)))
    kind, payload = cio.read_non_text()
    assert kind == "image" and payload.size == (30, 20) and payload.getpixel((5, 5)) == (10, 120, 200)
    cio.set_files([f1, f2])
    kind, payload = cio.read_non_text()
    assert kind == "files" and [os.path.basename(p) for p in payload] == ["bir.txt", "iki.txt"]

"""Tek dosyalık AracMerkezi.exe ve güncelleme manifesti üretir.

Kullanım:
    py build.py                                  # dist/AracMerkezi.exe + dist/manifest.json
    py build.py --update-url https://.../manifest.json   # uygulamaya varsayılan güncelleme adresini gömer
    py build.py --base-url https://.../          # manifestteki exe adresini mutlak yapar

Yeni sürüm yayınlamak için: src/aracmerkezi/__init__.py içindeki __version__ değerini artır,
`py build.py` çalıştır, dist/ içindeki AracMerkezi.exe ve manifest.json dosyalarını
manifest adresinin gösterdiği yere yükle. Kurulu uygulamalar bir sonraki açılışta kendini günceller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "AracMerkezi"


def read_version() -> str:
    text = (ROOT / "src" / "aracmerkezi" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def write_version_file(version: str) -> Path:
    """Windows sürüm bilgisi kaynağı (PyInstaller --version-file biçimi)."""
    nums = (tuple(int(x) for x in re.findall(r"\d+", version)) + (0, 0, 0, 0))[:4]
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', 'LumoraTools'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{NAME}'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', 'LumoraTools'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path = ROOT / "build" / "version_info.txt"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update-url", help="Uygulamaya gömülecek varsayılan manifest adresi (https)")
    ap.add_argument("--base-url", default="", help="exe'nin yayınlanacağı klasör adresi (sonu / ile)")
    ap.add_argument("--notes", default="", help="Manifeste yazılacak sürüm notu")
    args = ap.parse_args()

    if args.update_url:
        if not args.update_url.startswith("https://"):
            ap.error("--update-url https:// ile başlamalı")
        (ROOT / "src" / "aracmerkezi" / "_buildinfo.py").write_text(
            "# build.py --update-url ... ile yazılır. Boşsa güncelleme adresi Ayarlar'dan girilir.\n"
            f'UPDATE_URL = "{args.update_url}"\n', encoding="utf-8")

    icon = ROOT / "assets" / "icon.ico"
    version_file = write_version_file(read_version())  # .exe sağ tık > Ayrıntılar'da görünen sürüm
    # Araç modülleri dinamik import edilir (importlib), PyInstaller bunları kendiliğinden görmez.
    sys.path.insert(0, str(ROOT / "src"))
    from aracmerkezi.registry import BUILTIN_TOOLS
    hidden = [arg for name in BUILTIN_TOOLS for arg in ("--hidden-import", f"aracmerkezi.tools.{name}")]
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME, "--icon", str(icon), "--add-data", f"{icon};assets",
        "--add-data", f"{icon.parent / 'logo.png'};assets", "--version-file", str(version_file),
        "--paths", str(ROOT / "src"),
        "--collect-all", "customtkinter",
        "--collect-submodules", "aracmerkezi", "--collect-submodules", "duzenle",
        "--hidden-import", "pypdf", *hidden,
        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
        str(ROOT / "launch.py"),
    ]
    print("->", " ".join(cmd))
    if subprocess.call(cmd, cwd=ROOT) != 0:
        return 1

    exe = ROOT / "dist" / f"{NAME}.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    manifest = {"version": read_version(), "url": f"{args.base_url}{exe.name}", "sha256": digest,
                "notes": args.notes}
    (ROOT / "dist" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nHazır: {exe}  ({exe.stat().st_size / 1e6:.1f} MB)\nSürüm: {manifest['version']}\nSHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

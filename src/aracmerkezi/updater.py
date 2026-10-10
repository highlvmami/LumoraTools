"""Kendini güncelleme: manifest denetimi, doğrulamalı indirme ve çalışan .exe'nin değiştirilmesi.

Manifest (manifest.json) biçimi:
    {"version": "0.4.0", "url": "AracMerkezi.exe", "sha256": "<64 hex>", "notes": "..."}
`url` manifestin bulunduğu yere göre göreli olabilir.

Güvenlik: uzak kaynaklar yalnızca https olabilir ve indirilen dosyanın SHA-256 özeti
manifestteki ile eşleşmezse kurulmaz. Kod imzalama yoktur; güven, manifesti sunan
https adresine dayanır.

Windows'ta çalışan .exe silinemez ama yeniden adlandırılabilir. Bu yüzden değişim şöyle:
    AracMerkezi.exe -> AracMerkezi.exe.old, yeni dosya -> AracMerkezi.exe
.old dosyası bir sonraki açılışta silinir.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

CHUNK = 1024 * 1024
Progress = Callable[[int, int], None]  # (inen bayt, toplam bayt; bilinmiyorsa 0)


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Update:
    version: str
    url: str
    sha256: str
    notes: str = ""


def parse_version(v: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", v)
    if not parts:
        raise UpdateError(f"Geçersiz sürüm: {v!r}")
    return tuple(int(p) for p in parts)


def is_newer(candidate: str, current: str) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def _is_local(source: str) -> bool:
    scheme = urllib.parse.urlparse(source).scheme
    return scheme in ("", "file") or len(scheme) == 1  # "C:\..." sürücü harfi


def _open(source: str, timeout: float = 20) -> BinaryIO:
    if _is_local(source):
        path = urllib.request.url2pathname(urllib.parse.urlparse(source).path) \
            if source.startswith("file:") else source
        return open(path, "rb")
    if urllib.parse.urlparse(source).scheme == "https":
        return urllib.request.urlopen(source, timeout=timeout)  # noqa: S310 - şema denetlendi
    raise UpdateError("Güncelleme adresi https:// olmalı (ya da yerel bir yol).")


def _resolve(base: str, ref: str) -> str:
    if urllib.parse.urlparse(ref).scheme == "https" or (_is_local(ref) and Path(ref).is_absolute()):
        return ref
    if _is_local(base):
        return str(Path(base).parent / ref)
    return urllib.parse.urljoin(base, ref)


def fetch_manifest(source: str) -> Update:
    try:
        with _open(source) as f:
            data = json.load(f)
    except UpdateError:
        raise
    except Exception as e:
        raise UpdateError(f"Manifest okunamadı: {e}") from e
    try:
        version, url, sha = str(data["version"]), str(data["url"]), str(data["sha256"]).lower()
    except (KeyError, TypeError) as e:
        raise UpdateError(f"Manifest eksik alan içeriyor: {e}") from e
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise UpdateError("Manifestteki sha256 geçersiz.")
    parse_version(version)
    return Update(version, _resolve(source, url), sha, str(data.get("notes", "")))


def check(source: str, current: str) -> Update | None:
    """Daha yeni bir sürüm varsa onu, yoksa None döndürür."""
    update = fetch_manifest(source)
    return update if is_newer(update.version, current) else None


def download(update: Update, dest: Path, progress: Progress | None = None) -> Path:
    """Güncellemeyi `dest` dosyasına indirir ve özetini doğrular; uyuşmazsa dosyayı siler."""
    digest = hashlib.sha256()
    done = 0
    try:
        with _open(update.url, timeout=30) as src, open(dest, "wb") as out:
            total = int(getattr(src, "length", None) or 0)
            while chunk := src.read(CHUNK):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except UpdateError:
        dest.unlink(missing_ok=True)
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"İndirilemedi: {e}") from e
    if digest.hexdigest() != update.sha256:
        dest.unlink(missing_ok=True)
        raise UpdateError("İndirilen dosyanın SHA-256 özeti manifestle uyuşmuyor; güncelleme reddedildi.")
    return dest


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_exe() -> Path:
    return Path(sys.executable)


def old_path(exe: Path) -> Path:
    return exe.with_name(exe.name + ".old")


def new_path(exe: Path) -> Path:
    return exe.with_name(exe.name + ".new")


def replace_executable(current: Path, new: Path) -> None:
    """Çalışan `current`'ı yedeğe alıp yerine `new`'ı koyar. Hata olursa eski hâli geri yükler."""
    old = old_path(current)
    old.unlink(missing_ok=True)
    current.rename(old)
    try:
        new.rename(current)
    except OSError:
        old.rename(current)
        raise


def cleanup_old(exe: Path) -> None:
    try:
        old_path(exe).unlink(missing_ok=True)
        new_path(exe).unlink(missing_ok=True)
    except OSError:
        pass  # hâlâ kullanımda olabilir; sonraki açılışta tekrar denenir


def install(update: Update, exe: Path | None = None, progress: Progress | None = None) -> Path:
    """İndirir, doğrular, .exe'yi değiştirir. Yeni .exe'nin yolunu döndürür."""
    exe = exe or current_exe()
    staged = new_path(exe)
    try:
        download(update, staged, progress)
        replace_executable(exe, staged)
    except PermissionError as e:
        staged.unlink(missing_ok=True)
        raise UpdateError(f"Uygulama klasörüne yazılamadı ({exe.parent}): {e}") from e
    return exe


def restart(exe: Path) -> None:
    """Yeni sürümü ayrı bir süreç olarak başlatır (çağıran uygulamayı kapatmalı)."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"  # onefile alt süreç ortamını devralmasın
    subprocess.Popen([str(exe)], env=env, close_fds=True)  # noqa: S603

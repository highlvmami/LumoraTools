"""İzleyici mantığı: sahte pano ve sahte Tk bileşeniyle (gerçek panoya dokunmaz)."""
import tkinter as tk

import pytest
from PIL import Image

from aracmerkezi.tools.clipboard.monitor import ClipboardMonitor
from aracmerkezi.tools.clipboard.store import FILES, IMAGE, TEXT, ClipStore


class FakeClipboard:
    """Sayaçlı sahte Windows panosu."""

    def __init__(self):
        self.seq = 1
        self.text = None
        self.other = None            # ('image', Image) | ('files', [...])
        self.has_counter = True

    def copy_text(self, text):
        self.text, self.other = text, None
        self.seq += 1

    def copy_other(self, kind, payload):
        self.text, self.other = None, (kind, payload)
        self.seq += 1

    # clipboard_io arayüzü
    def sequence_number(self):
        return self.seq if self.has_counter else None

    def read_non_text(self):
        return self.other


class FakeWidget:
    def __init__(self, clip):
        self.clip = clip
        self.jobs = 0

    def clipboard_get(self):
        if self.clip.text is None:
            raise tk.TclError("CLIPBOARD selection doesn't exist or form \"STRING\" not defined")
        return self.clip.text

    def after(self, ms, fn):
        self.jobs += 1
        return f"job{self.jobs}"

    def after_cancel(self, job):
        pass


@pytest.fixture
def env(tmp_path):
    clip = FakeClipboard()
    store = ClipStore(tmp_path / "c.db")
    mon = ClipboardMonitor(FakeWidget(clip), store, io=clip)
    return clip, store, mon


def kinds(store):
    return [c.kind for c in store.list()]


def test_text_image_and_files_are_each_captured_once(env):
    clip, store, mon = env
    clip.copy_text("merhaba")
    mon._poll()
    mon._poll()                                           # sayaç aynı: tekrar kayıt yok
    clip.copy_other("image", Image.new("RGB", (8, 8), (9, 9, 9)))
    mon._poll()
    clip.copy_other("files", [r"C:\a\bir.txt", r"C:\a\iki.txt"])
    mon._poll()
    assert sorted(kinds(store)) == sorted([TEXT, IMAGE, FILES]) and store.count() == 3


def test_same_text_copied_again_is_bumped_not_duplicated(env):
    clip, store, mon = env
    clip.copy_text("a")
    mon._poll()
    clip.copy_text("b")
    mon._poll()
    clip.copy_text("a")                                   # sayaç değişti, içerik aynı → en üste
    mon._poll()
    assert [c.text for c in store.list()] == ["a", "b"]


def test_text_wins_over_other_formats(env):
    clip, store, mon = env
    clip.text, clip.other = "tablo hücresi", ("image", Image.new("RGB", (4, 4)))   # Excel/Word gibi karma içerik
    clip.seq += 1
    mon._poll()
    assert kinds(store) == [TEXT]


def test_paused_monitor_records_nothing_and_resume_skips_missed_content(env):
    clip, store, mon = env
    mon.set_paused(True)
    clip.copy_text("gizli")
    mon._poll()
    assert store.count() == 0
    mon.set_paused(False)                                 # durmuşken kopyalanan geriye dönük eklenmez
    mon._poll()
    assert store.count() == 0
    clip.copy_text("yeni")
    mon._poll()
    assert [c.text for c in store.list()] == ["yeni"]


def test_resume_does_not_capture_what_was_already_on_the_clipboard(env):
    clip, store, mon = env
    clip.copy_text("onceki")
    mon.resume()
    assert store.count() == 0 and mon.widget.jobs == 1


def test_mark_own_prevents_re_recording_what_the_app_put_on_the_clipboard(env):
    clip, store, mon = env
    clip.copy_other("image", Image.new("RGB", (6, 6)))   # geçmişten 'Kopyala' ile panoya yazıldı
    mon.mark_own()
    mon._poll()
    assert store.count() == 0
    clip.copy_other("image", Image.new("RGB", (6, 6), (1, 1, 1)))   # sonra kullanıcı başka şey kopyaladı
    mon._poll()
    assert kinds(store) == [IMAGE]


def test_without_a_sequence_counter_it_falls_back_to_text_comparison(env):
    clip, store, mon = env
    clip.has_counter = False
    clip.copy_text("bir")
    mon._poll()
    mon._poll()
    clip.copy_text("iki")
    mon._poll()
    assert [c.text for c in store.list()] == ["iki", "bir"]


def test_listeners_are_notified_and_may_remove_themselves(env):
    clip, store, mon = env
    calls = []

    def once():
        calls.append(1)
        mon.listeners.remove(once)

    mon.listeners.append(once)
    mon.listeners.append(lambda: calls.append(2))
    clip.copy_text("x")
    mon._poll()
    assert calls == [1, 2]
    clip.copy_text("y")
    mon._poll()
    assert calls == [1, 2, 2]


def test_failed_capture_does_not_break_the_loop(env):
    clip, store, mon = env
    clip.copy_other("files", [])                          # boş liste kaydedilmez ama döngü sürer
    mon._poll()
    assert store.count() == 0 and mon.widget.jobs == 1

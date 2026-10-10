import zipfile

from aracmerkezi.tools.search.index import Index, make_match, make_snippet


def make_docx(path, text):
    xml = f'<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def test_finds_text_files_and_ignores_binary(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("Bugün toplantı notları: bütçe planı", encoding="utf-8")
    (docs / "b.py").write_text("def hesapla():\n    return 42\n", encoding="utf-8")
    (docs / "c.txt").write_bytes(b"\x00\x01\x02 gizli ikili")
    idx = Index(tmp_path / "s.db")
    stats = idx.index_roots([docs])
    assert stats["scanned"] == 3
    assert [h.path for h in idx.search("hesapla")] == [str(docs / "b.py")]
    assert idx.search("gizli") == []


def test_turkish_characters_are_folded(tmp_path):
    (tmp_path / "n.txt").write_text("Çalışma ÖZETİ ve ığdır şehri", encoding="utf-8")
    idx = Index(tmp_path / "s.db")
    idx.index_roots([tmp_path])
    for q in ("çalışma", "calisma", "CALISMA", "özeti", "ozeti", "ıgdır", "igdir"):
        assert len(idx.search(q)) == 1, q


def test_prefix_and_all_words_must_match(tmp_path):
    (tmp_path / "1.txt").write_text("kırmızı elma ağacı")
    (tmp_path / "2.txt").write_text("yeşil elma")
    idx = Index(tmp_path / "s.db")
    idx.index_roots([tmp_path])
    assert len(idx.search("elm")) == 2
    assert len(idx.search("elma kirmizi")) == 1


def test_incremental_update_and_removal(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("eski icerik")
    idx = Index(tmp_path / "s.db")
    assert idx.index_roots([tmp_path])["indexed"] == 1
    assert idx.index_roots([tmp_path])["indexed"] == 0  # değişmedi
    f.write_text("yepyeni icerik burada")
    assert idx.index_roots([tmp_path])["indexed"] == 1
    assert idx.search("eski") == [] and len(idx.search("yepyeni")) == 1
    f.unlink()
    assert idx.index_roots([tmp_path])["removed"] == 1
    assert idx.search("yepyeni") == []
    assert idx.stats() == {"files": 0, "searchable": 0}


def test_docx_extraction(tmp_path):
    make_docx(tmp_path / "rapor.docx", "Yıllık gelir tablosu &amp; gider")
    idx = Index(tmp_path / "s.db")
    idx.index_roots([tmp_path])
    hits = idx.search("gelir")
    assert len(hits) == 1 and "gider" in hits[0].snippet and "&amp;" not in hits[0].snippet


def test_query_with_fts_syntax_does_not_crash(tmp_path):
    (tmp_path / "a.txt").write_text("merhaba dunya")
    idx = Index(tmp_path / "s.db")
    idx.index_roots([tmp_path])
    for q in ('"', "AND OR NOT", "merhaba*", "a:b", "(", "", "   "):
        idx.search(q)  # istisna fırlatmamalı


def test_snippet_highlights_original_text():
    body = "x" * 300 + " Çalışma planı hazır " + "y" * 300
    snippet, spans = make_snippet(body, make_match("calisma")[1])
    assert snippet.startswith("…")
    s, e = spans[0]
    assert snippet[s:e] == "Çalışma"


def test_skips_dirs_and_respects_stop(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("gizli paket")
    (tmp_path / "ok.txt").write_text("gorunur")
    idx = Index(tmp_path / "s.db")
    idx.index_roots([tmp_path])
    assert idx.search("gizli") == [] and len(idx.search("gorunur")) == 1

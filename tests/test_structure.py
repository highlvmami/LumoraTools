from aracmerkezi.structure import build_tree, list_entries


def make(tmp_path):
    (tmp_path / "Projeler" / "Web").mkdir(parents=True)
    (tmp_path / "Projeler" / "bos").mkdir()
    (tmp_path / "Belgeler").mkdir()
    (tmp_path / ".gizli").mkdir()
    (tmp_path / ".gizli" / "x.txt").write_text("x")
    (tmp_path / "Projeler" / "Web" / "index.html").write_text("a" * 10)
    (tmp_path / "Projeler" / "Web" / "stil.css").write_text("a" * 5)
    (tmp_path / "Projeler" / "not.md").write_text("a" * 3)
    (tmp_path / "Belgeler" / "Çalışma.docx").write_text("a" * 7)
    (tmp_path / "kok.txt").write_text("a")
    (tmp_path / ".gizli_dosya").write_text("x")
    return tmp_path


def names(node):
    return [c.name for c in node.children]


def test_lists_files_and_dirs_skipping_hidden(tmp_path):
    files, dirs, truncated = list_entries(make(tmp_path))
    assert not truncated
    assert {f.path.name for f in files} == {"Çalışma.docx", "index.html", "kok.txt", "not.md", "stil.css"}
    assert all(".gizli" not in str(d) for d in dirs)


def test_tree_structure_sorted_dirs_first_with_totals(tmp_path):
    root = make(tmp_path)
    files, dirs, _ = list_entries(root)
    top = build_tree(root, files, dirs)
    assert names(top) == ["Belgeler", "Projeler", "kok.txt"]          # klasörler önce, sonra dosya
    projeler = next(c for c in top.children if c.name == "Projeler")
    assert names(projeler) == ["bos", "Web", "not.md"]   # klasörler (a-z), sonra dosyalar
    web = next(c for c in projeler.children if c.name == "Web")
    assert (web.file_count, web.size) == (2, 15)
    assert projeler.file_count == 3 and projeler.size == 18
    assert top.file_count == 5 and top.size == 26
    assert next(c for c in projeler.children if c.name == "bos").file_count == 0   # boş klasör görünür


def test_filter_by_file_or_folder_name_prunes_empty_dirs(tmp_path):
    root = make(tmp_path)
    files, dirs, _ = list_entries(root)
    top = build_tree(root, files, dirs, "calisma")                    # Türkçe harf duyarsız
    assert names(top) == ["Belgeler"] and top.file_count == 1
    top = build_tree(root, files, dirs, "web")                        # klasör adıyla: içindekiler gelir
    assert top.file_count == 2 and names(top) == ["Projeler"]
    assert build_tree(root, files, dirs, "yokboyle").children == []


def test_limit_truncates(tmp_path):
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("x")
    files, _, truncated = list_entries(tmp_path, limit=3)
    assert len(files) == 3 and truncated

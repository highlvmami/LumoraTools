from pathlib import Path

from duzenle.engine import Move
from aracmerkezi.plan_view import PlanView

ROOT = Path("C:/kok") if Path("C:/").exists() else Path("/kok")


def view(names_groups, sizes=None):
    moves = [Move(ROOT / n, ROOT / g / n) for n, g in names_groups]
    return PlanView(ROOT, moves, {m.src: s for m, s in zip(moves, sizes or [0] * len(moves))})


DATA = [("a.jpg", "Resimler"), ("b.png", "Resimler"), ("c.pdf", "Belgeler"), ("d.txt", "Belgeler"),
        ("e.zip", "Arsivler")]


def test_default_everything_selected_and_grouped_sorted():
    v = view(DATA)
    assert len(v.selected_moves()) == 5
    assert [g for g, _ in v.groups()] == ["Arsivler", "Belgeler", "Resimler"]
    assert v.selected_group_count() == 3


def test_toggle_single_and_group_state():
    v = view(DATA)
    v.toggle(0)  # a.jpg kaldır
    assert v.group_state("Resimler") == "some"
    assert v.group_state("Belgeler") == "all"
    assert len(v.selected_moves()) == 4
    v.toggle(0)
    assert v.group_state("Resimler") == "all"


def test_toggle_group_unchecks_then_checks_all():
    v = view(DATA)
    v.toggle_group("Belgeler")
    assert v.group_state("Belgeler") == "none" and len(v.selected_moves()) == 3
    v.toggle_group("Belgeler")
    assert v.group_state("Belgeler") == "all"
    v.toggle(2)                     # kısmi durumda grup tıklanınca hepsi seçilir
    v.toggle_group("Belgeler")
    assert v.group_state("Belgeler") == "all"


def test_bulk_actions_apply_to_visible_only():
    v = view(DATA)
    v.set_visible(False)
    assert v.selected_moves() == []
    v.query = "pdf"
    v.set_visible(True)             # yalnızca c.pdf
    assert [it.name for it in v.selected_items()] == ["c.pdf"]
    v.query = ""
    v.invert_visible()              # c.pdf kapanır, diğer dördü açılır
    assert sorted(it.name for it in v.selected_items()) == ["a.jpg", "b.png", "d.txt", "e.zip"]


def test_filter_matches_name_group_and_turkish_insensitive():
    v = view([("Çalışma.docx", "Belgeler"), ("x.jpg", "Resimler")])
    v.query = "calisma"
    assert [it.name for it in v.visible()] == ["Çalışma.docx"]
    v.query = "resim"                # klasör adıyla
    assert [it.name for it in v.visible()] == ["x.jpg"]
    v.query = "yok"
    assert v.groups() == []


def test_selection_independent_of_filter_and_hidden_count():
    v = view(DATA)
    v.query = "jpg"
    assert [it.name for it in v.visible()] == ["a.jpg"]
    assert v.hidden_selected() == 4          # filtre nedeniyle gizli ama işaretli
    assert len(v.selected_moves()) == 5      # taşıma hepsini kapsar


def test_selected_bytes_counts_only_checked():
    v = view(DATA, sizes=[100, 200, 300, 400, 500])
    assert v.selected_bytes() == 1500
    v.toggle(4)
    assert v.selected_bytes() == 1000


def test_new_rel_shows_destination_including_conflict_rename():
    moves = [Move(ROOT / "a.jpg", ROOT / "Resimler" / "a (1).jpg")]
    it = PlanView(ROOT, moves).items[0]
    assert it.group == "Resimler" and it.new_rel.endswith("a (1).jpg") and it.new_rel.startswith("Resimler")

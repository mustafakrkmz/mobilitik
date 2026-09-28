from mobilitik.analysis.verbs import (
    extract_by_suffix,
    parse_suffix_conditions,
    suffix_verb_stats,
)


def test_parse_suffix_conditions_accepts_dashes_commas_and_semicolons():
    assert parse_suffix_conditions("-ıyor; -ildi, uldu") == ("ıyor", "ildi", "uldu")


def test_custom_passive_past_suffixes_find_surface_stems():
    assert extract_by_suffix("yapıldı", "ıldı; ildi") == ("yap", "ıldı")
    assert extract_by_suffix("değiştirildi", "ıldı; ildi") == ("değiştir", "ildi")
    assert extract_by_suffix("yapıldım", "ıldı") == ("yap", "ıldı")


def test_suffix_stats_mix_progressive_and_passive_conditions():
    rows = suffix_verb_stats(
        [
            "Servis geliyor ama parça değiştirilmedi.",
            "Montaj yapıldı ve ürün kuruluyor.",
            "Parça değiştirildi.",
        ],
        "ıyor; iyor; uyor; üyor; ıldı; ildi; uldu; üldü",
    )
    by_stem = {row.stem: row for row in rows}
    assert "gel" in by_stem
    assert "yap" in by_stem
    assert "değiştir" in by_stem
    assert "kurul" in by_stem

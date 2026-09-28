import pytest

from mobilitik.company import company_root_url, normalize_company_input


@pytest.mark.parametrize(
    "value,expected",
    [
        ("istikbal", "istikbal"),
        ("/bellona/", "bellona"),
        ("https://www.sikayetvar.com/cilek-mobilya", "cilek-mobilya"),
        ("https://sikayetvar.com/konfor-mobilya/", "konfor-mobilya"),
        ("www.sikayetvar.com/cilek-mobilya", "cilek-mobilya"),
    ],
)
def test_normalize_company_input(value, expected):
    assert normalize_company_input(value) == expected


def test_company_root_url_is_canonical():
    assert company_root_url("sikayetvar.com/konfor-mobilya") == "https://www.sikayetvar.com/konfor-mobilya"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://example.com/cilek-mobilya",
        "https://www.sikayetvar.com/cilek-mobilya/calisma-masasi",
        "https://www.sikayetvar.com/cilek-mobilya/bir-sikayet-detayi",
        "çilek mobilya",
    ],
)
def test_normalize_company_input_rejects_non_root_or_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_company_input(value)

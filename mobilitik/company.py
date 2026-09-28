from __future__ import annotations

import re
from urllib.parse import urlparse


SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_HOSTS = {"sikayetvar.com", "www.sikayetvar.com"}


def normalize_company_input(value: str) -> str:
    """Return a Şikayetvar company slug from a slug or company root URL.

    Accepted examples:
    - ``istikbal``
    - ``cilek-mobilya``
    - ``https://www.sikayetvar.com/cilek-mobilya``
    - ``sikayetvar.com/konfor-mobilya/``

    Category, complaint-detail and other deeper URLs are deliberately rejected;
    Mobilitik needs the company root page so pagination is unambiguous.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Firma alanı boş bırakılamaz.")

    if "://" not in raw and (raw.startswith("sikayetvar.com/") or raw.startswith("www.sikayetvar.com/")):
        raw = "https://" + raw

    if "://" in raw:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            raise ValueError("Yalnızca sikayetvar.com firma ana sayfası kullanılabilir.")

        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) != 1:
            raise ValueError(
                "Firma ana sayfasının kök linkini kullanın; kategori veya şikâyet detay linki kullanmayın."
            )
        slug = segments[0].lower()
    else:
        slug = raw.strip("/").lower()

    if not SLUG_RE.fullmatch(slug):
        raise ValueError("Geçerli bir Şikayetvar firma adı veya firma ana sayfası linki girin.")

    return slug


def company_root_url(value: str) -> str:
    """Return the canonical Şikayetvar root URL for a company input."""
    slug = normalize_company_input(value)
    return f"https://www.sikayetvar.com/{slug}"

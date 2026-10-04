from __future__ import annotations

from pathlib import Path


# Mobilitik projesinin kök dizini (mobilitik paketinin bir üst dizini)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Varsayılan SQLite veritabanı yolu
DEFAULT_DB_PATH = PROJECT_ROOT / "mobilitik.db"

# Varsayılan kategori kuralları JSON dosyası yolu
DEFAULT_CATEGORIES_PATH = PROJECT_ROOT / "mobilitik_categories.json"

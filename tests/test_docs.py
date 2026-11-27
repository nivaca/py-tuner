"""La documentación sigue al programa: los manuales dicen la versión del programa, sus imágenes existen en los
dos idiomas, sus PDF están hechos, y los registros de cambios y las descripciones tienen la versión."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from py_tuner import __version__

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


@pytest.mark.parametrize("lang", ["en", "es"])
def test_manual(lang):
    tex = (DOCS / f"MANUAL_{lang}.tex").read_text(encoding="utf-8")
    assert re.search(r"\\newcommand\*\{\\version\}\{([^}]+)\}", tex)[1] == __version__
    shots = re.findall(r"\\shot\{([^}]+)\}", tex)
    assert shots and all(name.endswith(f"_{lang}") for name in shots)
    for name in shots:
        assert (DOCS / "img" / "manual" / f"{name}.png").is_file() or (DOCS / "img" / f"{name}.png").is_file(), name
    assert (DOCS / f"MANUAL_{lang}.pdf").read_bytes()[:5] == b"%PDF-"


def test_manuals_have_the_same_pictures():
    names = {lang: [n.rsplit("_", 1)[0] for n in re.findall(r"\\shot\{([^}]+)\}",
                                                             (DOCS / f"MANUAL_{lang}.tex").read_text())]
             for lang in ("en", "es")}
    assert names["en"] == names["es"]


def test_changelogs_and_descriptions():
    for name in ("CHANGELOG.md", "CHANGELOG_es.md"):
        assert f"## {__version__} — " in (ROOT / name).read_text(encoding="utf-8"), name
    assert (DOCS / "DESCRIPCIÓN_es.md").read_text(encoding="utf-8").startswith(f"# py-tuner {__version__}:")
    sections = re.split(r"(?m)^(?=## )", (DOCS / "DESCRIPCIÓN_es.md").read_text(encoding="utf-8"))[1:]
    assert [s.splitlines()[0] for s in sections] == ["## Análisis", "## Diseño", "## Implementación",
                                                     "## Validación", "## Plataforma", "## Ambiente"]
    assert all(len(s) <= 4000 for s in sections)


def test_readme_links():
    for name in ("README.md", "README_es.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(((?:docs/|CHANGELOG|packaging/)[^)#]+)\)", text):
            assert (ROOT / target.replace("%C3%93", "Ó")).exists(), f"{name}: {target}"

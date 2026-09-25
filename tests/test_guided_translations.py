"""Static translation and config-flow contract tests for guided setup."""
from __future__ import annotations

import json
from pathlib import Path
import re


INTEGRATION_DIR = Path(__file__).parents[1] / "custom_components" / "teamtracker"
TRANSLATIONS = INTEGRATION_DIR / "translations"

REQUIRED_MAJOR_LOCALES = {
    "ar",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "es_419",
    "fi",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "nb",
    "nl",
    "pl",
    "pt",
    "pt-BR",
    "ro",
    "ru",
    "sk",
    "sv",
    "th",
    "tr",
    "uk",
    "vi",
    "zh-Hans",
    "zh-Hant",
}


def _leaves(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            result.update(_leaves(child, path))
    else:
        result[prefix] = value
    return result


def _placeholders(value: str) -> set[str]:
    return set(
        re.findall(
            r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})",
            str(value),
        )
    )


def test_translation_catalogs_cover_major_languages_and_match_english_shape():
    """Every shipped locale has the same keys/placeholders as English."""
    locale_files = {path.stem for path in TRANSLATIONS.glob("*.json")}
    assert REQUIRED_MAJOR_LOCALES <= locale_files

    english = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    strings = json.loads((INTEGRATION_DIR / "strings.json").read_text(encoding="utf-8"))
    assert strings == english

    english_leaves = _leaves(english)
    for path in sorted(TRANSLATIONS.glob("*.json")):
        translated = json.loads(path.read_text(encoding="utf-8"))
        translated_leaves = _leaves(translated)
        assert translated_leaves.keys() == english_leaves.keys(), path.name
        for key, english_value in english_leaves.items():
            assert _placeholders(translated_leaves[key]) == _placeholders(
                english_value
            ), f"{path.name}: {key}"


def test_greek_all_competitions_translation():
    """Greek is explicitly supported, including the All option."""
    greek = json.loads((TRANSLATIONS / "el.json").read_text(encoding="utf-8"))
    assert (
        greek["selector"]["competition"]["options"]["all_competitions"]
        == "Όλες οι διοργανώσεις"
    )


def test_intermediate_steps_are_next_and_competition_is_dropdown():
    """Keep the requested Next/Submit flow and dropdown competition selector."""
    source = (INTEGRATION_DIR / "config_flow.py").read_text(encoding="utf-8")
    assert 'step_id="user"' in source
    assert 'step_id="search"' in source
    assert 'step_id="select_competitor"' in source
    assert 'step_id="competition"' in source
    assert "last_step=False" in source
    assert "last_step=True" in source
    competition_block = source[
        source.index("async def async_step_competition") : source.index(
            "async def async_step_custom_api"
        )
    ]
    assert "_dropdown(" in competition_block
    assert "vol.In" not in competition_block

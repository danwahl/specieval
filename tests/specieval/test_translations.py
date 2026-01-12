"""Tests for the translations module."""

import pytest
from specieval.translations import Language, Translations


def test_translations_loads_default():
    """Test that translations can be loaded from the default path."""
    translations = Translations()

    # Should have loaded successfully
    assert translations.df is not None
    assert len(translations.df) > 0


def test_translations_loads_reverse():
    """Test that reverse translations can be loaded."""
    translations = Translations(reverse=True)

    assert translations.df is not None
    assert len(translations.df) > 0


def test_get_string_english():
    """Test getting a string in English."""
    translations = Translations()

    # Get one of the speciesism questions
    result = translations.get_string("spec_1", Language.ENGLISH)

    assert result is not None
    assert len(result) > 0
    assert isinstance(result, str)


def test_get_string_other_languages():
    """Test getting strings in various languages."""
    translations = Translations()

    languages = [
        Language.GERMAN,
        Language.FRENCH,
        Language.SPANISH,
        Language.CHINESE,
        Language.JAPANESE,
    ]

    for lang in languages:
        result = translations.get_string("spec_1", lang)
        assert result is not None
        assert len(result) > 0


def test_get_string_with_format_args():
    """Test string formatting with arguments."""
    translations = Translations()

    # The cot_template contains {prompt} and {levels} placeholders
    result = translations.get_string(
        "cot_template", Language.ENGLISH, prompt="Test prompt", levels=7
    )

    assert "Test prompt" in result
    assert "7" in result


def test_get_string_missing_id():
    """Test that missing string IDs raise KeyError."""
    translations = Translations()

    with pytest.raises(KeyError):
        translations.get_string("nonexistent_string_id", Language.ENGLISH)


def test_language_enum_values():
    """Test that language enum has expected values."""
    assert str(Language.ENGLISH) == "en"
    assert str(Language.GERMAN) == "de"
    assert str(Language.FRENCH) == "fr"
    assert str(Language.SPANISH) == "es"
    assert str(Language.CHINESE) == "zh"


def test_all_languages_have_core_strings():
    """Test that all languages have translations for core string IDs."""
    translations = Translations()

    core_strings = [
        "spec_1",
        "spec_2",
        "spec_3",
        "spec_4",
        "likert_scale",
        "cot_template",
    ]

    for lang in Language:
        for string_id in core_strings:
            result = translations.get_string(string_id, lang)
            assert result is not None, f"Missing {string_id} for {lang}"
            assert len(result) > 0, f"Empty {string_id} for {lang}"

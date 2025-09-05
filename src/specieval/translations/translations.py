"""Translation support for the SpeciEval project."""

from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


class Language(str, Enum):
    """Supported languages for translations."""

    ENGLISH = "en"
    GERMAN = "de"
    FRENCH = "fr"
    SPANISH = "es"
    CHINESE = "zh"
    JAPANESE = "ja"
    POLISH = "pl"
    PORTUGUESE = "pt"
    DUTCH = "nl"
    RUSSIAN = "ru"
    ITALIAN = "it"
    INDONESIAN = "id"
    KOREAN = "ko"
    MALAY = "ms"
    THAI = "th"

    def __str__(self) -> str:
        return self.value


class Translations:
    """Manages translations for the SpeciEval project."""

    def __init__(self, path: Path = None, reverse: bool = False):
        """Initialize the translations manager.

        Args:
            path: Path to the translations CSV file. If None, uses default path.
            reverse: Whether to use reverse translations.
        """
        if path is None:
            if reverse:
                path = Path(__file__).parent / "data" / "translations-reverse.csv"
            else:
                path = Path(__file__).parent / "data" / "translations.csv"

        self.df = pd.read_csv(path, comment="#")

    def get_string(
        self, string_id: str, language: Language = Language.ENGLISH, **format_args: Any
    ) -> str:
        """Get a translated string by ID and language, with optional formatting.

        Args:
            string_id: The identifier for the string
            language: The language to use
            **format_args: Optional formatting arguments to apply to the string

        Returns:
            The translated string

        Raises:
            KeyError: If the string ID doesn't exist
            ValueError: If the translation is missing for the specified language
        """
        lang_code = str(language)

        # Find the row with the matching ID
        row = self.df[self.df["string_id"] == string_id]

        if row.empty:
            raise KeyError(f"String ID not found: {string_id}")

        if lang_code not in self.df.columns:
            raise ValueError(
                f"Language {lang_code} is not available in translations file"
            )

        value = row[lang_code].iloc[0]

        if pd.isna(value):
            raise ValueError(f"No translation for {string_id} in {lang_code}")

        # Apply formatting if needed
        if format_args:
            value = value.format(**format_args)

        return value

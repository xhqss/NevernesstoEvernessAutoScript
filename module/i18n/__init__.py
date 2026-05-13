"""
Internationalization (i18n) module for al-script.
Supports JSON-based translation files and GUI language switching.
Adapted from ok-script ok/gui/i18n/ and ok/util/i18n.py
"""

import json
import os

from module.util.file import get_path_relative_to_exe


class Translator:
    """
    Simple JSON-based translator for i18n support.

    Usage:
        tr = Translator('zh_CN')
        print(tr('Start'))  # -> 开始
    """

    def __init__(self, lang='en'):
        self.lang = lang
        self._translations = {}
        self._fallback = {}
        self._load_translations()

    def _load_translations(self):
        """Load translation files for current language and fallback (en)."""
        # Load fallback (English)
        self._fallback = self._load_file('en')

        # Load target language
        if self.lang != 'en':
            self._translations = self._load_file(self.lang)

    def _load_file(self, lang):
        """Load a translation JSON file."""
        paths = [
            get_path_relative_to_exe(f'module/i18n/{lang}.json'),
            get_path_relative_to_exe(f'module/i18n/{lang}.json'),
            os.path.join(os.path.dirname(__file__), f'{lang}.json'),
        ]
        for path in paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass
        return {}

    def translate(self, key, default=None):
        """Translate a key to the current language."""
        if key in self._translations:
            return self._translations[key]
        if key in self._fallback:
            return self._fallback[key]
        return default or key

    def __call__(self, key, default=None):
        return self.translate(key, default)

    def set_language(self, lang):
        """Switch to a different language."""
        self.lang = lang
        self._translations = {}
        self._load_translations()

    def available_languages(self):
        """Get list of available language codes."""
        i18n_dir = os.path.dirname(__file__)
        langs = []
        for f in os.listdir(i18n_dir):
            if f.endswith('.json'):
                langs.append(f[:-5])
        return sorted(langs) if langs else ['en']


# Global translator instance
translator = Translator('en')


def tr(key, default=None):
    """Shorthand for translator.translate()."""
    return translator.translate(key, default)


def set_language(lang):
    """Set global language."""
    translator.set_language(lang)

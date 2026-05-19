"""
al-script GUI launcher.
Start with: python -m module.gui.launcher [config_name]
"""

import sys
import os


def _build_config(config_name):
    """Build full runtime config, merging game-specific config if available."""
    config = {
        'config_name': config_name,
        'use_gui': True,
        'config_folder': 'config',
    }

    try:
        from module.neverness.config import make_config
        game_config = make_config()
        _deep_merge(config, game_config)
    except ImportError:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()

    return config


def _deep_merge(base, override):
    """Recursively merge override dict into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def main():
    """Launch the al-script GUI application."""
    config_name = 'neas1'
    if len(sys.argv) > 1:
        config_name = sys.argv[1]
    config_name = os.environ.get('AL_CONFIG', config_name)

    from module.app import App
    config = _build_config(config_name)
    app = App(config=config)
    app.start()


if __name__ == '__main__':
    main()

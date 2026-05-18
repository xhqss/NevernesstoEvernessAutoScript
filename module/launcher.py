"""
al-script entry point.
Run with: python -m module.launcher [config_name]
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

    # Detect game module and merge its config
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
    """Main entry point for al-script."""
    config_name = 'template'
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ('-h', '--help'):
            print('al-script v0.1.0')
            print('Usage: al-script [config_name]')
            print('       al-script-gui [config_name]')
            print()
            print('Environment:')
            print('  AL_CONFIG    Config name (default: template)')
            return
        config_name = arg

    # Allow override via env
    config_name = os.environ.get('AL_CONFIG', config_name)

    from module.app import App
    config = _build_config(config_name)
    app = App(config=config)
    app.start()


if __name__ == '__main__':
    main()

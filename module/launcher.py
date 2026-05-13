"""
al-script entry point.
Run with: python -m module.launcher [config_name]
"""

import sys
import os


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
    app = App(config={'config_name': config_name, 'use_gui': True})
    app.start()


if __name__ == '__main__':
    main()

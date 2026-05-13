"""
al-script GUI launcher.
Start with: python -m module.gui.launcher [config_name]
"""

import sys
import os


def main():
    """Launch the al-script GUI application."""
    config_name = 'template'
    if len(sys.argv) > 1:
        config_name = sys.argv[1]
    config_name = os.environ.get('AL_CONFIG', config_name)

    from module.app import App
    app = App(config={'config_name': config_name, 'use_gui': True})
    app.start()


if __name__ == '__main__':
    main()

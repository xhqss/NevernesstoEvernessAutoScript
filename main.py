"""NevernesstoEvernessAutoScript - Game automation for Neverness to Everness (异环).

Built on the al-script framework.
"""
import sys
import os

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Ensure al-script is accessible
_ALSCRIPT_PATH = os.path.join(os.path.dirname(_PROJECT_ROOT), "al-script")
if os.path.isdir(_ALSCRIPT_PATH) and _ALSCRIPT_PATH not in sys.path:
    sys.path.insert(0, _ALSCRIPT_PATH)


def main():
    from module.app import App
    from module.neverness.config import make_config

    cfg = make_config()
    app = App(config=cfg)
    app.start()


if __name__ == "__main__":
    main()

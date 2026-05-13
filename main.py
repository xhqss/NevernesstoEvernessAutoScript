"""NevernesstoEvernessAutoScript - Game automation for Neverness to Everness (异环).

Built on the al-script framework.
"""
import sys
import os

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def main():
    """Main entry point for Neverness to Everness automation."""
    from module.launcher import main as launcher_main
    launcher_main()


if __name__ == "__main__":
    main()

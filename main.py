#!/usr/bin/env python3
"""
al-script quick launcher.
Run with: python main.py [config_name]
"""

import sys
import os

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(__file__))
    from module.launcher import main
    main()

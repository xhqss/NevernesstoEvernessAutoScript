"""
Application control - launch, kill, and manage application lifecycle.
"""

import subprocess
import time

from module.util.logger import logger


class AppControl:
    """Application lifecycle control."""
    
    def __init__(self, config=None):
        self.config = config or {}
    
    def launch(self, package=None, activity=None):
        """Launch an application."""
        if package:
            subprocess.run(
                ['adb', 'shell', 'monkey', '-p', package, '-c',
                 'android.intent.category.LAUNCHER', '1'],
                capture_output=True, timeout=10
            )
        elif activity:
            subprocess.run(
                ['adb', 'shell', 'am', 'start', '-n', activity],
                capture_output=True, timeout=10
            )
    
    def kill(self, package=None):
        """Kill an application."""
        if package:
            subprocess.run(
                ['adb', 'shell', 'am', 'force-stop', package],
                capture_output=True, timeout=5
            )
    
    def is_running(self, package):
        """Check if an application is running."""
        result = subprocess.run(
            ['adb', 'shell', 'pidof', package],
            capture_output=True, text=True, timeout=5
        )
        return bool(result.stdout.strip())

"""al-script deploy installer - main entry point for deployment package.

Usage: python -m deploy.installer
"""

from deploy.patch import pre_checks
from deploy.config import ExecutionError
from deploy.git import GitManager
from deploy.pip import PipManager


class Installer(GitManager, PipManager):
    """Main installer for al-script deployment package."""

    def install(self):
        try:
            pre_checks()
            self.git_install()
            self.pip_install()
        except ExecutionError:
            exit(1)


if __name__ == '__main__':
    Installer().install()

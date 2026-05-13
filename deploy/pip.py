"""Pip manager - installs Python dependencies using embedded pip."""

import os

from deploy.config import DeployConfig
from deploy.logger import logger
from deploy.utils import cached_property


class PipManager(DeployConfig):
    @cached_property
    def python(self):
        return self.filepath('PythonExecutable')

    def pip_install(self):
        logger.hr('Install Dependencies', 0)
        if not self.InstallDependencies:
            logger.info('InstallDependencies disabled, skip')
            return

        req_file = self.filepath('RequirementsFile')
        if not os.path.exists(req_file):
            logger.warning(f'Requirements file not found: {req_file}')
            return

        arg = ''
        if self.PypiMirror:
            arg += f' -i {self.PypiMirror}'

        self.execute(f'"{self.python}" -m pip install -r "{req_file}" {arg}')

    def pip_install_updater(self):
        """Install minimal packages needed for the update system."""
        logger.hr('Install Updater Dependencies', 1)
        arg = ''
        if self.PypiMirror:
            arg += f' -i {self.PypiMirror}'
        self.execute(f'"{self.python}" -m pip install requests pyyaml {arg}', allow_failure=True)

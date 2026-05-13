"""Deploy config - reads deploy.yaml and provides attribute access."""

import copy
import os
from typing import Optional, Union

from deploy.logger import logger
from deploy.utils import DEPLOY_CONFIG, DEPLOY_TEMPLATE, cached_property, poor_yaml_read, poor_yaml_write


class ExecutionError(Exception):
    pass


class ConfigModel:
    # Git
    Repository: str = 'https://github.com/your-org/al-script'
    Branch: str = 'master'
    GitExecutable: str = './toolkit/Git/mingw64/bin/git.exe'
    GitProxy: Optional[str] = None
    SSLVerify: bool = True
    AutoUpdate: bool = True
    KeepLocalChanges: bool = False

    # Python
    PythonExecutable: str = './toolkit/python.exe'
    PypiMirror: Optional[str] = None
    InstallDependencies: bool = True
    RequirementsFile: str = 'requirements.txt'

    # Adb
    AdbExecutable: str = './toolkit/Lib/site-packages/adbutils/binaries/adb.exe'
    ReplaceAdb: bool = True
    AutoConnect: bool = True
    InstallUiautomator2: bool = True

    # Launcher
    ConfigName: str = 'template'
    GuiMode: bool = True

    # Update
    EnableReload: bool = True
    CheckUpdateInterval: int = 5
    AutoRestartTime: str = '03:50'

    # Misc
    Debug: bool = False


class DeployConfig(ConfigModel):
    def __init__(self, file=DEPLOY_CONFIG):
        self.file = file
        self.config = {}
        self.read()
        self.write()
        self.show_config()

    def show_config(self):
        logger.hr('Show deploy config', 1)
        for k, v in self.config.items():
            if self.config_template.get(k) == v:
                continue
            logger.info(f'  {k}: {v}')
        logger.info('  (rest are defaults)')

    def read(self):
        self.config = poor_yaml_read(DEPLOY_TEMPLATE)
        self.config_template = copy.deepcopy(self.config)
        user_config = poor_yaml_read(self.file)
        for section in user_config:
            if isinstance(user_config[section], dict):
                self.config.setdefault(section, {})
                self.config[section].update(user_config[section])
            else:
                self.config[section] = user_config[section]

        # Flatten: take keys from Git, Python, Adb, Launcher, Update, Misc sections
        for section in self.config:
            if isinstance(self.config[section], dict):
                for key, value in self.config[section].items():
                    if hasattr(self, key):
                        super().__setattr__(key, value)
            elif hasattr(self, section):
                super().__setattr__(section, self.config[section])

    def write(self):
        poor_yaml_write(self.config, self.file)

    def filepath(self, key):
        return (
            os.path.abspath(os.path.join(self.root_filepath, self.config.get(key, '')))
            .replace('\\', '/')
        )

    @cached_property
    def root_filepath(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..')).replace('\\', '/')

    def execute(self, command, allow_failure=False, output=True):
        command = command.replace('\\', '/')
        if not output:
            command = command + ' >nul 2>nul'
        logger.info(f'  $ {command}')
        error_code = os.system(command)
        if error_code:
            if allow_failure:
                logger.info(f'  [allowed failure] code={error_code}')
                return False
            else:
                logger.info(f'  [failure] code={error_code}')
                self.show_error(command)
                raise ExecutionError
        else:
            logger.info(f'  [success]')
            return True

    def show_error(self, command=None):
        logger.hr('Update failed', 0)
        self.show_config()
        logger.info('')
        logger.info(f'Last command: {command}')
        logger.info('Check config/deploy.yaml and re-launch.')

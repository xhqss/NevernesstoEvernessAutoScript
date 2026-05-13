"""Pre-startup patches and checks for al-script deploy."""

import os
import re

from deploy.logger import logger


def check_running_directory():
    """Prevent running from compressed temp directories."""
    file = __file__.replace('\\', '/')
    if 'Temp/360zip' in file:
        logger.critical('Please extract the al-script archive before installing.')
        exit(1)
    if 'Temp/Rar' in file or 'Local/Temp' in file:
        logger.critical('Please extract the al-script archive before installing.')
        exit(1)


def patch_uiautomator2():
    """Patch uiautomator2 to use local asset cache and disable minicap."""
    cache_dir = './toolkit/Lib/site-packages/uiautomator2cache/cache'
    init_file = './toolkit/Lib/site-packages/uiautomator2/init.py'

    if not os.path.exists(init_file):
        logger.info('uiautomator2 not installed, skip patching')
        return

    modified = False
    with open(init_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Patch minicap_urls
    if re.search(r'self.minicap_urls', content):
        content = re.sub(r'self.minicap_urls', '[]', content)
        modified = True
        logger.info('uiautomator2 minicap_urls patched')

    # Patch appdir to use local cache
    if os.path.exists(cache_dir):
        appdir = "os.path.abspath(os.path.join(__file__, '../../uiautomator2cache'))"
        if re.search(r'appdir ?=(.*)\n', content):
            content = re.sub(r'appdir ?=.*\n', f'appdir = {appdir}\n', content)
            modified = True
            logger.info('uiautomator2 appdir patched')

    if modified:
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info('uiautomator2 patches saved')


def pre_checks():
    """Run all pre-startup checks and patches."""
    check_running_directory()
    patch_uiautomator2()

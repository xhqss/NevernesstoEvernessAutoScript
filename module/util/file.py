"""File path utility functions."""

import os
import sys


def get_path_relative_to_exe(path):
    """Get path relative to executable or current working directory."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.getcwd()
    return os.path.join(base, path)


def get_root_path():
    """Get the root directory of the al-script installation.

    In deployment mode, this is the directory containing toolkit/.
    In dev mode, this is the parent of the module directory.
    """
    # Check if running inside a deployment package (has toolkit/python.exe)
    cwd = os.getcwd()
    toolkit_python = os.path.join(cwd, 'toolkit', 'python.exe')
    if os.path.exists(toolkit_python):
        return cwd

    # Check parent directories
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        toolkit_python = os.path.join(current, 'toolkit', 'python.exe')
        if os.path.exists(toolkit_python):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # Fallback: module's grandparent directory
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def get_toolkit_path(subpath=''):
    """Get path within the toolkit directory. Returns None if toolkit not found."""
    root = get_root_path()
    toolkit = os.path.join(root, 'toolkit')
    if not os.path.isdir(toolkit):
        return None
    if subpath:
        return os.path.join(toolkit, subpath.replace('/', os.sep))
    return toolkit


def get_python_exe():
    """Get the Python executable path (embedded toolkit python or system python)."""
    toolkit = get_toolkit_path('python.exe')
    if toolkit and os.path.exists(toolkit):
        return toolkit
    return sys.executable


def get_git_exe():
    """Get the Git executable path (embedded or system)."""
    toolkit = get_toolkit_path('Git/mingw64/bin/git.exe')
    if toolkit and os.path.exists(toolkit):
        return toolkit
    return 'git'


def get_adb_exe():
    """Get the ADB executable path (embedded or system)."""
    toolkit = get_toolkit_path('Lib/site-packages/adbutils/binaries/adb.exe')
    if toolkit and os.path.exists(toolkit):
        return toolkit
    return 'adb'


def delete_if_exists(path):
    """Delete file if it exists."""
    if os.path.exists(path):
        os.remove(path)


def install_path_isascii(path):
    """Check if install path contains only ASCII characters."""
    try:
        path.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

"""
Git-based update system for al-script.
Supports version checking, downloading, and updating from GitHub releases.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime

import requests

from module.util.file import get_path_relative_to_exe
from module.util.logger import logger


class GitUpdater:
    """
    Git-based auto-updater.
    
    Checks for new versions from GitHub releases, downloads and applies updates.
    
    Args:
        repo_url: GitHub repo URL (e.g., 'https://api.github.com/repos/user/repo')
        current_version: Current version string.
        exit_event: Threading event for graceful shutdown.
    """
    
    def __init__(self, repo_url=None, current_version='0.0.0', exit_event=None):
        self.repo_url = repo_url or 'https://api.github.com/repos/your-org/al-script'
        self.current_version = current_version
        self.exit_event = exit_event
        self.latest_version = None
        self.latest_download_url = None
        self.update_available = False
        self.changelog = ''
    
    def check_for_updates(self):
        """
        Check GitHub API for newer releases.
        
        Returns:
            bool: True if update is available.
        """
        try:
            # Get latest release from GitHub API
            repo_api = self.repo_url.replace('github.com', 'api.github.com/repos')
            if 'api.github.com' not in repo_api:
                repo_api = f'https://api.github.com/repos/{self.repo_url}/releases/latest'
            
            headers = {'Accept': 'application/vnd.github.v3+json'}
            resp = requests.get(repo_api, headers=headers, timeout=10)
            
            if resp.status_code != 200:
                logger.warning(f'GitHub API returned {resp.status_code}')
                return False
            
            data = resp.json()
            tag = data.get('tag_name', '').lstrip('v')
            self.latest_version = tag
            self.changelog = data.get('body', '')
            
            # Find the right asset
            assets = data.get('assets', [])
            for asset in assets:
                name = asset.get('name', '')
                if name.endswith('.zip') or name.endswith('.exe'):
                    self.latest_download_url = asset.get('browser_download_url')
                    break
            
            # Compare versions
            self.update_available = self._compare_versions(
                self.latest_version, self.current_version
            ) > 0
            
            if self.update_available:
                logger.info(f'Update available: {self.current_version} -> {self.latest_version}')
            else:
                logger.info(f'Already up to date: {self.current_version}')
            
            return self.update_available
            
        except Exception as e:
            logger.error(f'Failed to check updates: {e}')
            return False
    
    def download_update(self, progress_callback=None):
        """
        Download the latest update.
        
        Args:
            progress_callback: Optional callback(downloaded, total) for progress.
            
        Returns:
            str: Path to downloaded file, or None on failure.
        """
        if not self.latest_download_url:
            logger.error('No download URL available')
            return None
        
        try:
            temp_dir = tempfile.mkdtemp(prefix='al_update_')
            temp_file = os.path.join(temp_dir, 'update.zip')
            
            resp = requests.get(self.latest_download_url, stream=True, timeout=30)
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if self.exit_event and self.exit_event.is_set():
                        logger.info('Update download cancelled')
                        return None
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded, total)
            
            logger.info(f'Downloaded update to {temp_file} ({total} bytes)')
            
            if temp_file.endswith('.zip'):
                extract_dir = os.path.join(temp_dir, 'extracted')
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(temp_file, 'r') as zf:
                    zf.extractall(extract_dir)
                return extract_dir
            
            return temp_file
            
        except Exception as e:
            logger.error(f'Failed to download update: {e}')
            return None
    
    def apply_update(self, source_dir):
        """
        Apply downloaded update by replacing current files.
        
        Args:
            source_dir: Directory containing updated files.
            
        Returns:
            bool: True if successful.
        """
        try:
            current_dir = get_path_relative_to_exe()
            
            # Backup current version
            backup_dir = os.path.join(current_dir, '.backup')
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            
            # Copy new files
            for item in os.listdir(source_dir):
                src = os.path.join(source_dir, item)
                dst = os.path.join(current_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            
            logger.info(f'Update applied: {self.current_version} -> {self.latest_version}')
            
            # Write new version
            self._save_current_version()
            
            return True
            
        except Exception as e:
            logger.error(f'Failed to apply update: {e}')
            return False
    
    def _compare_versions(self, v1, v2):
        """
        Compare two version strings.
        Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal.
        """
        try:
            parts1 = [int(x) for x in str(v1).split('.')]
            parts2 = [int(x) for x in str(v2).split('.')]
            
            # Pad to same length
            while len(parts1) < len(parts2):
                parts1.append(0)
            while len(parts2) < len(parts1):
                parts2.append(0)
            
            for a, b in zip(parts1, parts2):
                if a > b:
                    return 1
                elif a < b:
                    return -1
            return 0
        except (ValueError, AttributeError):
            return 0
    
    def _save_current_version(self):
        """Save current version to a file."""
        version_file = get_path_relative_to_exe('version.json')
        try:
            with open(version_file, 'w') as f:
                json.dump({
                    'version': self.latest_version or self.current_version,
                    'updated_at': datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.warning(f'Failed to save version file: {e}')


def check_repo(path, url):
    """Check if a git repo exists at path."""
    try:
        import git
        if os.path.exists(os.path.join(path, '.git')):
            return git.Repo(path)
    except Exception:
        pass
    return None


def delete_folder_native(path):
    """Delete a folder using native Windows method."""
    try:
        shutil.rmtree(path)
    except Exception:
        try:
            subprocess.run(['cmd', '/c', 'rmdir', '/s', '/q', path],
                           capture_output=True, timeout=30)
        except Exception:
            pass

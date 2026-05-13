"""
Windows emulator detection - adapted from Alas module/device/platform/emulator_windows.py
Detects installed Android emulators and their instances on Windows.
"""

import os
import re
import winreg
from dataclasses import dataclass

from module.device.platform.emulator_base import (
    EmulatorBase, EmulatorInstanceBase, EmulatorManagerBase,
    cached_property, iter_folder, remove_duplicated_path, abspath
)


@dataclass
class RegValue:
    name: str
    value: str
    typ: int


def list_reg(reg):
    """List all values in a registry key."""
    rows = []
    index = 0
    try:
        while True:
            value = RegValue(*winreg.EnumValue(reg, index))
            index += 1
            rows.append(value)
    except OSError:
        pass
    return rows


def list_key(reg):
    """List all subkeys in a registry key."""
    rows = []
    index = 0
    try:
        while True:
            value = winreg.EnumKey(reg, index)
            index += 1
            rows.append(value)
    except OSError:
        pass
    return rows


class EmulatorInstance(EmulatorInstanceBase):
    """Windows emulator instance."""
    
    @cached_property
    def emulator(self):
        return Emulator(self.path)


class Emulator(EmulatorBase):
    """Windows emulator type detection."""
    
    @cached_property
    def type(self):
        result = self.path_to_type(self.path)
        return result if result else 'Unknown'
    
    @classmethod
    def path_to_type(cls, path: str) -> str:
        """
        Detect emulator type from executable path.
        """
        folder, exe = os.path.split(path)
        folder, dir1 = os.path.split(folder)
        folder, dir2 = os.path.split(folder)
        exe = exe.lower()
        dir1 = dir1.lower()
        dir2 = dir2.lower()
        
        if exe == 'nox.exe':
            if dir2 == 'nox':
                return cls.NoxPlayer
            elif dir2 == 'nox64':
                return cls.NoxPlayer64
            else:
                return cls.NoxPlayer
        
        if exe in ['bluestacks.exe', 'bluestacksgp.exe']:
            if dir1 in ['bluestacks', 'bluestacks_cn', 'bluestackscn']:
                return cls.BlueStacks4
            elif dir1 in ['bluestacks_nxt', 'bluestacks_nxt_cn']:
                return cls.BlueStacks5
            else:
                return cls.BlueStacks4
        
        if exe == 'hd-player.exe':
            if dir1 in ['bluestacks', 'bluestacks_cn']:
                return cls.BlueStacks4
            elif dir1 in ['bluestacks_nxt', 'bluestacks_nxt_cn']:
                return cls.BlueStacks5
            else:
                return cls.BlueStacks5
        
        if exe == 'dnplayer.exe':
            if dir1 == 'ldplayer':
                return cls.LDPlayer3
            elif dir1 == 'ldplayer4':
                return cls.LDPlayer4
            elif dir1 == 'ldplayer9':
                return cls.LDPlayer9
            elif dir1 == 'ldplayer14':
                return cls.LDPlayer14
            else:
                return cls.LDPlayer3
        
        if exe == 'nemuplayer.exe':
            if dir2 == 'nemu':
                return cls.MuMuPlayer
            elif dir2 == 'nemu9':
                return cls.MuMuPlayerX
            else:
                return cls.MuMuPlayer
        
        if exe in ['mumuplayer.exe', 'mumunxmain.exe']:
            return cls.MuMuPlayer9
        
        if exe == 'memu.exe':
            return cls.MEmuPlayer
        
        return ''
    
    @staticmethod
    def multi_to_single(exe: str):
        """Convert multi-instance manager to single instance executable."""
        if 'HD-MultiInstanceManager.exe' in exe:
            yield exe.replace('HD-MultiInstanceManager.exe', 'HD-Player.exe')
            yield exe.replace('HD-MultiInstanceManager.exe', 'Bluestacks.exe')
        elif 'MultiPlayerManager.exe' in exe:
            yield exe.replace('MultiPlayerManager.exe', 'Nox.exe')
        elif 'dnmultiplayer.exe' in exe:
            yield exe.replace('dnmultiplayer.exe', 'dnplayer.exe')
        elif 'NemuMultiPlayer.exe' in exe:
            yield exe.replace('NemuMultiPlayer.exe', 'NemuPlayer.exe')
        elif 'MuMuMultiPlayer.exe' in exe:
            yield exe.replace('MuMuMultiPlayer.exe', 'MuMuPlayer.exe')
        elif 'MuMuManager.exe' in exe:
            yield exe.replace('MuMuManager.exe', 'MuMuPlayer.exe')
        elif 'MEmuConsole.exe' in exe:
            yield exe.replace('MEmuConsole.exe', 'MEmu.exe')
        else:
            yield exe
    
    @staticmethod
    def single_to_console(exe: str):
        """Convert single instance executable to its console."""
        if 'MuMuPlayer.exe' in exe:
            return exe.replace('MuMuPlayer.exe', 'MuMuManager.exe')
        elif 'MuMuNxMain.exe' in exe:
            return exe.replace('MuMuNxMain.exe', 'MuMuManager.exe')
        elif 'LDPlayer.exe' in exe:
            return exe.replace('LDPlayer.exe', 'ldconsole.exe')
        elif 'dnplayer.exe' in exe:
            return exe.replace('dnplayer.exe', 'ldconsole.exe')
        elif 'Bluestacks.exe' in exe:
            return exe.replace('Bluestacks.exe', 'bsconsole.exe')
        elif 'MEmu.exe' in exe:
            return exe.replace('MEmu.exe', 'memuc.exe')
        else:
            return exe
    
    @staticmethod
    def vbox_file_to_serial(file: str) -> str:
        """Extract ADB serial from VirtualBox .vbox file."""
        regex = re.compile(r'<*?hostport="(.*?)".*?guestport="5555"/>')
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f.readlines():
                    match = regex.search(line)
                    if match:
                        return f'127.0.0.1:{match.group(1)}'
        except (FileNotFoundError, PermissionError):
            pass
        return ''


class EmulatorManager(EmulatorManagerBase):
    """Manages detection of all installed emulators."""
    
    @classmethod
    def all_emulators(cls):
        """Detect all installed emulators on this PC."""
        results = {}
        for path in cls.iter_emulator_paths():
            emu_type = Emulator.path_to_type(path)
            if emu_type and emu_type not in results:
                results[emu_type] = Emulator(path)
        return list(results.values())
    
    @classmethod
    def all_emulator_instances(cls):
        """Detect all emulator instances on this PC."""
        results = []
        seen_serials = set()
        
        for path in cls.iter_emulator_paths():
            instances = cls.path_to_instances(path)
            for inst in instances:
                if inst.serial not in seen_serials:
                    seen_serials.add(inst.serial)
                    results.append(inst)
        
        return results
    
    @classmethod
    def iter_emulator_paths(cls):
        """Iterate all emulator executable paths found on this PC."""
        yield from cls._find_nox()
        yield from cls._find_bluestacks()
        yield from cls._find_ldplayer()
        yield from cls._find_mumu()
        yield from cls._find_memu()
    
    @classmethod
    def _find_nox(cls):
        """Find NoxPlayer installations."""
        paths = []
        # Default install paths
        candidates = [
            'C:/Program Files (x86)/Nox/bin/Nox.exe',
            'C:/Program Files (x86)/Nox64/bin/Nox.exe',
        ]
        for path in candidates:
            if os.path.exists(path):
                paths.append(abspath(path))
        
        # Registry
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                 r'SOFTWARE\WOW6432Node\Duodian\Nox')
            path = winreg.QueryValueEx(key, 'InstallDir')[0]
            for exe in ['Nox.exe', 'Nox64/bin/Nox.exe']:
                full = os.path.join(path, exe)
                if os.path.exists(full):
                    paths.append(abspath(full))
        except (FileNotFoundError, OSError):
            pass
        
        for path in cls._find_from_reg_uninstall('Nox'):
            paths.append(path)
        
        return remove_duplicated_path(paths)
    
    @classmethod
    def _find_bluestacks(cls):
        """Find BlueStacks installations."""
        paths = []
        
        # Common install paths
        candidates = [
            'C:/Program Files/BlueStacks/Bluestacks.exe',
            'C:/Program Files/BlueStacks/HD-Player.exe',
            'C:/Program Files/BlueStacks_nxt/HD-Player.exe',
            'C:/Program Files/BlueStacks_cn/HD-Player.exe',
            'C:/Program Files/BlueStacks_cn/Bluestacks.exe',
        ]
        for path in candidates:
            if os.path.exists(path):
                paths.append(abspath(path))
        
        # Registry
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r'SOFTWARE\BlueStacks')
            path = winreg.QueryValueEx(key, 'InstallDir')[0]
            for exe in ['Bluestacks.exe', 'HD-Player.exe']:
                full = os.path.join(path, exe)
                if os.path.exists(full):
                    paths.append(abspath(full))
        except (FileNotFoundError, OSError):
            pass
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r'SOFTWARE\BlueStacks_nxt')
            path = winreg.QueryValueEx(key, 'InstallDir')[0]
            for exe in ['Bluestacks.exe', 'HD-Player.exe']:
                full = os.path.join(path, exe)
                if os.path.exists(full):
                    paths.append(abspath(full))
        except (FileNotFoundError, OSError):
            pass
        
        return remove_duplicated_path(paths)
    
    @classmethod
    def _find_ldplayer(cls):
        """Find LDPlayer installations."""
        paths = []
        
        candidates = [
            'C:/LDPlayer/LDPlayer4/dnplayer.exe',
            'C:/LDPlayer/LDPlayer9/dnplayer.exe',
        ]
        for path in candidates:
            if os.path.exists(path):
                paths.append(abspath(path))
        
        # Registry
        for key_name in ['LDPlayer4', 'LDPlayer9', 'LDPlayer']:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     rf'SOFTWARE\WOW6432Node\Changzhi\{key_name}')
                path = winreg.QueryValueEx(key, 'InstallDir')[0]
                full = os.path.join(path, 'dnplayer.exe')
                if os.path.exists(full):
                    paths.append(abspath(full))
            except (FileNotFoundError, OSError):
                pass
        
        return remove_duplicated_path(paths)
    
    @classmethod
    def _find_mumu(cls):
        """Find MuMu Player installations."""
        paths = []
        
        candidates = [
            'C:/Program Files (x86)/Nemu/nemuplayer.exe',
            'C:/Program Files/Nemu/nemuplayer.exe',
            'C:/Program Files/Netease/MuMuPlayer12/shell/MuMuPlayer.exe',
            'C:/Program Files/Netease/MuMuPlayer9/nemuplayer.exe',
        ]
        for path in candidates:
            if os.path.exists(path):
                paths.append(abspath(path))
        
        # Registry
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r'SOFTWARE\WOW6432Node\Netease\Nemu')
            path = winreg.QueryValueEx(key, 'InstallDir')[0]
            full = os.path.join(path, 'nemuplayer.exe')
            if os.path.exists(full):
                paths.append(abspath(full))
        except (FileNotFoundError, OSError):
            pass
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r'SOFTWARE\WOW6432Node\Netease\MuMuPlayer12')
            path = winreg.QueryValueEx(key, 'InstallDir')[0]
            full = os.path.join(path, 'shell/MuMuPlayer.exe')
            if os.path.exists(full):
                paths.append(abspath(full))
        except (FileNotFoundError, OSError):
            pass
        
        return remove_duplicated_path(paths)
    
    @classmethod
    def _find_memu(cls):
        """Find MEmu installations."""
        paths = []
        
        candidates = [
            'C:/Program Files (x86)/Microvirt/MEmu/MEmu.exe',
        ]
        for path in candidates:
            if os.path.exists(path):
                paths.append(abspath(path))
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r'SOFTWARE\WOW6432Node\Microvirt')
            path = winreg.QueryValueEx(key, 'InstallDir')[0]
            full = os.path.join(path, 'MEmu/MEmu.exe')
            if os.path.exists(full):
                paths.append(abspath(full))
        except (FileNotFoundError, OSError):
            pass
        
        return remove_duplicated_path(paths)
    
    @staticmethod
    def _find_from_reg_uninstall(name):
        """Search for emulator in Windows uninstall registry."""
        paths = []
        uninstall_keys = [
            r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
            r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
        ]
        
        for key_path in uninstall_keys:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                for subkey_name in list_key(key):
                    try:
                        subkey = winreg.OpenKey(key, subkey_name)
                        values = list_reg(subkey)
                        install_dir = ''
                        display_name = ''
                        for v in values:
                            if v.name == 'DisplayName' and isinstance(v.value, str):
                                display_name = v.value
                            if v.name == 'InstallLocation' and isinstance(v.value, str):
                                install_dir = v.value
                        if name.lower() in display_name.lower():
                            if install_dir and os.path.isdir(install_dir):
                                paths.append(abspath(install_dir))
                    except OSError:
                        pass
            except OSError:
                pass
        
        return paths
    
    @staticmethod
    def path_to_instances(path):
        """Convert emulator executable path to instance list."""
        instances = []
        folder = os.path.dirname(path)
        
        # Check for vbox files (common for Nox, LDPlayer)
        vbox_dir = os.path.join(folder, 'vms')
        if os.path.isdir(vbox_dir):
            for vm_folder in iter_folder(vbox_dir, is_dir=True):
                vbox_file = os.path.join(vm_folder, f'{os.path.basename(vm_folder)}.vbox')
                if os.path.exists(vbox_file):
                    serial = Emulator.vbox_file_to_serial(vbox_file)
                    if serial:
                        instances.append(EmulatorInstance(
                            serial=serial,
                            name=os.path.basename(vm_folder),
                            path=path
                        ))
        
        if not instances:
            instances.append(EmulatorInstance(
                serial='127.0.0.1:5555',
                name='default',
                path=path
            ))
        
        return instances

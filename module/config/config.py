"""
Config reader - reads user JSON config and provides attribute access.
Adapted from Alas module/config/config.py
"""

import json
import os
import copy
import threading
from datetime import datetime

from module.config.deep import deep_get, deep_set
from module.config.utils import filepath_config, read_file, write_file, DEFAULT_TIME
from module.config.config_generated import GeneratedConfig
from module.util.logger import logger


class Function:
    """Represents a scheduled task function."""
    
    def __init__(self, data):
        self.enable = deep_get(data, keys="Scheduler.Enable", default=False)
        self.command = deep_get(data, keys="Scheduler.Command", default="Unknown")
        self.next_run = deep_get(data, keys="Scheduler.NextRun", default=DEFAULT_TIME)
    
    def __str__(self):
        enable = "Enable" if self.enable else "Disable"
        return f"{self.command} ({enable}, {str(self.next_run)})"
    
    __repr__ = __str__


class AlConfig(GeneratedConfig):
    """
    Configuration class that reads from user JSON config files.
    
    Usage:
        config = AlConfig('my_config')
        print(config.Emulator_Serial)
        config.Emulator_Serial = 'new_value'
    """
    
    bound = {}
    modified = {}
    stop_event = threading.Event()
    
    def __setattr__(self, key, value):
        if key in self.bound:
            path = self.bound[key]
            self.modified[path] = value
        super().__setattr__(key, value)
    
    def __init__(self, config_name, task=None):
        self.config_name = config_name
        self.data = {}
        self.task = task
        self.auto_update = True
        
        # Read user config JSON
        self.load()

        # Bind attributes (track initially loaded values, then clear)
        self._bind_attributes()
        self.modified.clear()
    
    def load(self):
        """Load user config from JSON file, correcting against args.json."""
        from module.config.config_updater import ConfigUpdater

        path = filepath_config(self.config_name)
        raw = read_file(path)
        if raw:
            # Existing user config — correct it against current args.json
            updater = ConfigUpdater()
            self.data = updater.config_update(raw, is_template=False)
            # Write back the corrected config
            write_file(path, self.data)
            logger.info(f'Loaded and corrected config: {path}')
        else:
            # No user config yet — use template as fallback
            template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'template.json')
            self.data = read_file(template_path)
            logger.info(f'Loaded config from template: {template_path}')
    
    def save(self):
        """Save modified config to JSON file, with side-effect callbacks."""
        from module.config.config_updater import ConfigUpdater

        path = filepath_config(self.config_name)
        self._apply_modifications()

        # Run save callbacks for each modified key
        updater = ConfigUpdater()
        for key, value in list(self.modified.items()):
            for cb_key, cb_value in updater.save_callback(key, value):
                deep_set(self.data, keys=cb_key.split('.'), value=cb_value)

        write_file(path, self.data)
        self.modified.clear()
        logger.info(f'Saved config: {path}')
    
    def _bind_attributes(self):
        """Bind all config attributes to bound dict for auto-save."""
        for task, groups in self.data.items():
            for group, args in groups.items():
                for arg_name, value in args.items():
                    attr_name = f'{task}_{group}_{arg_name}'
                    self.bound[attr_name] = f'{task}.{group}.{arg_name}'
                    # Set initial value
                    if isinstance(value, str) and value and not value.startswith('20'):
                        setattr(self, attr_name, value)
                    elif isinstance(value, bool):
                        setattr(self, attr_name, value)
                    elif isinstance(value, (int, float)):
                        setattr(self, attr_name, value)
                    else:
                        setattr(self, attr_name, value)
    
    def _apply_modifications(self):
        """Apply bound modifications to data dict."""
        for path, value in self.modified.items():
            deep_set(self.data, keys=path.split('.'), value=value)
        self.modified.clear()
    
    def get_function(self, name=None):
        """Get a Function object for a task."""
        name = name or self.task
        if name and name in self.data:
            return Function(self.data[name])
        return None
    
    def get_task_list(self):
        """Get list of available task names."""
        tasks = []
        for task_name in self.data:
            if task_name == 'Dashboard':
                continue
            scheduler = deep_get(self.data, keys=f'{task_name}.Scheduler')
            if scheduler is not None:
                tasks.append(task_name)
        return tasks
    
    @property
    def SERVER(self):
        return 'default'

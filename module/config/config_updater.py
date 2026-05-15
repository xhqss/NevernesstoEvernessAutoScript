"""
Config updater - reads existing user JSON configs and corrects them against
the canonical args.json definition. Fills missing fields, removes obsolete
ones, and validates values against option lists.

Adapted from Alas module/config/config_updater.py
"""

import os
import sys

# Ensure project root is on sys.path (for direct execution in PyCharm / CLI)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime

from module.config.deep import deep_get, deep_set, deep_iter, deep_default
from module.config.utils import (
    read_file, write_file, filepath_config, filepath_args, parse_value,
    DEFAULT_TIME,
)


class ConfigUpdater:
    """
    Reads existing user JSON configs and corrects them against the latest
    args.json (generated from YAML definitions by ConfigGenerator).

    Usage:
        updater = ConfigUpdater()
        updater.update_file('my_config')  # corrects config/my_config.json
        updater.update_file('template', is_template=True)  # reset template
    """

    @property
    def args(self):
        """Load args.json — the canonical argument definitions."""
        return read_file(filepath_args())

    def config_update(self, old, is_template=False):
        """
        Merge an old config dict with current args definitions.

        For each argument defined in args.json:
        - If the old config has a valid value, keep it
        - If the old value is missing/empty, or the arg is locked/state/hidden,
          use the default from args.json

        Args:
            old (dict): Existing user config data
            is_template (bool): If True, always use defaults (reset template)

        Returns:
            dict: Corrected config
        """
        new = {}

        for keys, data in deep_iter(self.args, depth=3):
            # keys = [task, group, arg]; data = {type, value, option, display, ...}
            value = deep_get(old, keys=keys, default=data.get('value'))
            typ = data.get('type', 'input')
            display = data.get('display')

            # Use default when:
            # - generating template
            # - value is missing or empty
            # - argument is locked or state (non-user-modifiable)
            # - argument is hidden (unless it's stored data)
            if is_template or value is None or value == '' \
                    or typ in ('lock', 'state') \
                    or (display == 'hide' and typ != 'stored'):
                value = data['value']

            value = parse_value(value, data=data)
            deep_set(new, keys=keys, value=value)

        return new

    def read_file(self, config_name, is_template=False):
        """
        Read and update a config file.

        Args:
            config_name (str): Config name (without .json), e.g. 'my_config'
            is_template (bool): Whether this is the template config

        Returns:
            dict: Corrected config data (not written back to disk yet)
        """
        old = read_file(filepath_config(config_name))
        return self.config_update(old, is_template=is_template)

    def write_file(self, config_name, data):
        """
        Write corrected config data back to disk.

        Args:
            config_name (str): Config name (without .json)
            data (dict): Corrected config data
        """
        write_file(filepath_config(config_name), data)

    def update_file(self, config_name, is_template=False):
        """
        Read, correct, and write a config file in one call.

        Args:
            config_name (str): Config name (without .json)
            is_template (bool): Whether this is the template config

        Returns:
            dict: The corrected config data that was written
        """
        data = self.read_file(config_name, is_template=is_template)
        self.write_file(config_name, data)
        return data

    def save_callback(self, key, value):
        """
        Called when a config value changes via GUI.
        Yields additional key-value pairs to set as side effects.

        Args:
            key (str): Dotted key path, e.g. "Main.Scheduler.Enable"
            value: New value set by user

        Yields:
            Tuple[str, Any]: Additional (key, value) pairs to set
        """
        # When a task is enabled, ensure it has all required Scheduler fields
        if key.endswith(".Scheduler.Enable") and value is True:
            parts = key.split(".")
            task_name = parts[0]
            yield f"{task_name}.Scheduler.NextRun", "2020-01-01 00:00:00"
            yield f"{task_name}.Scheduler.Command", task_name
            yield f"{task_name}.Scheduler.SuccessInterval", 30
            yield f"{task_name}.Scheduler.FailureInterval", 30
            yield f"{task_name}.Scheduler.ServerUpdate", "00:00"


if __name__ == '__main__':
    """
    Process the whole config generation + update.

             task.yaml ---+
         argument.yaml ---+-----> args.json ---> config_generated.py
         override.yaml ---+          |
          default.yaml ---+          +----------> template.json
              gui.yaml ----+----------+----------> i18n/{lang}.json (TODO)

    Then correct user config against latest args.json.
    """
    from module.config.config_generator import generate_all

    # Step 1: regenerate args.json / config_generated.py / template.json from YAML
    generate_all()

    # Step 2: update specific user config (or just template if no arg)
    if len(sys.argv) > 1:
        config_name = sys.argv[1]
        ConfigUpdater().update_file(config_name)
    else:
        ConfigUpdater().update_file('template', is_template=True)

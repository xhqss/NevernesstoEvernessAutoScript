"""
Config generator - reads YAML definitions and generates args.json + config class.
Adapted from Alas module/config/config_updater.py
"""

import os
import sys
import json
import copy
from datetime import datetime

# Ensure project root is on sys.path (for direct execution in PyCharm / CLI)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from module.config.deep import deep_get, deep_set, deep_iter
from module.config.utils import (
    read_file, write_file, filepath_argument, filepath_args,
    data_to_type
)


class ConfigGenerator:
    """
    Generates:
    1. args.json - Standardized argument definitions for GUI
    2. config_generated.py - Python class with all config values
    """
    
    @property
    def argument(self):
        """
        Load argument.yaml, standardize structure.
        
        Returns:
            dict: {group: {arg: {type, value, option, ...}}}
        """
        data = {}
        raw = read_file(filepath_argument('argument'))
        # raw is like {Scheduler: {Enable: {...}, NextRun: ..., Command: ...}}
        for group_name, group_data in raw.items():
            data[group_name] = {}
            for arg_name, arg_value in group_data.items():
                arg = {'type': 'input', 'value': ''}
                if not isinstance(arg_value, dict):
                    arg_value = {'value': arg_value}
                arg['type'] = data_to_type(arg_value)
                if isinstance(arg_value.get('value'), datetime):
                    arg['type'] = 'datetime'
                    arg['validate'] = 'datetime'
                arg.update(arg_value)
                data[group_name][arg_name] = arg
        
        # Storage group
        data['Storage'] = {
            'Storage': {
                'type': 'storage', 'value': {},
                'valuetype': 'ignore', 'display': 'disabled'
            }
        }
        return data
    
    @property
    def task(self):
        """Load task.yaml - task group definitions."""
        return read_file(filepath_argument('task'))
    
    @property
    def default(self):
        """Load default.yaml - default values."""
        return read_file(filepath_argument('default'))
    
    @property
    def override(self):
        """Load override.yaml - non-modifiable values."""
        return read_file(filepath_argument('override'))
    
    @property
    def args(self):
        """
        Merge all YAML definitions into args.json.

        ALAS-style task.yaml: each task lists its specific argument groups.
        Tasks only get the groups they declare, plus Storage.

        Flow:
            task.yaml ---+
        argument.yaml ---+-----> args.json
        override.yaml ---+
         default.yaml ---+
        """
        data = {}

        # Parse task.yaml — each task name maps to its assigned groups
        # Format: {TaskGroup: {tasks: {TaskName: [GroupA, GroupB, ...]}}}
        task_groups = {}  # {task_name: [group_name, ...]}

        for path, groups in deep_iter(self.task, min_depth=1, depth=3):
            if 'tasks' not in path:
                continue
            if isinstance(groups, list):
                # path = [TaskGroup, 'tasks', TaskName]
                task = path[2]
                valid_groups = [g for g in groups if g in self.argument]
                for g in groups:
                    if g not in self.argument:
                        print(f'  `{task}.{g}` is not related to any argument group')
                if 'Storage' in self.argument and 'Storage' not in valid_groups:
                    valid_groups.append('Storage')
                task_groups[task] = valid_groups

        # Build args: each task only gets its assigned groups
        for task_name, group_names in task_groups.items():
            for group_name in group_names:
                deep_set(
                    data,
                    keys=[task_name, group_name],
                    value=copy.deepcopy(self.argument[group_name])
                )

        # Apply defaults — only for groups already assigned to the task
        for p, v in deep_iter(self.default, depth=3):
            if len(p) == 3 and deep_get(data, keys=p[:2]) is not None:
                deep_set(data, keys=p + ['value'], value=v)

        # Apply overrides
        for p, v in deep_iter(self.override, depth=3):
            if len(p) == 3 and isinstance(v, dict):
                for arg_k, arg_v in v.items():
                    deep_set(data, keys=p + [arg_k], value=arg_v)
            elif len(p) == 3:
                deep_set(data, keys=p + ['value'], value=v)
                deep_set(data, keys=p + ['display'], value='hide')

        # Set command for each task
        for task_name in task_groups:
            if deep_get(data, keys=f'{task_name}.Scheduler.Command'):
                deep_set(data, keys=f'{task_name}.Scheduler.Command.value', value=task_name)
                deep_set(data, keys=f'{task_name}.Scheduler.Command.display', value='hide')

        return data
    
    def generate_args_json(self):
        """Generate args.json from YAML definitions."""
        args = self.args
        path = filepath_args()
        write_file(path, args)
        print(f'Generated: {path}')
        return args
    
    def generate_code(self):
        """Generate config_generated.py Python class."""
        from module.config.code_generator import CodeGenerator
        
        args = self.args
        lines = [
            'import datetime',
            '',
            '# This file was automatically generated by al/config/config_generator.py.',
            "# Don't modify it manually.",
            '',
            '',
            'class GeneratedConfig:',
            '    """',
            '    Auto generated configuration',
            '    """',
            '',
        ]
        
        for task, groups in args.items():
            for group, args_dict in groups.items():
                if not isinstance(args_dict, dict):
                    continue
                for arg_name, arg_data in args_dict.items():
                    if not isinstance(arg_data, dict):
                        continue
                    attr_name = f'{task}_{group}_{arg_name}'
                    value = arg_data.get('value', '')
                    option_str = ''
                    if 'option' in arg_data:
                        options = arg_data['option']
                        option_str = f'  # {", ".join(str(o) for o in options)}'
                    
                    if isinstance(value, str):
                        lines.append(f'    {attr_name} = {repr(value)}{option_str}')
                    elif isinstance(value, bool):
                        lines.append(f'    {attr_name} = {str(value)}{option_str}')
                    elif isinstance(value, datetime):
                        lines.append(f'    {attr_name} = datetime.datetime({value.year}, {value.month}, {value.day}, {value.hour}, {value.minute})')
                    elif value is None:
                        lines.append(f'    {attr_name} = None{option_str}')
                    else:
                        lines.append(f'    {attr_name} = {repr(value)}{option_str}')
        
        code = '\n'.join(lines)
        path = os.path.join(os.path.dirname(__file__), 'config_generated.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f'Generated: {path}')

        return code


def generate_all():
    """Generate args.json and config_generated.py from YAML definitions."""
    gen = ConfigGenerator()
    gen.generate_args_json()
    gen.generate_code()


if __name__ == '__main__':
    # Generation only — use config_updater.py for the full pipeline (generation + correction)
    generate_all()

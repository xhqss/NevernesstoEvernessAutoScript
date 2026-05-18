"""
Thin adapter that wraps a task/group from the nested AlConfig data dict
into the flat key-value interface expected by ConfigItemFactory / LabelAnd* widgets.
"""


class GroupConfigAdapter:
    """Presents a single config group (e.g. NTEKeyBinding) as a flat dict-like.

    Usage:
        adapter = GroupConfigAdapter(al_config.data, 'DefaultTask', 'NTEKeyBinding', group_schema)
        value = adapter.get('SkillKey')      # → 'e'
        adapter['SkillKey'] = 'q'            # writes through to al_config.data

    This is the bridge between al-script's nested {Task: {Group: {Arg: val}}}
    structure and ok-nte's flat `config[key]` pattern.
    """

    def __init__(self, al_config_data: dict, task_name: str,
                 group_name: str, schema: dict):
        self._data = al_config_data
        self._task = task_name
        self._group = group_name
        self._schema = schema  # {arg_name: {value: ..., type: ..., option: ...}}

    # ── dict-like read ──────────────────────────────────────

    def get(self, key: str, default=None):
        """Return current value for *key* (an argument name)."""
        task = self._data.get(self._task, {})
        group = task.get(self._group, {})
        if key in group:
            return group[key]
        # Fall back to schema default
        arg = self._schema.get(key, {})
        if isinstance(arg, dict):
            return arg.get('value', default)
        return default

    def get_default(self, key: str):
        """Return schema default for *key*."""
        arg = self._schema.get(key, {})
        if isinstance(arg, dict):
            return arg.get('value')
        return arg

    # ── dict-like write ─────────────────────────────────────

    def __setitem__(self, key: str, value):
        task = self._data.setdefault(self._task, {})
        group = task.setdefault(self._group, {})
        group[key] = value

    def __getitem__(self, key):
        return self.get(key)

    # ── iteration ───────────────────────────────────────────

    def items(self):
        for key in self._schema:
            if isinstance(self._schema[key], dict):
                if self._schema[key].get('display') in ('hide', 'disabled'):
                    continue
            yield key, self.get(key)

    def keys(self):
        for key in self._schema:
            if isinstance(self._schema[key], dict):
                if self._schema[key].get('display') in ('hide', 'disabled'):
                    continue
            yield key

    def __contains__(self, key):
        return key in self._schema

    def has_user_config(self):
        """Returns True if this group exists in user config (not just defaults)."""
        task = self._data.get(self._task, {})
        return self._group in task

    def reset_to_default(self):
        task = self._data.get(self._task, {})
        group = task.get(self._group, {})
        for key in list(group.keys()):
            if key in self._schema:
                arg = self._schema[key]
                if isinstance(arg, dict) and 'value' in arg:
                    group[key] = arg['value']

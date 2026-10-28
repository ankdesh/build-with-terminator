"""Machine settings. Relative paths always start at the checkout root."""
from dataclasses import dataclass
import os
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[3]
DEFAULTS = {
    'paths': {'harness': '.tools/deepseek-harness', 'fonts': '/usr/share/fonts/truetype/dejavu',
              'data': 'test_data', 'work': 'work', 'archive': 'archives'},
    'tools': {'python': 'python3.12', 'uv': 'uv', 'node': 'node', 'pnpm': 'pnpm',
              'klayout': 'klayout', 'bwrap': 'bwrap', 'git': 'git', 'docker': 'docker'},
    'resources': {'cpus': 2, 'workers': 4, 'memory_mb': 2048, 'timeout_seconds': 120},
    'asic': {'openroad': 'openroad', 'yosys': 'yosys', 'cpus': 2, 'memory_mb': 8192,
             'timeout_seconds': 3600},
}

@dataclass
class Settings:
    root: Path
    values: dict
    config_file: Path

    def path(self, key):
        value = Path(os.path.expandvars(os.path.expanduser(self.values['paths'][key])))
        return (value if value.is_absolute() else self.root/value).absolute()

    def tool(self, key):
        value = self.values['tools'][key]
        return str(self.root/value) if '/' in value and not Path(value).is_absolute() else value

    def public(self):
        return {**self.values, 'paths': {k: str(self.path(k)) for k in self.values['paths']}}


def load(path=None, overrides=None, root=ROOT):
    import copy
    root = Path(root).absolute()
    path = Path(path) if path else root/'config/local.toml'
    if not path.is_absolute():
        path = root/path
    values = copy.deepcopy(DEFAULTS)
    if path.exists():
        supplied = tomllib.loads(path.read_text())
        for section, entries in supplied.items():
            if section not in values or not isinstance(entries, dict):
                raise ValueError(f'Unknown configuration section: {section}')
            for key, value in entries.items():
                if key not in values[section]:
                    raise ValueError(f'Unknown setting: {section}.{key}')
                if type(value) is not type(values[section][key]):
                    raise ValueError(f'Invalid type: {section}.{key}')
                values[section][key] = value
    elif path != root/'config/local.toml':
        raise ValueError(f'Configuration file does not exist: {path}')
    for name, value in (overrides or {}).items():
        section, key = name.split('.')
        if value is not None:
            values[section][key] = value
    for section in ('resources', 'asic'):
        for key, value in values[section].items():
            if key in ('cpus', 'workers', 'memory_mb', 'timeout_seconds') and value < 1:
                raise ValueError(f'{section}.{key} must be positive')
    if values['resources']['workers'] > 4:
        raise ValueError('The C1 evaluator supports 1 to 4 workers')
    return Settings(root, values, path)

"""Versioned C2+C3 records, separate from the C1 manifest."""
from collections import Counter
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import re

ORFS_COMMIT = '64939f3717ad7c694199ba04cb98924b98022868'
IMAGE = 'openroad/orfs@sha256:6810dbf0e03dddbc89ed8c0a1e13cad09ce4c98d40c4ac0ab99fdc04b0676347'


def sha256(path):
    with Path(path).open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256')
    return digest.hexdigest()


def safe_path(root, relative):
    path = (Path(root)/relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Artifact path escapes dataset')
    return path


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n'); tmp.replace(path)


@dataclass(frozen=True)
class Case:
    case_id: str
    level: int
    kind: str
    source_group: str
    gds: str
    gds_sha256: str
    edit_policy: dict
    scope_box_um: list
    evidence: dict
    metrics: dict
    source: dict

    def __post_init__(self):
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', self.case_id) or self.level not in range(1, 6):
            raise ValueError('Invalid case identity')
        if self.kind not in ('repair', 'clean_control', 'no_edit'):
            raise ValueError('Unknown case kind')
        from ...edit_policy import EditPolicy
        EditPolicy.from_dict(self.edit_policy)

    def to_dict(self):
        return asdict(self)


@dataclass
class Manifest:
    cases: list[Case] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)
    schema_version: int = 1
    benchmark_version: str = 'c2c3-1.0.0'
    profile: str = 'asap7_c2c3_v1'
    deck_sha256: str = ''
    qualification_sha256: str = ''

    @property
    def complete(self):
        if len(self.cases) != 50 or self.blocked:
            return False
        return all(Counter(c.kind for c in self.cases if c.level == level) ==
                   {'repair': 6, 'clean_control': 2, 'no_edit': 2} and
                   sorted(Counter(c.source_group for c in self.cases if c.level == level).values()) == [5, 5]
                   for level in range(1, 6))

    def to_dict(self):
        return {**asdict(self), 'complete': self.complete, 'planned_cases': 50,
                'validation_level': 'geometry_only'}

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data.get('schema_version') != 1 or data.get('benchmark_version') != 'c2c3-1.0.0':
            raise ValueError('Unsupported C2+C3 manifest')
        values = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        values['cases'] = [Case(**c) for c in data['cases']]
        result = cls(**values)
        if len({c.case_id for c in result.cases}) != len(result.cases):
            raise ValueError('Duplicate case identities')
        if len({c.gds_sha256 for c in result.cases}) != len(result.cases):
            raise ValueError('Duplicate GDS files')
        return result

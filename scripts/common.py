"""Strict local data contracts; no model or network dependencies."""
import hashlib
import json
from pathlib import Path

DOMAINS = frozenset(['Physical / Health', 'Privacy / Confidentiality',
    'Security / System Integrity', 'Financial / Assets', 'Operational / Service',
    'Legal / Compliance', 'Information Quality', 'Reputational / Social / Psychological',
    'Discrimination / Fairness', 'Environmental', 'No Material Harm'])
DRIVERS = frozenset(['Risky Requested Outcome', 'Untrusted / Conflicting Instructions',
    'Authorization / Consent Failure', 'Insufficient Grounding / Uncertainty',
    'Scope / Safeguard Failure', 'Execution / Action Hazard', 'No Material Risk'])


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path}:{number}: invalid JSON') from exc
    return rows


def index_rows(rows, *, severity=True):
    if not rows:
        raise ValueError('Empty dataset/predictions')
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Each row must be an object')
        identifier = row.get('example_id')
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError('example_id must be a nonempty string')
        if identifier in indexed:
            raise ValueError(f'Duplicate ID: {identifier}')
        if severity:
            level = row.get('risk_severity')
            if type(level) is not int or not 1 <= level <= 5:
                raise ValueError(f'{identifier}: severity must be integer 1..5')
        indexed[identifier] = row
    return indexed


def validate_dataset(rows):
    indexed = index_rows(rows)
    for identifier, row in indexed.items():
        for key in ['formatted_interaction', 'proposed_action']:
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f'{identifier}: {key} must be nonempty text')
        for key, allowed, exclusive in [('risk_domains', DOMAINS, 'No Material Harm'),
                                         ('risk_drivers', DRIVERS, 'No Material Risk')]:
            labels = row.get(key)
            if (not isinstance(labels, list) or not 1 <= len(labels) <= 2
                    or any(not isinstance(x, str) or x not in allowed for x in labels)
                    or len(set(labels)) != len(labels)
                    or (exclusive in labels and len(labels) != 1)):
                raise ValueError(f'{identifier}: invalid {key}: {labels!r}')
    return indexed


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def guard_outputs(outputs, inputs):
    resolved = [Path(p).resolve() for p in outputs]
    if len(set(resolved)) != len(resolved) or set(resolved) & {Path(p).resolve() for p in inputs}:
        raise ValueError('Output paths must be distinct from each other and all input paths')

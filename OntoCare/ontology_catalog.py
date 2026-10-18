"""Read supplied ontology as data and namespace identifiers by source sheet."""
import json
import zipfile
from collections import Counter


def inspect_bundle(path):
    with zipfile.ZipFile(path) as archive:
        rows = json.loads(archive.read('anker-ontology-input/01-service-ontology/instances-knowledge.json'))
        steps = json.loads(archive.read('anker-ontology-input/01-service-ontology/instances-steps.json'))
    catalog = {}
    for row in rows:
        key = f"{row['sheet']}:{row['source_row']}"
        if key in catalog:
            raise ValueError('Duplicate source identity: ' + key)
        catalog[key] = row
    ids = Counter(row['kb_id'] for row in rows)
    # A bare kb_id cannot safely join a step when its parent is ambiguous.
    ambiguous_steps = [step for step in steps if ids[step['kb_id']] != 1]
    return {'knowledge_count': len(catalog), 'namespaced_ids': list(catalog),
            'duplicate_legacy_ids': sum(n > 1 for n in ids.values()),
            'step_count': len(steps), 'ambiguous_step_count': len(ambiguous_steps),
            'note': 'Ambiguous legacy step joins are excluded from automatic workflow import.'}

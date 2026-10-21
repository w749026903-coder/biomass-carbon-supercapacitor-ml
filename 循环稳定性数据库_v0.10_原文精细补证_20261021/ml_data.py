"""Read-only v0.10 overlay; retain both v0.9 decisions and the v0.8 source base."""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / '循环稳定性数据库_v0.9_训练质量准备_20261021'
NAME = '_cycling_v09_parent_api'
if NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(NAME, PARENT / 'ml_data.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = module
    spec.loader.exec_module(module)
base = sys.modules[NAME]
Dataset = base.Dataset
DataNotReady = base.DataNotReady


class Database(base.Database):
    def __init__(self, path=None):
        folder = Path(__file__).resolve().parent
        contract = json.loads((folder / 'data_contract.json').read_text('utf-8'))
        parent = PARENT / 'cycling_v0_9.sqlite'
        with parent.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if digest != contract['parent_database_sha256']:
            raise RuntimeError('Immutable v0.9 overlay fingerprint changed.')
        super().__init__(parent)
        self.root = folder
        self.contract = contract
        self.path = Path(path).resolve() if path else folder / 'cycling_v0_10.sqlite'
        # Do not overwrite parent's .delta/.cases: inherited methods need v0.9.
        self.delta_v10 = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        self.delta_v10.row_factory = sqlite3.Row
        self.delta_v10.execute('PRAGMA query_only=ON')
        self.cases_v10 = {
            r['endpoint_id']: json.loads(r['decision_json'])
            for r in self.delta_v10.execute('select * from evidence_decisions_v10')
        }

    def close(self):
        if hasattr(self, 'delta_v10'):
            self.delta_v10.close()
        super().close()

    def incoming_tests(self, document_id=None):
        return [json.loads(json.dumps(self.cases_v10[r['endpoint_id']]['after']))
                if r['endpoint_id'] in self.cases_v10 else r
                for r in super().incoming_tests(document_id)]

    def fetch(self, profile=None, year_min=None, year_max=None):
        profile = profile or self.contract['default_profile']
        result = super().fetch(profile, None, None)
        rows = {r['endpoint_id']: r for r in result.rows}
        for key, case in self.cases_v10.items():
            if profile in self.contract['profiles']:
                rows.pop(key, None)
                if profile not in case['profiles']:
                    continue
            elif key not in rows:
                continue
            r = json.loads(json.dumps(case['after']))
            r['profile_review'] = {'reason': case['reason'], 'evidence': case['evidence'],
                                   'review_version': 'v0.10'}
            rows[key] = r
        result.rows = [r for r in sorted(rows.values(), key=lambda r: (r['source_group'], r['endpoint_id']))
                       if (year_min is None or r['source_year'] is not None and r['source_year'] >= int(year_min))
                       and (year_max is None or r['source_year'] is not None and r['source_year'] <= int(year_max))]
        counts = collections.Counter(r['source_group'] for r in result.rows)
        for r in result.rows:
            r['source_weight'] = 1 / counts[r['source_group']]
        return result

    def evidence(self, endpoint_id, field=None):
        old = super().evidence(endpoint_id, field)
        case = self.cases_v10.get(endpoint_id)
        if not case:
            return old
        changed = {k for k, v in case['after'].items() if v != case['before'].get(k)}
        changed |= {k for k, v in case['after']['fields'].items()
                    if v != case['before']['fields'].get(k)}
        for r in old:
            if r['field_name'] in changed:
                r['selected'] = 0
                r['status'] = 'superseded_in_v10'
        for e in case['evidence']:
            for f in e.get('fields', []):
                if field and field != f:
                    continue
                old.append({'field_name': f,
                            'value_json': json.dumps(case['after'].get(f, case['after']['fields'].get(f)), ensure_ascii=False),
                            'selected': 1, 'review_version': 'v0.10', **e})
        return old

    def holds(self, endpoint_id):
        if endpoint_id not in self.cases_v10:
            return super().holds(endpoint_id)
        case = self.cases_v10[endpoint_id]
        return {'open_issues': case['after']['open_issues'],
                'remaining_evidence_work': case['after']['remaining_evidence_work'],
                'previous_holds': super().holds(endpoint_id),
                'v10_reason': case['reason'], 'v10_profiles': case['profiles']}

    def admission_checks(self, endpoint_id, profile=None):
        if endpoint_id not in self.cases_v10:
            return super().admission_checks(endpoint_id, profile)
        c = self.cases_v10[endpoint_id]
        return [{'profile': p, 'endpoint_id': endpoint_id,
                 'status': 'approved_for_reported_protocol' if p in c['profiles'] else 'pending_or_outside',
                 'reason': c['reason'], 'evidence': c['evidence']}
                for p in ([profile] if profile else self.contract['profiles'])]

    def review_queue(self):
        """Current non-admitted incoming observations, preserving all holds."""
        return [r for r in self.incoming_tests() if not r['eligible']]

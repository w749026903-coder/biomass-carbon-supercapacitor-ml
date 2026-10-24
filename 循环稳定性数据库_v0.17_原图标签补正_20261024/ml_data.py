"""Read-only v0.17 reviewed delta with explicit current profile membership.

Parent versions retain their original labels, memberships and review history.
"""
from pathlib import Path
import collections, hashlib, importlib.util, json, re, sqlite3, sys
ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / '循环稳定性数据库_v0.16_补证与口径复核_20261024'
NAME = '_cycling_v016_parent_for_v017'
if NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(NAME, PARENT / 'ml_data.py')
    mod = importlib.util.module_from_spec(spec); sys.modules[NAME] = mod; spec.loader.exec_module(mod)
base = sys.modules[NAME]
Dataset, DataNotReady = base.Dataset, base.DataNotReady

class Database(base.Database):
    def __init__(self, path=None):
        folder = Path(__file__).resolve().parent
        contract = json.loads((folder / 'data_contract.json').read_text('utf8'))
        with (PARENT / 'cycling_v0_16.sqlite').open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != contract['parent_database_sha256']:
                raise RuntimeError('Immutable v0.16 changed.')
        super().__init__(PARENT / 'cycling_v0_16.sqlite')
        self.root, self.contract = folder, contract
        self.path = Path(path).resolve() if path else folder / contract['database_file']
        self.delta_v17 = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        self.delta_v17.row_factory = sqlite3.Row
        self.delta_v17.execute('pragma query_only=on')
        self.changes_v17 = collections.defaultdict(list)
        for r in self.delta_v17.execute('select * from field_changes_v17 order by endpoint_id,field_name'):
            self.changes_v17[r['endpoint_id']].append(dict(r))
        self.reviews_v17 = {r['endpoint_id']: json.loads(r['review_json']) for r in self.delta_v17.execute('select * from reviews_v17')}
        self.members_v17 = collections.defaultdict(set)
        for r in self.delta_v17.execute('select * from profile_membership_v17'):
            self.members_v17[r['profile']].add(r['endpoint_id'])

    def close(self):
        if hasattr(self, 'delta_v17'): self.delta_v17.close()
        super().close()

    def _apply_v17(self, row):
        if row is not None and hasattr(self, 'changes_v17') and not getattr(self, '_reading_parent_v17', False):
            for c in self.changes_v17.get(row['endpoint_id'], []):
                row[c['field_name']] = json.loads(c['after_json'])
                row[c['field_name'] + '_status'] = 'v017_' + c['operation']
            if row['endpoint_id'] in self.reviews_v17:
                row['review_disposition_v17'] = self.reviews_v17[row['endpoint_id']]['disposition']
            profiles = [p for p in self.contract['profiles'] if row['endpoint_id'] in self.members_v17[p]]
            # v13 Dataset validates this compatibility field; current membership is explicit.
            row['admission_profiles_v13'] = profiles
            row['admission_profiles_v17'] = profiles
        return row

    def fetch(self, profile=None, year_min=None, year_max=None):
        if not hasattr(self, 'delta_v17'): return super().fetch(profile, year_min, year_max)
        profile = profile or self.contract['default_profile']
        if profile not in self.contract['profiles'] and profile not in ['all_review', 'review_3e_all', 'incoming_review']:
            return super().fetch(profile, year_min, year_max)
        # Apply current evidence before year filters or cohort membership.
        rows = []
        for row in super().fetch('all_review').rows:
            row = self._apply_v17(row); key = row['endpoint_id']
            if profile in self.contract['profiles'] and key not in self.members_v17[profile]: continue
            if profile == 'review_3e_all' and row['system'] != '3E': continue
            if profile == 'incoming_review' and not key.startswith('incoming:'): continue
            if year_min is not None and (row.get('source_year') is None or row['source_year'] < int(year_min)): continue
            if year_max is not None and (row.get('source_year') is None or row['source_year'] > int(year_max)): continue
            rows.append(row)
        counts = collections.Counter(r['source_group'] for r in rows)
        for r in rows: r['source_weight'] = 1 / counts[r['source_group']]
        features = self.contract['profiles'][profile]['features'] if profile in self.contract['profiles'] else self.contract['core_features']
        return Dataset(profile, sorted(rows, key=lambda r: (r['source_group'], r['endpoint_id'])), list(features))

    def by_endpoint(self, key): return self._apply_v17(super().by_endpoint(key))

    def holds(self, key):
        flag = getattr(self, '_reading_parent_v17', False); self._reading_parent_v17 = True
        try: old = super().holds(key)
        finally: self._reading_parent_v17 = flag
        if not hasattr(self, 'reviews_v17') or key not in self.reviews_v17: return old
        r = self.reviews_v17[key]
        return dict(open_issues=r['open_issues'], approved_profiles=r['approved_profiles'], disposition=r['disposition'],
                    reason=r['reason'], resolution=r['resolution'], caveats=r.get('caveats', []), previous_holds=old, review_version='v0.17')

    def reviewed_pending_batch(self, include_outside=False):
        rows = [dict(self.reviews_v17.get(r['endpoint_id'], r)) for r in super().reviewed_pending_batch(True)]
        if include_outside: return rows  # Fixed historical 41-case audit, including admitted decisions.
        return [r for r in rows if not r['disposition'].startswith(('outside_', 'approved_'))]

    def admission_checks(self, key, profile=None):
        if not hasattr(self, 'delta_v17'): return super().admission_checks(key, profile)
        row = self.by_endpoint(key)
        result = []
        for p in ([profile] if profile else self.contract['profiles']):
            flag = getattr(self, '_reading_parent_v17', False); self._reading_parent_v17 = True
            try: history = super().admission_checks(key, p)
            finally: self._reading_parent_v17 = flag
            result.append(dict(endpoint_id=key, profile=p, status='approved_for_reported_protocol' if row and p in row['admission_profiles_v17'] else 'not_approved',
                               current_review=self.reviews_v17.get(key), historical_checks=history, review_version='v0.17'))
        return result

    def field_changes(self, key=None, include_history=False):
        rows = [dict(c, before=json.loads(c['before_json']), after=json.loads(c['after_json']),
                     evidence=json.loads(c['evidence_json']), review_version='v0.17')
                for k, cs in self.changes_v17.items() for c in cs if key is None or key == k]
        return (super().field_changes(key, include_history=True) if include_history else []) + rows

    def evidence(self, key, field=None):
        flag = getattr(self, '_reading_historical_evidence', False); self._reading_historical_evidence = True
        try: old = super().evidence(key, field)
        finally: self._reading_historical_evidence = flag
        if not hasattr(self, 'changes_v17'): return old
        changes = self.changes_v17.get(key, []); names = {c['field_name'] for c in changes}
        for e in old:
            if e.get('field_name') in names: e.update(selected=0, currently_selected=0, superseded_by_v17=True)
        for c in changes:
            if field is not None and field != c['field_name']: continue
            for e in json.loads(c['evidence_json']):
                old.append(dict(e, endpoint_id=key, field_name=c['field_name'], value_json=c['after_json'], selected=1,
                                currently_selected=1, review_version='v0.17', excerpt_kind='reviewed_own_source_field'))
        return old

    def material_properties(self, material_key=None, selected_only=True):
        old = super().material_properties(material_key, selected_only)
        if not hasattr(self, 'delta_v17') or getattr(self, '_reading_historical_evidence', False): return old
        rows = [dict(r) for r in self.delta_v17.execute('select * from material_fields_v17') if material_key is None or r['material_key'] == material_key]
        keys = {(r['material_key'], r['field_name']) for r in rows}
        if selected_only: old = [r for r in old if (r['material_key'], r['field_name']) not in keys]
        else:
            for r in old:
                if (r['material_key'], r['field_name']) in keys: r.update(selected=0, superseded_by_v17=True)
        for r in rows: r.update(value=json.loads(r['value_json']), evidence=json.loads(r['evidence_json']), selected=1,
                               review_version='v0.17', stage='before_cycling', training_admission_inferred=False, applies_to_systems_json='[]')
        return old + rows

    def search_native(self, query, doi=None, limit=10):
        words = str(query).split(); limit = max(0, int(limit))
        if not words or not limit: return []
        out = []
        for raw in self.delta_v17.execute('select * from source_segments_v17'):
            r = dict(raw)
            if doi and r['doi'] != str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'): continue
            if not all(w.lower() in r['text'].lower() for w in words): continue
            if hashlib.sha256(r['text'].encode()).hexdigest() != r['content_sha256']: raise RuntimeError('Evidence text changed.')
            with (ROOT / r['path']).open('rb') as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() != r['sha256']: raise RuntimeError('Evidence source changed.')
            text = r.pop('text'); hit = re.search('|'.join(re.escape(w) for w in words), text, re.I)
            start = max(0, hit.start() - 180) if hit else 0
            r.update(excerpt=text[start:start + 1400], training_eligible=0, status='evidence_search_match_not_test_admission', provider='v17_reviewed_evidence')
            out.append(r)
            if len(out) == limit: break
        if len(out) < limit: out.extend(super().search_native(query, doi, limit - len(out)))
        return out

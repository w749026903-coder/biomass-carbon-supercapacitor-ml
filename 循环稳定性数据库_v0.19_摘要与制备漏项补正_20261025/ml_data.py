"""Read-only, source-qualified v0.19 corrections; no new admission or ML fits."""
from pathlib import Path
import collections, hashlib, importlib.util, json, re, sqlite3, sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / '循环稳定性数据库_v0.18_来源题录与质量核查_20261024'
NAME = '_cycling_v018_parent_for_v019'
if NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(NAME, PARENT / 'ml_data.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = module
    spec.loader.exec_module(module)
base = sys.modules[NAME]
Dataset, DataNotReady = base.Dataset, base.DataNotReady


class Database(base.Database):
    def __init__(self, path=None):
        folder = Path(__file__).resolve().parent
        contract = json.loads((folder / 'data_contract.json').read_text('utf8'))
        with (PARENT / 'cycling_v0_18.sqlite').open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != contract['parent_database_sha256']:
                raise RuntimeError('Immutable v0.18 fingerprint differs.')
        super().__init__(PARENT / 'cycling_v0_18.sqlite')
        self.root, self.contract = folder, contract
        self.path = Path(path).resolve() if path else folder / contract['database_file']
        self.delta_v19 = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        self.delta_v19.row_factory = sqlite3.Row
        self.delta_v19.execute('pragma query_only=on')
        self.changes_v19 = collections.defaultdict(list)
        for change in self.delta_v19.execute('select * from field_changes_v19 order by endpoint_id,field_name'):
            self.changes_v19[change['endpoint_id']].append(dict(change))
        self.reviews_v19 = {r['endpoint_id']: json.loads(r['review_json'])
                            for r in self.delta_v19.execute('select * from reviews_v19')}

    def close(self):
        if hasattr(self, 'delta_v19'):
            self.delta_v19.close()
        super().close()

    def _apply_v19(self, row):
        if row is not None and hasattr(self, 'changes_v19'):
            for change in self.changes_v19.get(row['endpoint_id'], []):
                row[change['field_name']] = json.loads(change['after_json'])
                row[change['field_name'] + '_status'] = 'v019_' + change['operation']
            if row['endpoint_id'] in self.reviews_v19:
                review = self.reviews_v19[row['endpoint_id']]
                row['review_disposition_v19'] = review['disposition']
                row['current_open_issues_v19'] = list(review['open_issues'])
        return row

    def fetch(self, profile=None, year_min=None, year_max=None):
        data = super().fetch(profile, year_min, year_max)
        if not hasattr(self, 'delta_v19'):
            return data
        return Dataset(data.profile, [self._apply_v19(row) for row in data.rows], list(data.features))

    def by_endpoint(self, key):
        return self._apply_v19(super().by_endpoint(key))

    def holds(self, key):
        previous = super().holds(key)
        if not hasattr(self, 'reviews_v19') or key not in self.reviews_v19:
            return previous
        review = self.reviews_v19[key]
        return dict(open_issues=review['open_issues'], approved_profiles=review['approved_profiles'],
                    disposition=review['disposition'], reason=review['reason'],
                    resolution=review['resolution'], previous_holds=previous, review_version='v0.19')

    def reviewed_pending_batch(self, include_outside=False):
        previous = super().reviewed_pending_batch(True)
        rows = [dict(self.reviews_v19.get(row['endpoint_id'], row)) for row in previous]
        return rows if include_outside else [r for r in rows if not r['disposition'].startswith(('outside_', 'approved_'))]

    def admission_checks(self, key, profile=None):
        result = super().admission_checks(key, profile)
        if hasattr(self, 'reviews_v19') and key in self.reviews_v19:
            for check in result:
                check['historical_v18_review'] = check.get('current_review')
                check['current_review'] = self.reviews_v19[key]
                check['review_version'] = 'v0.19'
        return result

    def field_changes(self, key=None, include_history=False):
        rows = [dict(change, before=json.loads(change['before_json']), after=json.loads(change['after_json']),
                     evidence=json.loads(change['evidence_json']), review_version='v0.19')
                for record, changes in self.changes_v19.items() for change in changes if key is None or record == key]
        return (super().field_changes(key, include_history=True) if include_history else []) + rows

    def evidence(self, key, field=None):
        previous = super().evidence(key, field)
        if not hasattr(self, 'changes_v19'):
            return previous
        names = {change['field_name'] for change in self.changes_v19.get(key, [])}
        for item in previous:
            if item.get('field_name') in names:
                item.update(selected=0, currently_selected=0, superseded_by_v19=True)
        for change in self.changes_v19.get(key, []):
            if field is not None and field != change['field_name']:
                continue
            for item in json.loads(change['evidence_json']):
                previous.append(dict(item, endpoint_id=key, field_name=change['field_name'],
                                     value_json=change['after_json'], selected=1, currently_selected=1,
                                     review_version='v0.19', excerpt_kind='reviewed_own_source_qualified_field'))
        return previous

    def material_properties(self, material_key=None, selected_only=True):
        previous = super().material_properties(material_key, selected_only)
        if not hasattr(self, 'delta_v19') or getattr(self, '_reading_historical_evidence', False):
            return previous
        rows = [dict(r) for r in self.delta_v19.execute('select * from material_fields_v19')
                if material_key is None or r['material_key'] == material_key]
        keys = {(r['material_key'], r['field_name']) for r in rows}
        if selected_only:
            previous = [r for r in previous if (r['material_key'], r['field_name']) not in keys]
        else:
            for item in previous:
                if (item['material_key'], item['field_name']) in keys:
                    item.update(selected=0, superseded_by_v19=True)
        for row in rows:
            row.update(value=json.loads(row['value_json']), evidence=json.loads(row['evidence_json']),
                       selected=1, review_version='v0.19', stage='before_cycling',
                       training_admission_inferred=False, applies_to_systems_json='[]')
        return previous + rows

    def search_native(self, query, doi=None, limit=10):
        words, limit = str(query).split(), max(0, int(limit))
        if not words or not limit:
            return []
        if not hasattr(self, 'delta_v19'):
            return super().search_native(query, doi, limit)
        found = []
        wanted_doi = str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/') if doi else None
        for raw in self.delta_v19.execute('select * from source_segments_v19 order by segment_id'):
            row = dict(raw)
            if wanted_doi and row['doi'] != wanted_doi:
                continue
            if not all(word.lower() in row['text'].lower() for word in words):
                continue
            if hashlib.sha256(row['text'].encode()).hexdigest() != row['content_sha256']:
                raise RuntimeError('Reviewed native segment differs.')
            with (ROOT / row['path']).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                    raise RuntimeError('Reviewed source fingerprint differs.')
            text = row.pop('text')
            match = re.search('|'.join(re.escape(word) for word in words), text, re.I)
            start = max(0, match.start() - 180) if match else 0
            row.update(excerpt=text[start:start + 1600], provider='v19_reviewed_native_source',
                       training_eligible=0, status='search_match_not_training_admission')
            found.append(row)
            if len(found) >= limit:
                return found
        return (found + super().search_native(query, doi, limit))[:limit]

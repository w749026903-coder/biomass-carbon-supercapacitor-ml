"""Source grouping for candidate JSON or canonical material FK; never writes evidence."""
from data.literature_current import open_literature_database

def normalize_doi(value):
    value=value.strip().lower()
    for prefix in ['https://doi.org/','http://doi.org/','doi:']:
        if value.startswith(prefix):value=value[len(prefix):]
    return value.rstrip('/')

def source_grouped_candidates(database):
    materials={r['material_key']:r for r in database.materials()};result=[]
    for item in database.tests():
        material=materials[item['material_key']];doi=normalize_doi(material['doi'])
        if not doi.startswith('10.'):raise ValueError('No verified material DOI for '+item['candidate_id'])
        record=dict(item['record']);raw=record.get('source_group')
        if raw and normalize_doi(raw)!=doi:raise ValueError('Conflicting source group for '+item['candidate_id'])
        if not raw:
            record.update(source_group='doi:'+doi,source_group_raw=raw,source_group_binding=dict(basis='canonical materials.doi via preserved material_key foreign key',material_key=item['material_key'],doi=material['doi'],not_new_measurement=True))
        result.append(dict(item,record=record))
    return result

class GroupedLiteratureDatabase:
    """Facade for consumers needing a source group in every candidate record."""
    def __init__(self):self.database=open_literature_database()
    def __enter__(self):self.database.__enter__();return self
    def __exit__(self,*args):return self.database.__exit__(*args)
    def __getattr__(self,name):return getattr(self.database,name)
    def tests(self):return source_grouped_candidates(self.database)

def open_grouped_literature_database():return GroupedLiteratureDatabase()

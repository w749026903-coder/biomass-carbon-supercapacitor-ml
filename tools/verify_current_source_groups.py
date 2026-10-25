"""Read-only compatibility verification; primary sealed v7/v0.20 payloads are unchanged."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'文献全量利用复核_20261026/批次07_棕榈壳与串并联'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def verify(prepare=False):
    from data.literature_groups import open_grouped_literature_database,normalize_doi,source_grouped_candidates
    from data.literature_current import open_literature_database
    pointer=json.loads((ROOT/'data/current_literature.json').read_text('utf8'));db=ROOT/pointer['directory']/pointer['database_file'];before=sha(db)
    with open_literature_database() as raw,open_grouped_literature_database() as grouped:
        original={r['candidate_id']:r for r in raw.tests()};rows=grouped.tests();materials={r['material_key']:r for r in raw.materials()};derived=[]
        assert len(rows)==len(original)==31
        for row in rows:
            ident=row['candidate_id'];r=row['record'];old=original[ident]['record']
            assert normalize_doi(r['source_group'])==normalize_doi(materials[row['material_key']]['doi'])
            assert all(r[k]==v for k,v in old.items())
            if 'source_group' not in old:derived.append(ident);assert r['source_group_binding']['material_key']==row['material_key']
        assert derived==['LP7_PK_stack25_26_C2100']
        class ConflictingReader:
            def materials(self):return list(materials.values())
            def tests(self):
                row=dict(rows[-1]);row['record']=dict(row['record'],source_group='doi:10.0000/intentionally_conflicting_source')
                return [row]
        try:source_grouped_candidates(ConflictingReader())
        except ValueError:rejected=True
        else:rejected=False
        assert rejected,'Never replace an existing conflicting group with a convenient DOI.'
    # The historical validator locally imports its literature reader. Inject only a
    # version-dispatched, FK-grouped read-only facade in this process, then restore.
    # Its 988 science/history/input checks, CSV and payload comparisons are intact.
    import data.literature_v4 as legacy_reader
    import verify_new_source_v020 as historical
    saved=legacy_reader.open_literature_database
    try:
        legacy_reader.open_literature_database=open_grouped_literature_database
        historical.verify()
    finally:legacy_reader.open_literature_database=saved
    addendum=json.loads((historical.OUT/'verification_addendum.json').read_text('utf8'))
    assert sha(historical.OUT/'merge_manifest.json')==addendum['primary_manifest_sha256']
    for item in addendum['outputs']:assert sha(ROOT/item['path'])==item['sha256']
    assert sha(db)==before==pointer['sha256']
    value=dict(status='passed',candidate_rows=31,raw_JSON_groups_present=30,groups_derived_from_canonical_material_FK=derived,all_candidate_material_DOI_groups_match=True,conflicting_existing_group_rejected=True,original_values_preserved=True,cycling_988_checks_with_grouped_reader='passed unchanged',cycling_v020_addendum_payloads_preserved=True,primary_v7_manifest_sha256=sha(OUT/'merge_manifest.json'),literature_database_sha256=before,model_fits=0,ordinary_cycling_admissions_added=0,full_literature_goal_complete=False)
    report=OUT/'verification_grouping_addendum.json'
    if prepare:
        assert not (OUT/'grouping_addendum_manifest.json').exists();write(report,value)
    else:assert json.loads(report.read_text('utf8'))==value
    if (OUT/'grouping_addendum_manifest.json').exists():
        for item in json.loads((OUT/'grouping_addendum_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/item['path'])==item['sha256']
    print(json.dumps(value,ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)>2 or (len(sys.argv)==2 and sys.argv[1] not in ['--prepare','--seal']):raise SystemExit('No args:readonly; --prepare/--seal:one-time addendum setup')
    prepare=len(sys.argv)==2 and sys.argv[1]=='--prepare';verify(prepare)
    if len(sys.argv)==2 and sys.argv[1]=='--seal':
        dest=OUT/'grouping_addendum_manifest.json';assert not dest.exists()
        files=[OUT/'verification_grouping_addendum.json',OUT/'verification_grouping_addendum.md',ROOT/'data/literature_groups.py',Path(__file__).resolve()]
        write(dest,dict(primary_manifest_sha256=sha(OUT/'merge_manifest.json'),outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))

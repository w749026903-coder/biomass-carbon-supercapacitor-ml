import json, sqlite3, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DB = PROJECT/'循环稳定性数据库_v0.2_20261017/cycling_v0_2.sqlite'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def norm(s):
    s=(s or '').strip().lower()
    for p in ['https://doi.org/','http://doi.org/','http://dx.doi.org/','https://dx.doi.org/','doi:']:
        if s.startswith(p):s=s[len(p):].strip()
    return s
con=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
tables={t:[dict(r) for r in con.execute('select * from '+t)] for t in ['papers','source_files','source_relationships','issues','admissions']}
idxpath=PROJECT/'文献整理_20261017/当前唯一文献位置.json'
idx=json.loads(idxpath.read_text(encoding='utf-8-sig'))
prevpath=PROJECT/'循环稳定性文献补充_20261017/第一批文献清单_核验后.json'
prev=json.loads(prevpath.read_text(encoding='utf-8-sig'))
freeze_paths=[PROJECT/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json',PROJECT/'训练适用性审核_20261016/训练相关问题登记.json']
freeze=[{'path':str(p),'records':json.loads(p.read_text(encoding='utf-8-sig'))} for p in freeze_paths]
save('基线只读快照.json',{'database_sha256':sha(DB),'tables':tables,'unique_library_index':idx,'previous_batch':prev,'freezes':freeze})
records=[]
for p in tables['papers']:
    records.append({'doi_normalized':norm(p['doi']),'doi_original':p['doi'],'id':p['paper_id'],'title':p['title'],'kind':'existing_archived_paper','action':'exclude_from_new_count; supplements_only_if_missing'})
for p in prev:
    records.append({'doi_normalized':norm(p['doi']),'doi_original':p['doi'],'id':p['id'],'title':p['title'],'kind':'previous_batch','action':'not_new_batch2; preserve_previous_status','main_obtained':p['main_obtained']})
for f in freeze[0]['records']:
    records.append({'doi_normalized':norm(f['doi']),'kind':'frozen_or_excluded','status':f['status'],'reason':f['reason'],'action':'never_auto_unfreeze'})
save('DOI去重基线.json',{'normalization':'trim/lowercase/strip DOI URL or prefix; original preserved','records':records,'counts':{'papers':len(tables['papers']),'library_entries':len(idx),'source_files':len(tables['source_files']),'issues':len(tables['issues']),'previous_batch':len(prev)}})
sourcechecks=[]
for f in tables['source_files']:
    p=Path(f['path']);actual=sha(p) if p.exists() else None
    sourcechecks.append({'path':str(p),'expected_sha256':f['sha256'],'sha256':actual,'match':actual==f['sha256']})
save('基线与原文保护指纹.json',{'database':str(DB),'database_sha256':sha(DB),'inputs':[{'path':str(p),'sha256':sha(p)} for p in [idxpath,prevpath,*freeze_paths,PROJECT/'并行协作契约_v1_20261017.json']], 'source_files':sourcechecks})
for p in tables['papers']:print(p['paper_id'],p['doi'],p['title'])
print('CHECKS',len(sourcechecks),all(x['match'] for x in sourcechecks))

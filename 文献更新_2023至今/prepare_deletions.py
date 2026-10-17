from pathlib import Path
import json,hashlib,sys,collections
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
ledger=json.loads((ROOT/'文献下载_120篇/下载归档最终台账.json').read_text(encoding='utf-8-sig'))
inventory=json.loads((OUT/'旧120篇_年份复核.json').read_text(encoding='utf-8'))
old={x['doi'].lower():x for x in inventory if x['year'] and x['year']<2023}
known_hashes={}
for rec in ledger:
    doi=rec['doi'].lower()
    if doi not in old:continue
    if rec.get('local_pdf') and Path(rec['local_pdf']).is_file():
        assert old[doi]['date_live_refreshed'], doi
        digest=hashlib.sha256(Path(rec['local_pdf']).read_bytes()).hexdigest()
        assert digest==rec['sha256']
        known_hashes[digest]={'doi':doi,'year':old[doi]['year'],'kind':'论文PDF','old_id':rec['collection_id']}
    for sup in rec.get('supplements',[]):
        p=Path(sup['local_path'])
        if not p.is_file():continue
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        assert digest==sup['sha256']
        known_hashes[digest]={'doi':doi,'year':old[doi]['year'],'kind':'旧论文附属文件','old_id':rec['collection_id']}
files=list(ROOT.rglob('*.pdf'))+list(ROOT.rglob('*.docx'))+list(Path(r'D:\文献').rglob('*.pdf'))+list(Path(r'D:\文献').rglob('*.docx'))
manifest=[]
for p in files:
    if any(part.lower() in {'.git','.agents','.codex','.aws'} for part in p.parts):continue
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    if digest in known_hashes:
        manifest.append({**known_hashes[digest],'path':str(p.resolve()),'sha256':digest,'bytes':p.stat().st_size})
assert len({x['path'].lower() for x in manifest})==len(manifest)
with (OUT/'删除清单_2022年及以前.json').open('x',encoding='utf-8') as f:
    json.dump(manifest,f,ensure_ascii=False,indent=2)
print('FILES',len(manifest),'UNIQUE_DOIS',len({x['doi'] for x in manifest}),'BY_ROOT',dict(collections.Counter('D:/文献' if x['path'].startswith('D:\\文献\\') else 'project' for x in manifest)))
for x in manifest: print(x['year'],x['kind'],x['path'])

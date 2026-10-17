from pathlib import Path
import json,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent
rows=json.loads((OUT/'获取结果_归档前.json').read_text(encoding='utf-8'))
manifest=[]
for row in rows:
    if row.get('download_status')!='新增全文已核验_待归档':continue
    path=Path(row['staged_path']);target=Path(r'D:\文献')/row['filename']
    assert path.is_file() and not target.exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    manifest.append({'paper_id':row['collection_id'],'source':str(path),'target':str(target),'sha256':row['sha256'],'kind':'paper'})
    for sup in row.get('supplements_current',[]):
        path=Path(sup['staged_path']);target=Path(r'D:\文献\补充材料_2023至今')/sup['filename']
        assert path.is_file() and not target.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sup['sha256']
        manifest.append({'paper_id':row['collection_id'],'source':str(path),'target':str(target),'sha256':sup['sha256'],'kind':'supplement'})
with (OUT/'新增归档清单.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
print('Archive files',len(manifest))

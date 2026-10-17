from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent.parent
p=ROOT/'文献分类与审核准备_20261016/本地与压缩包文件盘点.json'
inventory=json.loads(p.read_text(encoding='utf-8'))
for rec in inventory['records']:
    target=Path(rec['local_pdf'])
    local={'kind':'local_pdf','path':str(target),'filename':target.name,'bytes':target.stat().st_size,
           'origin':'20261017物理去重整理','historical_path_manifest':str(ROOT/'文献整理_20261017/整理计划.json')}
    seen=set();archives=[]
    for source in rec['sources']:
        if source['kind']=='local_pdf':continue
        key=(source['kind'],source.get('archive'),source.get('entry'))
        if key not in seen:seen.add(key);archives.append(source)
    rec['sources']=[local]+archives
p.write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Collapsed historical source pointers to one actual local file per content')

"""Index exact source-byte copies inside the project; never modify/extract the original library."""
from __future__ import annotations
import hashlib,json,re,zipfile
from pathlib import Path
from repository_checks import digest
ROOT=Path(__file__).resolve().parents[1]
baseline=ROOT/'同体系文献补充_第二批_20261017/基线与原文保护指纹.json'
items=json.loads(baseline.read_text(encoding='utf-8'))['source_files']
needed={x.get('expected_sha256') or x['sha256'] for x in items};copies={h:[] for h in needed}
for p in ROOT.rglob('*'):
    if not p.is_file() or any(x in p.parts for x in ['.git','.venv','node_modules','__pycache__']):continue
    if p.suffix.lower() not in ['.pdf','.xml','.txt','.docx','.doc','.xlsx','.xls']:continue
    h=digest(p)
    if h in copies:copies[h].append({'kind':'repository_file','path':p.relative_to(ROOT).as_posix()})
archives=[ROOT/'文献整理_20261017/整理前文件备份.zip',ROOT/'文献整理_20261017/原始压缩包/1.zip']
for archive in archives:
    if not archive.exists():continue
    with zipfile.ZipFile(archive) as z:
        for m in z.infolist():
            if m.is_dir() or Path(m.filename).suffix.lower() not in ['.pdf','.xml','.txt','.docx','.doc','.xlsx','.xls']:continue
            with z.open(m) as f:h=hashlib.file_digest(f,'sha256').hexdigest()
            if h in copies:copies[h].append({'kind':'archive_member','archive':archive.relative_to(ROOT).as_posix(),'member':m.filename,'uncompressed_bytes':m.file_size})
out=[]
for x in items:
    h=x.get('expected_sha256') or x['sha256'];parts=x['path'].replace('\\','/').split('/');source_id=None
    for part in parts:
        match=re.match(r'^(SRC\d+|R\d+)_',part)
        if match:source_id=match.group(1);break
    out.append({'source_id':source_id,'original_local_path':x['path'],'filename':parts[-1],'sha256':h,'portable_copies':copies[h],'external_only':not bool(copies[h])})
target=ROOT/'data/source_locations_portable.json';target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps({'scope':'Original 137 source files; third-round additional SI remains in its own external_sources directory.','original_source_index':str(baseline.relative_to(ROOT).as_posix()),'records':out,'total':len(out),'available_inside_repository':sum(bool(x['portable_copies']) for x in out),'external_only_count':sum(x['external_only'] for x in out)},ensure_ascii=False,indent=2),encoding='utf-8')
rows=json.loads((ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/新增50篇_逐篇数据与获取状态.json').read_text(encoding='utf-8'))['records']
lines=['# 新增50篇文献：可移植入口','','保留历史原件中的Windows绝对路径；本页使用仓库相对路径。克隆后取齐LFS文件，再打开HTML/PDF或直接读取XML。','','|编号与体系|文献及DOI|本地正文|','|---|---|---|']
for r in rows:
    local=r.get('readable_html') or next(iter(r['complete_main_files']),None);link='待补正文'
    if local:
        rel=local.replace('\\','/').split('机器学习-超级电容器/',1)[-1];link=f'[打开](../{rel})'
    lines.append(f'|{r["temporary_id"]} {r["cycle_configuration"]}|{r["title"]}<br>[{r["doi"]}]({r["doi_url"]})|{link}|')
(ROOT/'docs/LITERATURE_INDEX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'indexed_sources':len(out),'available_inside_repository':sum(bool(x['portable_copies']) for x in out),'external_only':sum(x['external_only'] for x in out)},ensure_ascii=False))

from pathlib import Path
import collections,ctypes,hashlib,html,json,re,shutil,sys,unicodedata,zipfile
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
LIB=Path(r'D:\文献').resolve()
AUDIT=ROOT/'训练适用性审核_20261016'
CAT=ROOT/'文献分类与审核准备_20261016'
FOLDERS={'A':'01_优先提取实验数据','B':'02_分体系或限定字段','C':'03_待核与冻结',
         'D':'04_方法与背景','E':'05_范围外资料'}

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKC',s).lower())
def inside(p,root):
    p=p.resolve();assert p.is_relative_to(root.resolve()),(p,root)
    assert p!=root.resolve();return p

def plan():
    assert not (OUT/'整理计划.json').exists(),'Existing plan: inspect instead of regenerating'
    rows=read(AUDIT/'逐份训练用途审核.json')
    byhash={x['sha256']:x for x in rows}
    files=[]
    for p in sorted(LIB.rglob('*')):
        if p.is_file():files.append({'path':str(inside(p,LIB)), 'relative':str(p.relative_to(LIB)),
                                     'bytes':p.stat().st_size,'sha256':digest(p),'suffix':p.suffix.lower()})
    papers=[x for x in files if x['suffix']=='.pdf' and not any(y.startswith('补充材料') for y in Path(x['relative']).parts[:-1])]
    groups=collections.defaultdict(list)
    for f in papers:groups[f['sha256']].append(f)
    assert set(groups)==set(byhash),'New or missing PDFs: audit before organizing'
    assert len(rows)==len(byhash)==122
    actions=[];duplicates=[];mapping={};destinations=set()
    for row in rows:
        candidates=groups[row['sha256']]
        chosen=next((x for x in candidates if x['path']==row['local_pdf']),None)
        assert chosen is not None,row['id']
        if row['use_category']=='F':
            target=OUT/'年份排除_不在文献库'/f'{row["id"]}_2022_椰壳碳预印本.pdf'
        else:
            stem=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',row['title'])
            stem=re.sub(r'\s+',' ',stem).strip(' .')[:100].rstrip(' .')
            folder=LIB/FOLDERS[row['use_category']]/f'{row["id"]}_{row["year"] or "年份待核"}_{stem}'
            target=folder/'正文.pdf'
        assert not target.exists(),target
        assert str(target).casefold() not in destinations;destinations.add(str(target).casefold())
        if row['use_category']!='F':inside(target,LIB)
        else:inside(target,OUT)
        action={'id':row['id'],'category':row['use_category'],'source':chosen['path'],
                'target':str(target),'sha256':row['sha256'],'bytes':chosen['bytes'],'kind':'paper'}
        actions.append(action)
        for f in candidates:
            mapping[f['path']]=str(target)
            if f is not chosen:duplicates.append({**f,'keep_target':str(target),'id':row['id']})
    si_owner={'B001':'R001','B017':'R012','B019':'SRC005','R107':'R107'}
    paper_by_id={x['id']:x for x in actions}
    for f in files:
        if f in papers:continue
        if f['suffix']=='.zip':
            assert Path(f['path']).name=='1.zip'
            target=OUT/'原始压缩包'/'1.zip'
            actions.append({'source':f['path'],'target':str(target),'sha256':f['sha256'],'bytes':f['bytes'],'kind':'archive'})
        else:
            assert any(y.startswith('补充材料') for y in Path(f['relative']).parts[:-1]),f
            owner=si_owner[Path(f['path']).name.split('__')[0]]
            target=Path(paper_by_id[owner]['target']).parent/('补充材料__'+Path(f['path']).name)
            actions.append({'id':owner,'source':f['path'],'target':str(target),'sha256':f['sha256'],'bytes':f['bytes'],'kind':'supplement'})
        mapping[f['path']]=str(target)
    # Check bibliography identity and near-identical text before any destructive deduplication.
    identity={}
    for key in ['doi','title']:
        grouped=collections.defaultdict(list)
        for row in rows:
            if row.get(key):grouped[norm(row[key])].append(row['id'])
        identity[key+'_duplicate_groups']=[v for v in grouped.values() if len(v)>1]
    texts=read(AUDIT/'正文证据定位.json');shingles={}
    for row in texts:
        text=Path(row['fulltext_file']).read_text(encoding='utf-8')
        text=re.split(r'(?im)^\s*(?:\d+\.?\s*)?references\s*$',text)[0]
        words=re.findall('[a-z]{2,}',text.lower())
        shingles[row['id']]={hash(tuple(words[i:i+5])) for i in range(len(words)-4)}
    near=[];ids=list(shingles)
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            x,y=shingles[a],shingles[b]
            if min(len(x),len(y))<200:continue
            common=len(x&y);similarity=common/max(1,min(len(x),len(y)))
            if similarity>=0.65:near.append({'ids':[a,b],'smaller_text_shingle_overlap':round(similarity,4)})
    identity['near_identical_text_candidates']=near
    assert not identity['doi_duplicate_groups'] and not identity['title_duplicate_groups'] and not near,identity
    write(OUT/'书目与正文重复核对.json',identity)
    total=sum(f['bytes'] for f in files if f['suffix']!='.zip')
    assert shutil.disk_usage(OUT).free>total*2+1024**3
    p={'library':str(LIB),'created_date':'2026-10-17','files_before':files,'paper_files_before':len(papers),
       'unique_paper_contents_before':len(groups),'actions':actions,'duplicate_copies_to_recycle':duplicates,
       'old_to_new_paths':mapping,'counts_by_category':dict(collections.Counter(x['category'] for x in actions if x['kind']=='paper')),
       'backup_zip':str(OUT/'整理前文件备份.zip'),'identity_review':identity}
    assert len(duplicates)==21
    assert len(actions)==122+4+1
    write(OUT/'整理计划.json',p)
    print(json.dumps({'files_before':len(files),'paper_files_before':len(papers),'unique_contents':len(groups),
                      'duplicate_copies':len(duplicates),'paper_files_after_in_library':121,'supplements':4,
                      'excluded_pre2023_paper':1,'preserve_original_zip_outside_library':True,
                      'backup_estimated_input_MB':round(total/1024**2,1),'identity_review':identity},ensure_ascii=False,indent=2))

def backup():
    plan=read(OUT/'整理计划.json');target=Path(plan['backup_zip'])
    for f in plan['files_before']:assert digest(Path(f['path']))==f['sha256'],f['path']
    if not target.exists():
        with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=4,allowZip64=True) as z:
            for f in plan['files_before']:
                if f['suffix']!='.zip':z.write(f['path'],Path(f['relative']).as_posix())
    checks=[]
    with zipfile.ZipFile(target) as z:
        assert len(z.infolist())==sum(f['suffix']!='.zip' for f in plan['files_before'])
        for f in plan['files_before']:
            if f['suffix']=='.zip':continue
            assert hashlib.sha256(z.read(Path(f['relative']).as_posix())).hexdigest()==f['sha256'],f['relative']
            checks.append(f['relative'])
    write(OUT/'备份核验.json',{'zip':str(target),'sha256':digest(target),'verified_members':len(checks),
           'original_zip_preserved_separately':True,'all_members_sha256_match':True})
    print(json.dumps({'backup_verified_files':len(checks),'backup_MB':round(target.stat().st_size/1024**2,1)},ensure_ascii=False))

def move():
    plan=read(OUT/'整理计划.json');verified=read(OUT/'备份核验.json')
    assert digest(Path(plan['backup_zip']))==verified['sha256']
    for a in plan['actions']:
        src=Path(a['source']);dst=Path(a['target']);inside(src,LIB)
        assert dst.resolve().is_relative_to(LIB) or dst.resolve().is_relative_to(OUT)
        if dst.exists():assert digest(dst)==a['sha256'] and not src.exists(),(src,dst)
        else:
            assert digest(src)==a['sha256'];dst.parent.mkdir(parents=True,exist_ok=True)
            src.rename(dst)
        assert digest(dst)==a['sha256']
        with (OUT/'移动日志.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(a,ensure_ascii=False)+'\n')
    write(OUT/'移动完成.json',{'files_moved':len(plan['actions']),'all_hashes_match':True})
    print('Moved and verified',len(plan['actions']),'files; duplicates awaiting recycle')

def recycle():
    plan=read(OUT/'整理计划.json');verified=read(OUT/'备份核验.json')
    assert digest(Path(plan['backup_zip']))==verified['sha256']
    assert (OUT/'移动完成.json').exists()
    # Each exact duplicate has a verified retained file plus a separately verified ZIP backup.
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_=[('hwnd',ctypes.c_void_p),('wFunc',ctypes.c_uint),('pFrom',ctypes.c_wchar_p),
                  ('pTo',ctypes.c_wchar_p),('fFlags',ctypes.c_ushort),('fAnyOperationsAborted',ctypes.c_bool),
                  ('hNameMappings',ctypes.c_void_p),('lpszProgressTitle',ctypes.c_wchar_p)]
    fn=ctypes.windll.shell32.SHFileOperationW;fn.argtypes=[ctypes.POINTER(SHFILEOPSTRUCTW)];fn.restype=ctypes.c_int
    recycled=[]
    for a in plan['duplicate_copies_to_recycle']:
        src=inside(Path(a['path']),LIB);kept=Path(a['keep_target'])
        assert digest(kept)==a['sha256'] and src!=kept
        if src.exists():
            assert digest(src)==a['sha256']
            buf=ctypes.create_unicode_buffer(str(src)+'\0\0')
            op=SHFILEOPSTRUCTW();op.wFunc=3;op.pFrom=ctypes.cast(buf,ctypes.c_wchar_p)
            op.fFlags=0x0040|0x0010|0x0400|0x0004
            result=fn(ctypes.byref(op))
            assert result==0 and not op.fAnyOperationsAborted and not src.exists(),(src,result)
        recycled.append({'path':str(src),'sha256':a['sha256'],'retained':str(kept),'status':'recycled'})
        with (OUT/'重复副本回收日志.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(recycled[-1],ensure_ascii=False)+'\n')
    # Only remove enumerated empty directories below the known library root.
    removed=[]
    for folder in sorted((p for p in LIB.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        inside(folder,LIB)
        if not any(folder.iterdir()):folder.rmdir();removed.append(str(folder))
    write(OUT/'去重完成.json',{'recycled_exact_duplicates':len(recycled),'removed_empty_directories':removed})
    print('Recycled',len(recycled),'verified duplicates; removed',len(removed),'empty folders')

def indexes():
    plan=read(OUT/'整理计划.json');rows=read(AUDIT/'逐份训练用途审核.json')
    moves={a['id']:a for a in plan['actions'] if a['kind']=='paper'}
    supplements=collections.defaultdict(list)
    for a in plan['actions']:
        if a['kind']=='supplement':supplements[a['id']].append(a['target'])
    for row in rows:
        a=moves[row['id']]
        if row['use_category']=='F':continue
        folder=Path(a['target']).parent
        text=f'# {row["title"]}\n\n编号：{row["id"]}。年份：{row["year"] or "待核"}。\n\n'
        text+=f'训练用途：{row["use_label"]}。\n\n{row["reason"]}\n\n{row["restrictions"]}\n\n'
        text+='[打开正文](正文.pdf)\n\n'
        for si in supplements[row['id']]:text+=f'[补充材料](<{Path(si).name}>)\n\n'
        if row.get('doi'):text+=f'DOI：[{row["doi"]}](https://doi.org/{row["doi"]})\n\n'
        text+='文献用途分类不等于具体实验记录已经获准进入训练库。\n'
        (folder/'使用说明.md').write_text(text,encoding='utf-8')
    # A single searchable local entry point, without duplicating any PDF.
    html_rows=[]
    for row in rows:
        if row['use_category']=='F':continue
        a=moves[row['id']];relative=Path(a['target']).relative_to(LIB).as_posix()
        html_rows.append('<tr data-cat="'+row['use_category']+'"><td>'+html.escape(row['id'])+'</td><td>'+str(row['year'] or '待核')+'</td>'
           '<td>'+html.escape(row['use_label'])+'</td><td><a href="'+quote(relative,safe='/')+'">'+html.escape(row['title'])+'</a></td>'
           '<td>'+html.escape(row['restrictions'])+'</td></tr>')
    options=''.join(f'<option value="{k}">{v[3:]}</option>' for k,v in FOLDERS.items())
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>文献目录</title><style>
body{font:15px/1.6 "Microsoft YaHei",sans-serif;margin:32px;color:#24303a}h1{font-size:25px}input,select{font:inherit;padding:8px;margin:6px 12px 18px 0}input{width:420px}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dde3e8}th{background:#273a4c;color:white;position:sticky;top:0}tr:nth-child(even){background:#f4f7f9}a{color:#135e99}td:nth-child(1){white-space:nowrap}td:nth-child(4){width:36%}td:nth-child(5){width:34%}.muted{color:#566470}</style>
<h1>文献目录</h1><p>121份不重复论文，4份补充材料。主要来源候选39，分体系或限定字段17，待核14，方法背景24，范围外27。</p>
<p class="muted">按文件内容去重，并核对DOI、题名及近似正文。2022年预印本和原始压缩包已移出当前文献库，保存在项目归档中。用途分类不等于实验记录已获准训练。</p>
<input id="q" type="search" placeholder="搜索题名、编号、年份或使用限制"><select id="cat"><option value="">全部分类</option>'''+options+'''</select><span id="count"></span>
<table><thead><tr><th>编号</th><th>年份</th><th>用途</th><th>题名（点击打开PDF）</th><th>使用限制</th></tr></thead><tbody>'''+''.join(html_rows)+'''</tbody></table>
<script>const q=document.querySelector('#q'),c=document.querySelector('#cat'),rs=[...document.querySelectorAll('tbody tr')];function filter(){let n=0;for(const r of rs){const ok=(!c.value||r.dataset.cat===c.value)&&r.textContent.toLowerCase().includes(q.value.toLowerCase());r.hidden=!ok;if(ok)n++;}document.querySelector('#count').textContent='显示 '+n+' 份';}q.addEventListener('input',filter);c.addEventListener('change',filter);filter();</script></html>'''
    (LIB/'打开文献目录.html').write_text(page,encoding='utf-8')
    (LIB/'整理说明.md').write_text('''# 文献库使用说明

整理日期：2026-10-17。

当前有121份按内容去重的论文PDF，另有4份补充材料（3个PDF、1个Word）。每篇独占一个按编号、年份和题名命名的文件夹，内含正文及已取得的对应补充材料；使用说明列出用途和限制。

01_优先提取实验数据：39份。
02_分体系或限定字段：17份。
03_待核与冻结：14份。
04_方法与背景：24份。
05_范围外资料：27份。

可打开“打开文献目录.html”搜索并筛选。没有复制PDF作为分类入口。

21份内容完全相同的副本已在核验保留件后移入回收站。1份2022年预印本移出当前文献库，原始1.zip移到项目归档，均保留追溯。整理前147个文件的内容备份、原ZIP及逐件位置映射位于D:/机器学习-超级电容器/文献整理_20261017。

训练用途报告和总表仍在项目的“训练适用性审核_20261016”目录，已同步当前路径。目录分类不等于训练数据已经准入。
''',encoding='utf-8')
    write(OUT/'当前唯一文献位置.json',[{'id':a['id'],'category':a['category'],'local_pdf':a['target'],'sha256':a['sha256'],
                    'in_active_library':a['category']!='F','supplements':supplements[a['id']]} for a in plan['actions'] if a['kind']=='paper'])
    print('Created searchable directory and per-paper notes')

if __name__=='__main__':
    {'plan':plan,'backup':backup,'move':move,'recycle':recycle,'indexes':indexes}[sys.argv[1]]()

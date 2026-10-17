import json,urllib.request,concurrent.futures,hashlib,zipfile,io
from pathlib import Path
from lxml import etree
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
logs=[]
for fn in ['扩搜补充材料获取日志.json','三电极及追加补充材料获取日志.json']:
    f=ROOT/fn
    if f.exists():logs.extend(json.loads(f.read_text(encoding='utf-8')))
jobs=[x for x in logs if any(y.lower().endswith('.zip') for y in x.get('archive_members',[]))]
def run(x):
    wid=x['id'];d=ROOT/'sources'/wid;rec={'working_id':wid,'url':x['url'],'documents':[],'nested_archives':[]}
    try:
        with urllib.request.urlopen(x['url'],timeout=35) as r:b=r.read(40000001)
        assert len(b)<=40000000
        (d/'supplementary_package.zip').write_bytes(b)
        def extract(data,depth=0):
            z=zipfile.ZipFile(io.BytesIO(data))
            for m in z.infolist():
                if m.file_size>25000000 or m.is_dir():continue
                name=Path(m.filename).name
                if name.lower().endswith('.zip') and depth<2:
                    rec['nested_archives'].append(m.filename);extract(z.read(m),depth+1)
                elif name.lower().endswith(('.pdf','.docx','.txt','.csv','.xlsx','.xls')):
                    bb=z.read(m);p=d/name
                    if p.exists() and p.read_bytes()!=bb:p=d/('nested'+str(depth)+'_'+name)
                    if not p.exists():p.write_bytes(bb)
                    detail={'path':str(p),'bytes':len(bb),'sha256':hashlib.sha256(bb).hexdigest()}
                    if name.lower().endswith('.pdf'):
                        try:
                            ps=[{'page':i+1,'text':pg.extract_text() or ''} for i,pg in enumerate(PdfReader(io.BytesIO(bb)).pages)];(d/(p.name+'.pages.json')).write_text(json.dumps(ps,ensure_ascii=False,indent=2),encoding='utf-8');detail['pages']=len(ps)
                        except Exception as e:detail['text_error']=str(e)
                    elif name.lower().endswith('.docx'):
                        zz=zipfile.ZipFile(io.BytesIO(bb));tx=' '.join(etree.fromstring(zz.read('word/document.xml')).itertext());(d/(p.name+'.txt')).write_text(tx,encoding='utf-8')
                    rec['documents'].append(detail)
                elif depth==0 and wid in ['OA003','OA006','OA022','OA025','OA050','OA059','OA060'] and name.lower().endswith(('.jpg','.png','.webp')) and any(k in name for k in ['g007','g008','g011']):
                    p=d/name
                    if not p.exists():p.write_bytes(z.read(m))
        extract(b);rec['status']='nested_documents_extracted'
    except Exception as e:rec.update(status='failed_no_bypass',error=str(e))
    print(wid,rec['status'],[Path(q['path']).name for q in rec['documents']],flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:out=list(ex.map(run,jobs))
(ROOT/'嵌套补充材料解包日志.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

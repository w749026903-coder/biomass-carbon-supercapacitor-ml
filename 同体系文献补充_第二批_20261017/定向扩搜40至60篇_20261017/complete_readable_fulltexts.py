import json,urllib.request,concurrent.futures,zipfile,io,hashlib,html,re
from pathlib import Path
from lxml import etree
ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/'新增50篇_逐篇数据与获取状态.json').read_text(encoding='utf-8'))
def run(r):
    d=ROOT/'sources'/r['working_id'];p=d/'main.xml'
    if not p.exists():return None
    t=etree.parse(str(p),etree.XMLParser(resolve_entities=False,no_network=True));ids=t.xpath('//article-id[@pub-id-type="pmc"]/text()');pc=None
    if ids:pc=ids[0];pc=pc if pc.startswith('PMC') else 'PMC'+pc
    if not pc:
        a=json.loads((d/'acquisition.json').read_text(encoding='utf-8'));pc=a.get('pmcid')
        if not pc:
            pc=next((x.get('pmcid') for x in json.loads((ROOT/'OA初筛待全文核查.json').read_text(encoding='utf-8')) if x['working_id']==r['working_id']),None)
    rec={'working_id':r['working_id'],'doi':r['doi'],'figures_saved':[],'documents_saved':[]}
    if pc:
        u=f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pc}/supplementaryFiles';rec['url']=u
        try:
            package=d/'supplementary_package.zip'
            if package.exists():b=package.read_bytes();rec['package_reused']=True
            else:
                with urllib.request.urlopen(u,timeout=40) as rr:b=rr.read(120000001)
                assert len(b)<=120000000,'package exceeds 120 MB cap'
                package.write_bytes(b);rec['package_reused']=False
            def unpack(blob,depth=0):
                z=zipfile.ZipFile(io.BytesIO(blob))
                for m in z.infolist():
                    if m.file_size>30000000 or m.is_dir():continue
                    name=Path(m.filename).name;ext=Path(name).suffix.lower()
                    if ext=='.zip' and depth<2:unpack(z.read(m),depth+1)
                    elif ext in ['.pdf','.docx','.doc','.txt','.csv','.xlsx','.xls']:
                        bb=z.read(m);out=d/name
                        if out.exists() and out.read_bytes()!=bb:out=d/('depth'+str(depth)+'_'+name)
                        if not out.exists():out.write_bytes(bb)
                        rec['documents_saved'].append(str(out))
                    elif ext in ['.jpg','.jpeg','.png','.webp','.gif','.svg','.tif','.tiff']:
                        if ext=='.gif' and any(q.filename==m.filename[:-4]+'.jpg' for q in z.infolist()):continue
                        fd=d/'figures';fd.mkdir(exist_ok=True);out=fd/name
                        if not out.exists():out.write_bytes(z.read(m))
                        rec['figures_saved'].append(str(out))
            unpack(b);rec['package_status']='obtained_and_validated_zip';rec['package_sha256']=hashlib.sha256(b).hexdigest()
        except Exception as e:rec.update(package_status='failed_no_bypass',error=str(e))
    else:rec.update(package_status='no_pmc_id_found')
    figs={p.stem:p for p in (d/'figures').glob('*')} if (d/'figures').exists() else {}
    missing=[]
    def esc(s):return html.escape(s or '',quote=True)
    def render(n,level=2):
        if not isinstance(n.tag,str):return ''
        tag=etree.QName(n).localname
        content=esc(n.text)
        for c in n:content+=render(c,level+1 if tag=='sec' else level)+esc(c.tail)
        if tag in ['sec']:return '<section>'+content+'</section>'
        if tag in ['title','article-title']:return f'<h{min(level,4)}>'+content+f'</h{min(level,4)}>'
        if tag=='p':return '<p>'+content+'</p>'
        if tag in ['italic','bold','sup','sub']:return '<'+{'italic':'i','bold':'b'}.get(tag,tag)+'>'+content+'</'+{'italic':'i','bold':'b'}.get(tag,tag)+'>'
        if tag in ['table','thead','tbody','tfoot','tr','td','th']:
            attrs=''.join(f' {k}="{esc(v)}"' for k,v in n.attrib.items() if k in ['colspan','rowspan']);return '<'+tag+attrs+'>'+content+'</'+tag+'>'
        if tag in ['table-wrap','fig']:return '<div class="object">'+content+'</div>'
        if tag in ['label']:return '<b>'+content+'</b> '
        if tag=='graphic':
            href=n.get('{http://www.w3.org/1999/xlink}href','');key=Path(href).stem
            f=figs.get(key)
            if not f:
                f=next((v for k,v in figs.items() if k==href or k.startswith(href+'.')),None)
            if f:return '<img loading="lazy" src="'+esc(f.relative_to(d).as_posix())+'" alt="原文图 '+esc(href)+'">'
            if href:missing.append(href)
            return '<p class="note">原图未本地取得：'+esc(href)+'</p>'
        if tag=='math':
            import copy
            mathnode=copy.deepcopy(n)
            for item in mathnode.iter():
                if isinstance(item.tag,str):item.tag=etree.QName(item).localname
            etree.cleanup_namespaces(mathnode);mathnode.set('xmlns','http://www.w3.org/1998/Math/MathML')
            return etree.tostring(mathnode,encoding='unicode',with_tail=False)
        if tag=='xref':return '<span>'+content+'</span>'
        if tag=='ext-link':
            u=n.get('{http://www.w3.org/1999/xlink}href','')
            return '<a href="'+esc(u)+'">'+content+'</a>' if u.startswith(('http://','https://')) else content
        if tag in ['list','ref-list']:return '<div>'+content+'</div>'
        if tag in ['list-item','ref']:return '<p>'+content+'</p>'
        if tag in ['inline-formula','disp-formula']:return '<span class="formula">'+content+'</span>'
        return content
    parts=[]
    for n in t.xpath('/article/front/article-meta/abstract|/article/body'):parts.append(render(n))
    # JATS often places figures/tables after the body; show those not already embedded.
    for n in t.xpath('/article/floats-group/*|/article/back/ref-list'):parts.append(render(n))
    doc='<!doctype html><html lang="en"><meta charset="utf-8"><title>'+esc(r['title'])+'</title><style>body{max-width:1000px;margin:40px auto;padding:0 24px;font:17px/1.7 Georgia,serif;color:#202327}h1{font-size:30px;line-height:1.3}h2,h3,h4{font-family:Arial,sans-serif}img{display:block;max-width:100%;height:auto;margin:20px auto}table{border-collapse:collapse;max-width:100%;font-size:15px}td,th{border:1px solid #ccc;padding:5px}.note{padding:14px;background:#f2f5f8;font:14px/1.6 Arial,sans-serif}.object{overflow:auto;margin:24px 0;padding:12px;border-top:1px solid #ddd}.formula{overflow-wrap:anywhere}a{color:#165ca3}</style><h1>'+esc(r['title'])+'</h1><p><a href="https://doi.org/'+esc(r['doi'])+'">DOI: '+esc(r['doi'])+'</a></p><p class="note">本地阅读版，依据出版社提交至PMC的原始JATS XML整理，供核对正文、图注、表格和原图。原始main.xml完整保留；此页不是出版社版式PDF。所有数字与正文冲突均保留原文，未修正或推算。实验准入状态见逐篇审核表。</p>'+''.join(parts)+'</html>'
    (d/'readable_article.html').write_text(doc,encoding='utf-8');rec['reader_path']=str(d/'readable_article.html');rec['missing_graphic_references']=sorted(set(missing));rec['expected_graphic_references']=len(t.xpath('//graphic'));rec['figures_saved']=list(dict.fromkeys(rec['figures_saved']));rec['documents_saved']=list(dict.fromkeys(rec['documents_saved']))
    (d/'reader_acquisition.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8');print(r['working_id'],rec['package_status'],'images',len(rec['figures_saved']),'unmatched',len(rec['missing_graphic_references']),flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:out=[x for x in ex.map(run,data['records']) if x]
(ROOT/'完整正文原图与阅读版获取记录.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

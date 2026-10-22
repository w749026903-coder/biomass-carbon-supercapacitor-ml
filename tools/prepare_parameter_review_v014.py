"""Read main-cohort originals and save compact method packets, not automatic values."""
from pathlib import Path
import collections,hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E
import pypdfium2 as P
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.cycling_db import open_database
BATCH=ROOT/'主集参数精提取_20261022'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    target=BATCH/'method_packets.json'
    if target.exists():raise FileExistsError('Use the saved packets; do not overwrite.')
    with open_database() as db:rows=db.fetch().rows;assert db.contract['version']=='v0.13'
    idx=sqlite3.connect((ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite').as_uri()+'?mode=ro',uri=True);idx.row_factory=sqlite3.Row
    grouped=collections.defaultdict(list)
    for r in rows:grouped[r['source_group'].removeprefix('doi:')].append(r)
    packets=[]
    for doi,rr in grouped.items():
        ss=[dict(r) for r in idx.execute("select distinct s.path,s.format,s.sha256 from sources s join identity_sources i using(sha256) where i.identity_key=? and s.format in ('pdf','xml')",('doi:'+doi,))]
        primary=[s for s in ss if Path(s['path']).name in ['main.xml','main.pdf','公开全文.xml'] or Path(s['path']).name.startswith('ADD_')]
        primary.sort(key=lambda s:(s['format']!='xml',len(s['path'])))
        assert primary,doi
        source=primary[0];p=Path(source['path']);assert sha(p)==source['sha256']
        segments=[]
        if source['format']=='xml':
            root=E.fromstring(p.read_bytes());body=root.find('body')
            allp=list(root.iter('p'));ordinals={id(x):i+1 for i,x in enumerate(allp)};seen=set()
            for sec in body.iter('sec'):
                title=' '.join(sec.findtext('title','').split())
                if not re.search(r'method|experimental|prepar|synthes|fabricat|electrochemical measure|electrode prepar',title,re.I):continue
                for para in sec.iter('p'):
                    if id(para) in seen:continue
                    seen.add(id(para));text=' '.join(' '.join(para.itertext()).split())
                    if text:segments.append(dict(locator=f'XML p {ordinals[id(para)]}; section {title}',text=text))
        else:
            doc=P.PdfDocument(p)
            for n in range(len(doc)):
                pg=doc[n];tp=pg.get_textpage();text=' '.join(tp.get_text_range().split());tp.close();pg.close()
                early=n<6 and re.search(r'synthes|prepar|experimental|activat|mass loading',text,re.I)
                late=re.search(r'Experimental Section|\d\.\d\.?\s*(?:Synthesis|Preparation|Electrochemical)|\d\s+Materials and Methods',text,re.I)
                if n>=1 and (early or late):segments.append(dict(locator=f'PDF p{n+1}',text=text))
            doc.close()
        packets.append(dict(doi=doi,endpoint_ids=[r['endpoint_id'] for r in rr],samples=[r['sample_name'] for r in rr],source=source,segments=segments))
    idx.close();BATCH.mkdir(exist_ok=True)
    target.write_text(json.dumps(packets,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(sources=len(packets),tests=len(rows),segments=sum(len(p['segments']) for p in packets)),ensure_ascii=False))
if __name__=='__main__':main()

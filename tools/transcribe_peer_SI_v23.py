"""Read native peer SI cells including page-break rows omitted by detected grids; no admission."""
from pathlib import Path
from contextlib import closing
import collections,json,re,sys
import pdfplumber
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro
OUT=ROOT/'文献全量利用复核_20261028/批次23_同体系机器学习蜜瓜皮鹅羽与综述对账'
PDF=ROOT/'文献下载_120篇/补充材料暂存/B001__CPLU-90-e202500342-s001.pdf'
PSHA='253ce243da966ccd4ed81adabfc92ea589a564d61fa28327214ea2064b00a590'
CURATOR='10.1002/cplu.202500342'
def extract():
    assert sha(PDF)==PSHA
    rows=[];receipts=[]
    with pdfplumber.open(PDF)as pdf:
        header_table=pdf.pages[1].find_tables()[0];header=header_table.extract()[0]
        edges=[c.bbox[0]for c in header_table.columns]+[header_table.columns[-1].bbox[2]]
        assert len(edges)==15 and len(header)==14
        for pno in range(2,9):
            page=pdf.pages[pno-1];tables=page.find_tables();assert len(tables)==1;table=tables[0];grid=table.extract();first=[]
            if pno>2:
                # The native continuation lacks its upper border. Its first row is above the detected grid.
                box=[edges[0],50,edges[-1],table.bbox[1]];words=page.crop(tuple(box)).extract_words();cells=[];word_proof=[]
                for a,b in zip(edges[:-1],edges[1:]):
                    found=[w for w in words if a<=(w['x0']+w['x1'])/2<b];cells.append(' '.join(w['text']for w in found));word_proof.append(found)
                assert cells[0].isdigit()and re.fullmatch(r'10\.\d{4,9}/\S+',cells[1],re.I)
                first=[dict(native_cells=cells,method='pagebreak_first_row_native_words',region=box,column_word_proof=word_proof)]
            native=first+[dict(native_cells=g,method='native_grid',grid_row=i+1,cell_bboxes=table.rows[i].cells)for i,g in enumerate(grid)if g[0]and str(g[0]).isdigit()]
            for q in native:
                cells=[' '.join(str(v).split())if v is not None else''for v in q['native_cells']];assert len(cells)==14
                no=int(cells[0]);doi=cells[1].lower();assert re.fullmatch(r'10\.\d{4,9}/\S+',doi)
                for v in cells[5:]:assert re.fullmatch(r'\d+(?:\.\d+)?',v),[no,v]
                rows.append(dict(row_number=no,cited_doi=doi,curator_doi=CURATOR,native_cells=q['native_cells'],cells=cells,numeric_values=[float(v)for v in cells[5:]],page=pno,source_sha256=PSHA,source_path=PDF.relative_to(ROOT).as_posix(),locator='SI TableS1 printedrow '+str(no),provenance=q,training_eligible=False,source_role='peer_secondary_compilation_not_new_own_material_observation',primary_protocol_verified=False))
            receipts.append(dict(page=pno,bbox=table.bbox,native_grid=grid,first_recovered=first,column_edges=edges))
    assert [r['row_number']for r in rows]==list(range(1,167))and len(rows)==166
    groups=collections.defaultdict(list);collisions=collections.defaultdict(list)
    for r in rows:
        c=r['cells'];features=tuple([r['cited_doi']]+c[2:5]+r['numeric_values'][:-1]);groups[features+(r['numeric_values'][-1],)].append(r['row_number']);collisions[features].append(r)
    exact=[x for x in groups.values()if len(x)>1]
    conflicts=[dict(row_numbers=[r['row_number']for r in rr],capacitance_values=[r['numeric_values'][-1]for r in rr],cited_doi=rr[0]['cited_doi'],reason='Identical recordedDOI and all11features, different reportedtargets; sample/protocol identifiers missing, no primaryerror diagnosis or autocorrection')for rr in collisions.values()if len({r['numeric_values'][-1]for r in rr})>1]
    dois=sorted({r['cited_doi']for r in rows});local={}
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as c:
        for doi in dois:
            rr=c.execute('select distinct s.path,s.format,s.sha256 from sources s join identity_sources i using(sha256)where lower(i.identity_key)=?',('doi:'+doi,)).fetchall();local[doi]=[dict(path=x[0],format=x[1],sha256=x[2])for x in rr]
    return dict(status='native_transcription_not_primary_admission',source_path=PDF.relative_to(ROOT).as_posix(),source_sha256=PSHA,header=header,rows=rows,page_receipts=receipts,raw_rows=166,cited_DOI_strings=len(dois),exact_duplicate_row_sets=exact,identical_recorded_features_conflicting_labels=conflicts,local_primary_evidence=local,locally_available_cited_DOI_strings=sum(bool(v)for v in local.values()),full_primary_protocols_verified=False,formal_training_admissions=0,model_fits=0,not_independent_material_count=True)
if __name__=='__main__':
    target=OUT/'peer_SI_S1_native_transcription.json';assert not target.exists()and not(OUT/'merge_manifest.json').exists()
    result=extract();write(target,result)
    print(json.dumps({k:v for k,v in result.items()if k in ['status','raw_rows','cited_DOI_strings','exact_duplicate_row_sets','identical_recorded_features_conflicting_labels','locally_available_cited_DOI_strings']},ensure_ascii=False))

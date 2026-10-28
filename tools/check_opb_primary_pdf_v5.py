"""Independent fresh-PDF check; run using the existing PDF-capable runtime."""
from pathlib import Path
import hashlib,json,re,sys
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'全量文献训练数据接入_v5_OPB主集关联_20261028'
SOURCE=ROOT/'三电极端点扩充_20261018/corpus/U002/main.pdf'

def main():
    assert not(OUT/'merge_manifest.json').exists()
    r=PdfReader(SOURCE);pages=[' '.join(p.extract_text().split())for p in r.pages];facts=json.loads((OUT/'new_facts.json').read_text('utf8'));caps=json.loads((OUT/'new_capacity_reports.json').read_text('utf8'));checked=[];checks=[]
    def ck(label,ok):assert ok,label;checks.append(label)
    rows=re.findall(r'\b(OPC|OPB|OPNP|OPBNP)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',pages[11]);ck('four_table_rows',len(rows)==4)
    names=['XRD_d002_nm','Raman_ID_IG','BET_surface_area_m2_g','total_pore_volume_cm3_g','HK_micropore_volume_cm3_g','average_pore_diameter_nm']
    for row in rows:
        for field,token in zip(names,row[1:]):
            f=next(f for f in facts if f['sample_name']==row[0]and f['field_name']==field);ck('fresh_table_cell:'+row[0]+field,f['value']==float(token));checked.append(f['fact_id'])
    d=re.search(r'D bands of OPC, OPB, OPNP and OPBNP are (.*?) cm',pages[11]);g=re.search(r'G bands are (.*?) cm',pages[11]);ck('Raman_lists_present',d is not None and g is not None)
    for field,match in [('Raman_D_position_cm_inv',d),('Raman_G_position_cm_inv',g)]:
        values=[float(v)for v in re.findall(r'\d+(?:\.\d+)?',match[1])];ck('four_positions:'+field,len(values)==4)
        for name,v in zip(['OPC','OPB','OPNP','OPBNP'],values):
            f=next(f for f in facts if f['sample_name']==name and f['field_name']==field);ck('Raman_position:'+name+field,f['value']==v);checked.append(f['fact_id'])
    span=pages[12]+pages[13];match=re.search(r'coexistence of C, O, N, B and P elements.*?contents were (.*?) respectively',span);ck('explicit_XPS_order',match is not None)
    vals=[float(v)for v in re.findall(r'(\d+(?:\.\d+)?)%',match[1])];ck('five_XPS_reports',len(vals)==5)
    for el,v in zip(['C','O','N','B','P'],vals):
        f=next(f for f in facts if f['field_name']=='XPS_'+el+'_reported_pct');ck('XPS_literal:'+el,f['value']==v and f['unit']=='%basis_unspecified'and not f['selected_for_this_purpose']);checked.append(f['fact_id'])
    m=re.search(r'loading mass of active material was (\d+)-(\d+) mg',pages[6],re.I);ck('loading_interval_in_source',m is not None)
    for name in ['OPC','OPB','OPNP','OPBNP']:
        for field,token in [('electrode_active_loading_lower_mg_cm2',m[1]),('electrode_active_loading_upper_mg_cm2',m[2])]:
            f=next(f for f in facts if f['sample_name']==name and f['field_name']==field);ck('loading_boundary:'+name+field,f['value']==int(token)and f['value_kind']=='protocol_interval_boundary');checked.append(f['fact_id'])
    match=re.search(r'corresponding specific capacitance of OPBNP is (.*?) F g',pages[14]);vals=[float(v)for v in re.findall(r'\d+(?:\.\d+)?',match[1])];ck('five_OPBNP_rate_values',len(vals)==5)
    for j,v in zip([1,2,5,10,20],vals):ck('rate_target:'+str(j),any(q['sample_name']=='OPBNP'and q['conditions']['reported_current_A_g']==j and q['value']==v for q in caps))
    for name,token in re.findall(r'\b(OPC|OPB|OPNP) \(([\d.]+) F g',pages[14]):ck('other_1A_target:'+name,any(q['sample_name']==name and q['conditions']['reported_current_A_g']==1 and q['value']==float(token)for q in caps))
    out=dict(status='passed',checks=len(checks),checked_fact_ids=sorted(set(checked)),source_path=SOURCE.relative_to(ROOT).as_posix(),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),method='Fresh pypdf extraction independent of curator numeric constants',table_rows=4,source_loading_interval=[int(m[1]),int(m[2])])
    (OUT/'pdf_primary_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(status='passed',checks=len(checks),facts=len(set(checked)))))

if __name__=='__main__':main()

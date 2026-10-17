from pathlib import Path
import collections,hashlib,json,re,sys,zipfile,xml.etree.ElementTree as ET
from docx import Document
sys.stdout.reconfigure(encoding='utf-8')
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=read(BASE/'逐份训练用途审核.json');summary=read(BASE/'审核汇总.json')
inv=read(ROOT/'文献分类与审核准备_20261016/本地与压缩包文件盘点.json')
assert len(rows)==len({x['id'] for x in rows})==len({x['sha256'] for x in rows})==122
assert {x['sha256'] for x in rows}=={x['sha256'] for x in inv['records']}
for row in rows:
    assert sha(Path(row['local_pdf']))==row['sha256']
    assert row['reason'] and row['restrictions'] and row['evidence']
    assert row['old_list_membership_used_as_filter'] is False
    assert row['eligible_for_database'] is False
    assert (BASE/'逐份证据卡'/f'{row["id"]}.md').is_file()
    assert all(1<=n<=row['pages'] for n in row['evidence_pdf_pages'])
files=[p for p in Path(r'D:\文献').rglob('*.pdf') if not any(s.startswith('补充材料') for s in p.relative_to(Path(r'D:\文献')).parts[:-1])]
assert {sha(p) for p in files}=={x['sha256'] for x in rows},'New or missing PDF contents since audit'
assert dict(collections.Counter(x['use_category'] for x in rows))=={k:v['count'] for k,v in summary['categories'].items()}
assert sum(x['useful_for_experimental_extraction'] for x in rows)==56
ids={x['id']:x for x in rows}
for pid in ['R088','SRC023','SRC071','SRC073','SRC086']:
    assert ids[pid]['use_category']=='C'
assert ids['SRC113']['use_category']=='F'
assert ids['SRC005']['use_category']=='A' and ids['R005']['use_category']=='A'
assert ids['SRC087']['use_category']=='D' and ids['R002']['use_category']=='D'
pilot=read(BASE/'R005_4个原始实验样例_待逐记录准入.json')
assert len(pilot)==len({x['sample_label_original'] for x in pilot})==4
assert {x['sample_label_original']:x['reported_specific_capacitance_F_g'] for x in pilot}=={
       'PW-650–1':362.2,'PW-650–3':346.6,'PW-400–3':353.3,'PW-400–1':276.0}
assert all(x['carbonization_atmosphere'] is None for x in pilot)
si=read(BASE/'R107_SI_6材料30测试_报告值样例.json')
assert len(si['materials'])==6 and len(si['tests'])==30
assert all(x['eligible_for_database'] is False for x in pilot+si['materials']+si['tests'])
assert len({(x['sample_label_original'],x['current_density_A_g']) for x in si['tests']})==30
source=Path(si['tests'][0]['source_file']);tables=Document(source).tables
for index in [1,3]:
    for row in tables[index].rows[2:]:
        values=[x.text.strip() for x in row.cells]
        actual={x['current_density_A_g']:x['reported_specific_capacitance_F_g'] for x in si['tests'] if x['sample_label_original']==values[0]}
        assert list(actual.values())==[float(x) for x in values[1:]]
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(BASE/'训练用途审核总表.xlsx') as z:
    book=ET.fromstring(z.read('xl/workbook.xml'));assert len(book.find('m:sheets',ns))==1
    tree=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    cells=tree.findall('.//m:sheetData/m:row/m:c',ns)
    assert not [x for x in cells if x.get('t')=='e']
    strings=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    def value(cell):
        v=cell.find('m:v',ns)
        if cell.get('t')=='s':return strings[int(v.text)]
        if cell.get('t')=='inlineStr':return ''.join(cell.find('m:is',ns).itertext())
        return v.text if v is not None else ''
    data={x.get('r'):value(x) for x in cells}
    assert data['B4']=='56' and data['B5']=='122' and data['B6']=='14'
    for i,row in enumerate(rows,10):
        assert data[f'A{i}']==row['id'] and data[f'C{i}']==row['use_label']
        assert data[f'E{i}']==row['reason'] and data[f'F{i}']==row['restrictions']
        assert data[f'I{i}']==row['local_pdf']
    pane=tree.find('.//m:pane',ns).attrib
    assert pane['xSplit']=='2' and pane['ySplit']=='9'
    assert len(tree.findall('.//m:tablePart',ns))==1
for p in [BASE/'训练用途审核报告.md',*(BASE/'逐份证据卡').glob('*.md')]:
    text=p.read_text(encoding='utf-8')
    for link in re.findall(r'\]\(<?([^\n>]+?)>?\)',text):
        if link.startswith(('http:','https:','#')):continue
        target=Path(link) if re.match(r'^[A-Za-z]:',link) else p.parent/link
        assert target.exists(),(p,link)
verification={'date':'2026-10-17','all_122_pdf_hashes_verified':True,
              'current_library_has_no_unreviewed_pdf_content':True,
              'all_122_have_individual_decisions_and_evidence_cards':True,
              'old_list_membership_not_used_as_selection_criterion':True,
              'all_existing_freezes_preserved':True,'source_candidates':56,
              'R005_4_reported_examples_checked':True,'R107_6_materials_30_tests_match_original_tables':True,
              'R107_supplement_sha256':sha(source),'workbook_rows':122,'workbook_formula_errors':0,
              'workbook_filter_table_and_freeze_panes_present':True,'all_report_links_exist':True,
              'no_formal_training_rows_approved':True,'no_model_run':True}
(BASE/'最终一致性核验.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(verification,ensure_ascii=False,indent=2))

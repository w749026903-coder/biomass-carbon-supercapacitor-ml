"""Read-only validation of the independent ledger, sources, copies and links.
Writes only this task's validation report. Does not download, classify, or fit.
"""
from pathlib import Path
import json,hashlib,collections,xml.etree.ElementTree as ET,re,urllib.parse,html.parser
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text('utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(p):p=Path(p);return p if p.is_absolute() else ROOT/p
checks=[]
def check(name,passed,detail=None):checks.append({'name':name,'pass':bool(passed),'detail':detail})
class Links(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.images=0
 def handle_starttag(self,t,a):
  for k,v in a:
   if k in ['src','href'] and v:self.links.append(v)
  if t=='img':self.images+=1
if __name__=='__main__':
 ledger=read(OUT/'三电极端点_53条.json')['rows'];lib=read(OUT/'文献类型分类索引.json');counts=read(OUT/'endpoint_counts.json')
 check('goal_more_than_50_verified_staged_3E_GCD_endpoints',len(ledger)>50,len(ledger))
 keys=[(r['doi'],r['sample'],r['electrolyte'],r['concentration_mol_L'],r['cycle_method'],r['cycle_count'],r['reported_current_A_g'],str(r['reported_current_other'])) for r in ledger]
 check('no_duplicate_endpoint_key',len(keys)==len(set(keys)))
 check('41_DOI_study_groups_not_53_independent_papers',len({r['doi'] for r in ledger})==41)
 check('53_rows_have_unique_ID',len({r['endpoint_id'] for r in ledger})==53)
 check('all_3E_GCD_explicit_profile',all(r['system']=='3E' and r['cycle_method']=='GCD' and r['counted'] for r in ledger))
 check('positive_N_retention_and_N_integer',all(isinstance(r['cycle_count'],int) and r['cycle_count']>0 and r['retention_pct']>0 for r in ledger))
 check('43_exact_6_approx_4_loss_complement',counts['reported_point']==43 and counts['reported_approximate']==6 and counts['loss_complement']==4)
 check('loss_complement_transparent_and_correct',all(abs(r['retention_pct']-(100-r['reported_loss_pct']))<1e-7 for r in ledger if r['value_kind']=='loss_complement'))
 check('approx_relation_preserved',all(r['retention_relation']=='approx' for r in ledger if r['source_tag'] in ['EXT_011','U021','PMC6843703','PMC8838214','B_R085','PMC7770663']))
 check('same_DOI_same_study_group',all(r['study_group']=='doi:'+r['doi'] for r in ledger))
 check('one_areal_current_not_converted',sum(r['reported_current_other'] is not None for r in ledger)==1 and next(r for r in ledger if r['reported_current_other'])['reported_current_A_g'] is None)
 check('four_unlocated_currents_preserved_null',sum(r['reported_current_A_g'] is None and r['reported_current_other'] is None for r in ledger)==4)
 check('all_training_admissions_false',all(not r['training_admitted'] and not r['material_identity_finalized'] and not r['current_mass_denominator_finalized'] for r in ledger))
 check('mixed_feedstocks_flagged',sum(bool(r['scope_flags']) for r in ledger)==2)
 check('ambiguous_or_2E_purple_KHC_not_counted',not {'PMC10958655','PMC6841744','PMC11357087','PMC7564396','PMC9655081'}&{r['source_tag'] for r in ledger})
 check('B_R042_electrolyte_1M_not_legacy_6M',next(r for r in ledger if r['source_tag']=='B_R042')['concentration_mol_L']==1)
 check('source_hashes_all_match',all(local(r['source_file']).exists() and sha(local(r['source_file']))==r['source_sha256'] for r in ledger))
 check('evidence_text_locators_and_reading_exist',all(r['locator'] and local(r['text_file']).exists() and local(r['reading_file']).exists() for r in ledger))
 new=read(OUT/'公开正文130篇_筛选状态.json');check('130_unique_downloaded_DOIs',len(new)==len({r['doi'] for r in new})==130)
 xmlerrors=[]
 for r in new:
  p=local(r['source_path']);root=ET.parse(p).getroot();dois={''.join(x.itertext()).strip().lower() for x in root.findall('.//article-id[@pub-id-type="doi"]')}
  if r['doi'].lower() not in dois or root.find('.//body') is None or sha(p)!=r['sha256']:xmlerrors.append(r['pmcid'])
 check('130_primary_XML_identity_body_SHA',not xmlerrors,xmlerrors)
 selected={r['source_tag'] for r in ledger if r['source_tag'].startswith('PMC')};check('19_new_selected_sources_22_endpoints',len(selected)==19 and sum(r['source_tag'] in selected for r in ledger)==22)
 figure_errors=[]
 for tag in selected:
  d=OUT/'new_sources'/tag;root=ET.parse(d/'main.xml').getroot();parser=Links();parser.feed((d/'正文阅读版.html').read_text('utf-8'))
  nf=len(root.findall('.//fig'))
  if nf<1 or parser.images<nf:figure_errors.append({'tag':tag,'XML_figures':nf,'rendered_images':parser.images})
  pack=read(d/'figure_package_acquisition.json')
  if sha(d/'figures_and_supplements.zip')!=pack['zip_sha256']:figure_errors.append({'tag':tag,'package':'hash mismatch'})
  for a in pack['files']:
   if sha(d/a['file'])!=a['sha256']:figure_errors.append({'tag':tag,'asset':a['file']})
 check('original_figures_and_SI_packages_present_including_floats_group',not figure_errors,figure_errors)
 check('8_new_SI_documents',len(read(OUT/'新增已取得补充文档.json'))==8)
 check('217_unique_classified_identities',len(lib['records'])==217 and len({r['doi'] if r['doi'] else r['source_sha256'] for r in lib['records']})==217)
 check('type_counts_4_ML_reviews_17_modeling_179_experiments',lib['counts']['01_机器学习综述']==4 and lib['counts']['02_机器学习与统计建模原始研究']==17 and lib['counts']['03_原始实验研究']==179)
 check('all_53_endpoints_mapped_once_in_classification',sorted(e for r in lib['records'] for e in r['endpoint_ids'])==sorted(r['endpoint_id'] for r in ledger))
 check('217_external_reading_files_exist',all(Path(r['classified_main']).exists() for r in lib['records']))
 check('217_portable_locations_available',all((r['repository_source'] and local(r['repository_source']).exists()) or r['portable_source_locations'] for r in lib['records']))
 originals=[]
 for r in lib['records']:
  for v in r['source_versions']:
   if not Path(v['path']).exists() or sha(v['path'])!=v['sha256']:originals.append(v['path'])
 check('original_paths_and_bytes_preserved',not originals,originals)
 copies=read(OUT/'分类复制与原件哈希.json');bad=[]
 for r in copies:
  if sha(r['source'])!=r['sha256'] or sha(r['destination'])!=r['sha256']:bad.append(r['destination'])
 check('1080_classified_copies_match_source_SHA',len(copies)==1080 and not bad,{'files':len(copies),'bad':bad})
 old=read(OUT/'protected_fingerprints.json');check('six_legacy_SQLite_and_contract_unchanged',all(sha(ROOT/r['path'])==r['sha256'] for r in old))
 missing=read(OUT/'仍需下载资料_逐项DOI.json');check('remaining_13_main_9_SI',len(missing['missing_main'])==13 and len(missing['missing_SI'])==9)
 check('pending_main_disjoint_from_obtained',not {r['doi'] for r in missing['missing_main']}&{r['doi'] for r in new})
 check('DOI_list_complete_22_and_not_truncated',set((OUT/'仍需下载_全部DOI.txt').read_text('utf-8').split())=={r['doi'] for r in missing['missing_main']+missing['missing_SI']})
 check('19_PDF_only_pending_distinguished_from_missing_fulltext',len((OUT/'已获XML原图但未获出版社PDF_完整DOI.txt').read_text('utf-8').split())==19)
 broken=[];nlinks=0
 paths=list((OUT/'new_sources').glob('*/正文阅读版.html'))+[OUT/'三电极端点清单.html',OUT/'文献类型目录.html']+list(Path(lib['external_root']).rglob('*.html'))
 for p in paths:
  parser=Links();parser.feed(p.read_text('utf-8'))
  for value in parser.links:
   if value.startswith(('#','https:','http:','mailto:','data:','javascript:')):continue
   value=urllib.parse.unquote(value.split('#')[0].split('?')[0])
   if not value:continue
   if value.startswith('file:///'):dest=Path(value[8:])
   else:dest=(p.parent/value).resolve()
   nlinks+=1
   if not dest.exists():broken.append({'file':str(p),'link':value})
 check('local_HTML_links_and_figures_resolve',not broken,{'links':nlinks,'broken':broken[:100]})
 result={'checks':checks,'passed':sum(x['pass'] for x in checks),'failed':sum(not x['pass'] for x in checks),'scope':'Counts and integrity checks supplement explicit primary-source reading; they are not scientific training admission.'}
 (OUT/'核验结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(bool(result['failed']))

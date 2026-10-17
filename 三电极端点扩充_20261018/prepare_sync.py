"""Freeze this task's outputs, preserve original doc line endings, and preview scoped sync."""
from pathlib import Path
import subprocess,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
PATHS=['三电极端点扩充_20261018','README.md','docs/CURRENT_STATE.md','docs/DATA_AND_PATHS.md','docs/LITERATURE_INDEX.md']
SYNC_ARGS=['--message','Collect 53 traceable three-electrode endpoints and classify literature by type','--summary','核定53个三电极GCD端点（41篇，43点值/6近似/4损失率换算），取得130份公开XML、21份原图SI包及8份独立SI文档，建立217身份的按类型分类副本和缺件DOI清单','--checks','36项核验通过；130原文DOI/正文/SHA一致；1080副本及原件一致，1234本地链接有效；6旧SQLite和契约未变；13正文/9SI仍缺。未合并未训练','--next','按manifest审窗口、质量分母、基线、材料/前作关系和7输入；4条循环电流仍缺；近似、换算及混合前驱体单独处理；保持每任务Git同步','--paths',*PATHS]
if __name__=='__main__':
 for f in PATHS[1:]:
  old=subprocess.run(['git','show','HEAD:'+f],cwd=ROOT,check=True,capture_output=True).stdout;p=ROOT/f;s=p.read_text('utf-8')
  p.write_bytes(s.replace('\r\n','\n').replace('\n','\r\n' if old.count(b'\r\n')>old.count(b'\n')/2 else '\n').encode('utf-8'))
 manifest={'schema':'literature-evidence-task-v1','date':'2026-10-18','ready_for_review':True,'collection_goal_achieved_under_stated_count_profile':True,'scientific_training_admission':False,'database_merged':False,'research_fits':0,'endpoint_counts':json.loads((OUT/'endpoint_counts.json').read_text('utf-8')),'ownership':PATHS,'original_literature_preserved':True,'external_classification_is_copy_view':True,'original_contract_preserved':True,'outputs':[]}
 for f in sorted(OUT.rglob('*')):
  if f.is_file() and f.name!='merge_manifest.json':manifest['outputs'].append({'path':f.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size})
 (OUT/'merge_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('MANIFEST',len(manifest['outputs']),'FILES',sum(r['bytes'] for r in manifest['outputs']),flush=True)
 subprocess.run(['git','diff','--stat'],cwd=ROOT,check=True)
 subprocess.run([sys.executable,'-B',str(ROOT/'tools/sync_task.py'),'--dry-run',*SYNC_ARGS],cwd=ROOT,check=True)

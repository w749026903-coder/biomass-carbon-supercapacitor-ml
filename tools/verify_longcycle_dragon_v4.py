"""Re-read actual deposited pixels; preserve the graph/prose discrepancy."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第五轮_长周期来源补证'
def main():
 q=json.loads((P/'dragon_curve_candidate.json').read_text('utf8'));p=ROOT/q['figure_path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==q['figure_sha256'];a=np.array(Image.open(p).convert('RGB'));r,g,b=(a[:,:,i].astype(float)for i in range(3));mask=(r>140)&(b>100)&(r>1.35*g)&(b>1.25*g);c=q['calibration'];points=[]
 for x in range(382,600,4):
  yy,xx=np.where(mask[16:68,x-1:x+2])
  if len(xx)<2:continue
  px=float(np.median(xx+x-1));py=float(np.median(yy+16));n=(px-c['x0'])/(c['x50000']-c['x0'])*50000;v=(c['y0']-py)/(c['y0']-c['y100'])*100;bound=3/(c['y0']-c['y100'])*100;dx=3/(c['x50000']-c['x0'])*50000
  points.append(dict(index=len(points),x_px=px,y_px=py,cycle_coordinate=n,cycle_upper=n+dx,retention_pct=v,reading_interval_pp=[v-bound,v+bound],reading_bound_pp=bound,pixel_count=len(xx),sampling_mode='visible_dense_trace_columns_not_raw_measurement_count'))
 assert points==q['points'];last=points[-1];assert last['reading_interval_pp'][0]>q['author_retention_pct'];assert not q['research_training_approved'];assert not q['new_formal_admission'];assert q['conditions']['reported_current_A_g']is None and q['conditions']['reported_current_mA_cm2']==500 and not q['conditions']['current_conversion_used']
 result=dict(status='verified_candidate_hold',actual_published_trace_points=len(points),author_endpoint_pct=q['author_retention_pct'],graph_endpoint_pct=q['graph_last_retention_pct'],no_endpoint_rescaling=True,area_current_not_mislabelled=True,model_admissions=0,doi='10.1021/acsomega.0c06171')
 (P/'dragon_candidate_verification.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

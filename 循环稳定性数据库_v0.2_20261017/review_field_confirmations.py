"""Append selected characterization confirmations without rewriting values."""
import hashlib
import json
import sqlite3
from review_batch1 import ROOT,DATE,js

def main():
    c=sqlite3.connect(ROOT/'cycling_v0_2.sqlite');c.row_factory=sqlite3.Row
    if c.execute("SELECT count(*) FROM review_events WHERE decision='verified_precycling_BET'").fetchone()[0]:
        raise RuntimeError('Field confirmations already recorded')
    items=[
      ('R103_CY01','BET_m2_g',2285.,'main',9,'2285','verified_precycling_BET','正文结论明确LAC800-4的2285 m²/g，成品而非木质素原料。'),
      ('SRC124_CY01','BET_m2_g',501.,'main',None,'MHDHPC-600 501','verified_precycling_BET','XML Table1与SI TableS2一致；标准批MHDHPC-600。'),
      ('SRC124_CY01','total_pore_volume_cm3_g',0.25,'supplement',8,'MHDHPC-600 501','verified_precycling_pore_volume','SI TableS2明列Vtotal cm³/g=0.25；不是Vmicro=0.24。'),
      ('SRC124_CY01','N_at_pct',2.1,'supplement',7,'MHDHPC-600 87.8','verified_precycling_XPS','SI TableS1明示at.%；成品N2.1，不是棉浆原料N8.8。'),
      ('SRC124_CY01','O_at_pct',8.8,'supplement',7,'MHDHPC-600 87.8','verified_precycling_XPS','SI TableS1明示at.%；标准批次成品氧。'),
    ]
    for rid in ['R107_CY01','R107_CY02']:
        items += [(rid,'BET_m2_g',3006.,'supplement',None,'Table S3.','verified_precycling_BET','SI TableS3成品DUGPC BET，不是原料或循环后表征。'),
                  (rid,'total_pore_volume_cm3_g',1.779,'supplement',None,'Table S3.','verified_precycling_pore_volume','SI TableS3 Vt cm³/g=1.779；两终点共享一个材料，不增加材料数。')]
    with c:
        for rid,field,value,role,page,anchor,decision,reason in items:
            paper=rid.split('_CY')[0]
            source=dict(c.execute('SELECT * FROM source_files WHERE paper_id=? AND role=?',(paper,role)).fetchone())
            assert hashlib.sha256(__import__('pathlib').Path(source['path']).read_bytes()).hexdigest()==source['sha256']
            pages=json.loads((ROOT/'evidence_text'/f'{paper}_{role}.json').read_text(encoding='utf-8'))
            text=' '.join(next(p for p in pages if page is None or p.get('page')==page)['text'].split())
            pos=text.find(anchor);assert pos>=0,(rid,anchor)
            assert c.execute(f'SELECT {field} FROM endpoint_features WHERE record_id=?',(rid,)).fetchone()[0]==value
            c.execute('INSERT INTO review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (rid,field,decision,js(value),source['path'],source['sha256'],f'{role} '+(f'PDF p{page}' if page else 'XML Table1 / SI TableS3'),text[max(0,pos-30):pos+len(anchor)+280],reason,DATE))
    c.close()
    print(f'Appended {len(items)} field confirmations; existing values unchanged.')

if __name__=='__main__':main()

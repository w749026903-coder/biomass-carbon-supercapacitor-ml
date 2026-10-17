"""Apply explicit, evidence-bounded first review; no admission or raw overwrite."""
import hashlib
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent
DB = ROOT/'cycling_v0_2.sqlite'
DATE = '2026-10-17'
def js(x):return json.dumps(x,ensure_ascii=False)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

# Each source has a separately reviewed locator, label, decision, and remaining gap.
REVIEWS = {
 'R093':dict(role='main',page=10,anchor='108.8%',label=108.8,material=True,protocol=True,baseline=False,
  outcome='conditional_hold',reason='108.8%与10000次/5 A/g及6 M KOH、0–1.2 V已核；图8e支持起始归一化但未明确基线圈号；电容公式单电极质量不等于循环电流分母；跨来源独立性待终审。'),
 'R103':dict(role='main',page=1,anchor='96.1%',label=96.1,material=True,protocol=True,baseline=False,
  outcome='conditional_hold',reason='摘要直接报告96.1%，正文为损失3.9%，不是仅靠推算生成标签；SI公式质量为单电极LAC负载，循环电流归一化仍未单独定义；基线圈号、独立性待核；孔体积数值未定位。'),
 'R104':dict(role='main',page=11,anchor='98.4',label=98.4,material=True,protocol=True,baseline=False,
  outcome='conditional_hold',reason='20000次/10 A/g、1 M乙酸钠及98.4±0.3%已核；成对器件/标准差不是独立材料。图10a从100%起始但未明确基线圈号；电流质量分母仍待澄清。'),
 'R106':dict(role='main',page=15,anchor='86.82%',label=86.82,material=False,protocol=False,baseline=False,
  outcome='frozen_pending_clarification',reason='FMC的5000次/86.82%已核，循环电流未定位。SI硅11.68 at%/22.20 wt%属于FMCA，不能移给FMC；正文提及SiO2，FMC自身成品范围仍待核。'),
 'R107':dict(role='main',page=8,anchor='95.5',label=None,material=True,protocol=None,baseline=True,
  outcome='conditional_hold',reason='明确相对initial capacitance；一万/两万次分别95.5%/94.9%，在v0.1共用同一暂定测试编号。SI Fig.S11直接确认两万次5 A/g、6 M KOH；图6支持一万次0–1 V，测试级补值也会显示于两万次节点，后者须标继承协议而非独立核实；电流分母、精确基线圈号、测试归并与独立性待终审。'),
 'R111':dict(role='main',page=8,anchor='89.44',label=89.44,material=True,protocol=False,baseline=False,
  outcome='conditional_hold',reason='2000次/1 A/g/89.44%已核；两电极段明确6 M KOH，补浓度和种类。循环电压仍未定位，不能借用三电极−1–0 V或从能量反算；SI未在库。'),
 'R112':dict(role='main',page=10,anchor='90.77',label=None,material=False,protocol=False,baseline=False,
  outcome='frozen_pending_clarification',reason='5000次90.77%及10000次74.40%是同一曲线节点。正文p10写0–1 V，p13 Fig11c内嵌循环曲线至约1.2 V，登记电压一致性疑点，不自行选择。p6还报告XPS Si2p 1.7%，需核材料范围与百分比口径。'),
 'SRC035':dict(role='main',page=8,anchor='100 %',label=100.,material=True,protocol=True,baseline=False,
  outcome='conditional_hold',reason='正文/图8g报告100%/10000次/5 A/g；图8c–h对应1 M Na2SO4，避免混入同页6 M KOH器件。摘要nearly/almost措辞另记，点值保持原摘录；基线、电流分母、独立性待核；孔体积指向未在库Table S1。'),
 'SRC123':dict(role='main',page=4,anchor='27.9%',label=27.9,material=True,protocol=True,baseline=True,
  outcome='frozen_pending_clarification',reason='等质量RHC器件10000次27.9%，相对作者initial capacitance。前作已定位2016 DOI 10.1016/j.colsurfa.2016.10.009：制备路线与本篇接近，但BET3263与3185不同，公开摘要不能确认同批材料/曲线复用；不判定独立也不判定复用。'),
 'SRC124':dict(role='main',page=None,anchor='initial',label=92.,material=True,protocol=True,baseline=True,
  outcome='conditional_hold',reason='XML Fig5h段落明确50000次10 A/g保持92%，并给初始216与末值200 F/g；保留作者92%，不改成200/216。SI验证标准MHDHPC-600的501 m²/g、0.25 cm³/g和XPS，不借给放大批次。循环电流分母未单独定义，独立性待核。')
}

def main():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
    if c.execute('SELECT count(*) FROM review_events').fetchone()[0]:
        raise RuntimeError('Review already applied; create a new incremental batch.')
    sources={(r['paper_id'],r['role']):dict(r) for r in c.execute('SELECT * FROM source_files')}
    rows=[dict(r) for r in c.execute('SELECT * FROM primary_screening_candidates ORDER BY record_id')]
    assert len(rows)==12
    def evidence(paper,role,page,anchor):
        source=sources[(paper,role)]
        pages=json.loads((ROOT/'evidence_text'/f'{paper}_{role}.json').read_text(encoding='utf-8'))
        selected=next(p for p in pages if page is None or p.get('page')==page)
        text=' '.join(selected['text'].split());pos=text.find(anchor)
        if pos<0:raise ValueError((paper,role,page,anchor))
        return source,text[max(0,pos-90):pos+len(anchor)+180]
    def event(r,field,decision,value,role,page,anchor,rationale,locator=None):
        s,excerpt=evidence(r['paper_id'],role,page,anchor)
        c.execute('INSERT INTO review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) VALUES (?,?,?,?,?,?,?,?,?,?)',
                  (r['record_id'],field,decision,js(value),s['path'],s['sha256'],locator or (f'{role} PDF p{page}' if page else f'{role} XML / document locator'),excerpt,rationale,DATE))
    def change(table,keyfield,key,field,value,reason):
        old=c.execute(f'SELECT {field} FROM {table} WHERE {keyfield}=?',(key,)).fetchone()[0]
        if old!=value:
            c.execute('INSERT INTO revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) VALUES (?,?,?,?,?,?)',(table,key,field,js(old),js(value),reason))
            c.execute(f'UPDATE {table} SET {field}=? WHERE {keyfield}=?',(value,key))
    with c:
        for r in rows:
            spec=REVIEWS[r['paper_id']]
            s=sources[(r['paper_id'],spec['role'])];assert sha(s['path'])==s['sha256']
            event(r,'source_and_label','verified_reported',r['retention_pct'],spec['role'],spec['page'],spec['anchor'],spec['reason'])
            for field,decision in [('cycle_current_mass_basis','needs_author_clarification'),('source_independence','pending_cross_source_audit')]:
                event(r,field,decision,None,spec['role'],spec['page'],spec['anchor'],spec['reason'])
            event(r,'normalization_reference','verified_author_initial_unspecified_cycle' if spec['baseline'] else 'not_explicitly_located',
                  'author_initial_capacitance' if spec['baseline'] else None,spec['role'],spec['page'],spec['anchor'],spec['reason'])
            checks={'source_checked':1,'material_checked':int(spec['material']),
                    'protocol_checked':int(spec['protocol'] if spec['protocol'] is not None else r['record_id']=='R107_CY01'),
                    'baseline_checked':int(spec['baseline'])}
            # baseline_checked records the author's reference definition, not a guessed first-cycle index.
            for field,value in {**checks,'status':spec['outcome'],'rationale':spec['reason']}.items():
                change('admissions','record_id',r['record_id'],field,value,spec['reason'])
        r=next(r for r in rows if r['record_id']=='R107_CY01')
        for field,value in [('voltage_lower_V',0.),('voltage_upper_V',1.)]:
            event(r,field,'verified_graph_axis',value,'main',7,'Fig. 6.',
                  '已目视核main p7 Fig6b与Fig6d inset为0–1 V。数据库共享测试编号导致两万次节点继承显示，后者非独立核实。','main PDF p7 Fig6b and Fig6d inset; rendered visual inspection')
            change('cycling_tests','cycle_test_id',r['cycle_test_id'],field,value,'Main p7 Fig6; shared provisional test propagates to both nodes; 20000-cycle protocol requires final audit')
            other=next(x for x in rows if x['record_id']=='R107_CY02')
            event(other,field,'inherited_shared_test_pending_final_audit',value,'main',7,'Fig. 6.',
                  '两个节点共用v0.1暂定cycle_test_id；由测试级字段继承，不是两万次窗口直接证据，不解除冻结。')
        for r in [r for r in rows if r['paper_id']=='R107']:
            event(r,'current_density_A_g','verified_reported',5.,'supplement',None,'Fig.S11.',
                  'SI Fig.S11直接写5 A/g与6 M KOH；一万次另有main Fig6d直接证据。','SI word/document.xml Fig.S11 caption')
            for field,value in [('N_at_pct',1.26),('O_at_pct',9.13)]:
                event(r,field,'verified_XPS_precycling',value,'supplement',None,'Table S5.',
                      'SI Table S5明示Atom (%)，成品DUGPC，非EDS、非循环后表征。','SI word/document.xml Table S5')
                change('endpoint_features','record_id',r['record_id'],field,value,'SI Table S5 XPS atom percent')
                if r['record_id']=='R107_CY01':
                    s,excerpt=evidence('R107','supplement',None,'Table S5.')
                    c.execute('INSERT INTO material_observations(material_id,record_id,property_name,value_json,unit,method,stage,source_path,locator,provenance_status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                              (r['material_id'],r['record_id'],field,js(value),'at%','XPS','precycling_as_prepared',s['path'],'Table S5','verified_batch1'))
        r=next(r for r in rows if r['paper_id']=='R111')
        for field,value in [('electrolyte','KOH'),('concentration_value',6.),('concentration_unit','M')]:
            event(r,field,'verified_device_section',value,'main',8,'6 M KOH','明确位于ACK-700两电极器件分析段，不借用引言/比较表。')
            change('cycling_tests','cycle_test_id',r['cycle_test_id'],field,value,'Main p8 device section explicitly 6 M KOH')
        for r in [r for r in rows if r['paper_id']=='R112']:
            event(r,'voltage_window_consistency','conflict_text_vs_cycle_inset',{'text':[0.,1.],'cycle_inset_upper_approximately':1.2},'main',10,'voltage range',
                  'Main p10明确0–1 V；已目视p13 Fig11c first/last20cycles内嵌图至1.2 V。不能认定正文或图必然正确。','main PDF p10 vs p13 Fig11c inset; rendered visual inspection')
            event(r,'Si_XPS_reported_percent','material_scope_review',1.7,'main',6,'Si 2p',
                  '原文XPS百分比，at/wt口径未在本处明确；不转换、不等同FMCA的EDS硅。')
            for code,reason in [('batch1_voltage_window_consistency','正文0–1 V与循环图内嵌曲线约1.2 V不一致，保留原候选窗口，继续冻结。'),
                                ('batch1_silicon_scope_review','XPS报告Si2p 1.7%；材料范围与百分比口径待审，没有设置通用硅含量剔除阈值。')]:
                c.execute('INSERT INTO issues(paper_id,record_id,severity,code,description,status,source_path,scope) VALUES (?,?,?,?,?,?,?,?)',
                          ('R112',r['record_id'],'high',code,reason,'open',sources[('R112','main')]['path'],'field_and_material'))
        for paper,field,decision,reason in [
            ('R103','total_pore_volume_cm3_g','not_located_in_available_evidence','正文N2等温线/孔径图与两页SI未定位可直接录入的总孔体积数值，不从等温线近似生成点值。'),
            ('SRC035','total_pore_volume_cm3_g','requires_missing_SI','正文p4指向Table S1，当前文献目录无本篇SI；不把未找到称为未报告。'),
            ('R106','current_density_A_g','not_located_in_available_evidence','正文p15及SI循环段未定位FMC循环电流；不借用倍率曲线的0.5 A/g。'),
            ('R111','voltage_window','requires_missing_SI','正文指向SI Fig S3器件GCD，当前SI未在库，三电极电压不能借用。')]:
            for r in [r for r in rows if r['paper_id']==paper]:
                spec=REVIEWS[paper];event(r,field,decision,None,spec['role'],spec['page'],spec['anchor'],reason)
        change('source_relationships','relationship_id',2,'related_doi','10.1016/j.colsurfa.2016.10.009','Matched local reference 15 to official publisher metadata; overlap still pending')
        change('source_relationships','relationship_id',2,'note',
               'Reference15 matched to official ScienceDirect 2016 volume511 pp294-302, DOI10.1016/j.colsurfa.2016.10.009. Similar carbonization500C/1h, activation700C/1h, KOH ratio4:1; BET3263 (2016) vs3185 (2025). These facts neither establish nor rule out batch/curve reuse. Public preview only; independence not cleared.',
               'Scope-bounded primary metadata and accessible methods comparison')
        c.executescript('''CREATE VIEW field_review_latest AS SELECT r.* FROM review_events r WHERE review_id=(SELECT max(x.review_id) FROM review_events x WHERE x.record_id=r.record_id AND x.field_name=r.field_name);''')
        assert c.execute('SELECT count(*) FROM training_ready').fetchone()[0]==0
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
    outcomes=[dict(r) for r in c.execute('SELECT record_id,status,source_checked,material_checked,protocol_checked,baseline_checked,mass_basis_checked,independence_checked,freeze_cleared,eligible,rationale FROM admissions WHERE source_checked=1 ORDER BY record_id')]
    (ROOT/'首批逐记录审查.json').write_text(js(outcomes),encoding='utf-8')
    c.close()
    print(f'Applied {len(outcomes)} explicit reviews; no records admitted.')

if __name__=='__main__':main()

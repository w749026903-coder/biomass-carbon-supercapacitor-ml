"""Forward-only research curation of the remaining fixed two-electrode queue."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030'
P11=BASE/'第十一轮_双电极原文曲线补充';OUT=P11/'batch3_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')

def main():
    assert not(OUT/'curve_dataset_v3f.json').exists(),'Never overwrite a curated increment'
    ptr=read(ROOT/'data/current_retention_research.json')
    assert ptr['sha256']=='969a97610edef592ffd09d8fb8668847d238c3f85973f2242eb999f527397a7f'
    protected=[ROOT/ptr['database'],ROOT/'data/current_training_latest.json',ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json',P11/'queue_plan.json',BASE/'research_goal.json']
    canonical=read(ROOT/'data/current_training_latest.json')
    protected.append(ROOT/canonical['directory']/canonical['database_file'])
    protected += [BASE/p for p in ['第二轮_证据与曲线扩充/cycling_research_v3b.sqlite','第八轮_原文补证与双电极曲线/cycling_research_v3c.sqlite','第十一轮_双电极原文曲线补充/cycling_research_v3d.sqlite']]
    # The canonical file is protected through its actual pointer field.
    for value in canonical.values():
        if isinstance(value,str) and value.endswith('.sqlite') and (ROOT/value).exists():protected.append(ROOT/value)
    rec=read(OUT/'figure_receipts.json')
    protected += [ROOT/x['source_path'] for x in rec]
    for folder in ['第十轮_稳健表达与来源权重','第九轮_同窗口形状对照','第四轮_选模稳定性复核']:
        protected += [BASE/folder/name for name in ['training_plan.json','results.json'] if (BASE/folder/name).exists()]
    protection={p.resolve().as_posix():sha(p) for p in protected}
    write(OUT/'source_protection.json',dict(files=protection,prior_pointer=ptr,prior_pointer_sha256=sha(ROOT/'data/current_retention_research.json'),prior_commit='37b1c8880d0a2bd29452d4c103ea7ba22c974ef3'))
    candidates=read(OUT/'extracted_curve_candidates_v3.json');qc=read(OUT/'extraction_qc_v3.json')
    reasons={
      'OPC':'hold_graph_text_disagreement: Fig8g last near99.1469%, fixed3px interval excludes author100%. Both values retained; no endpoint calibration or author label change.',
      'OPBNP':'hold_unresolved_occluded_glyph_geometry: Red CE glyphs occlude blue retention glyphs, blue annotation pixels also interfere. Both coordinate attempts are provisional, not reliable retention observations. Do not reinterpret failed92.84% read as an author contradiction.',
    }
    reviews=[]
    for q,r in zip(candidates,qc):
        label=r['label'];approved=label not in reasons
        if approved:
            assert q['endpoint_consistent_with_graph_bound'] and r['last_visible_cycle']>=.97*q['target_cycle_count']
            assert r['windows'][1]['point_count']>=3
        q['training_eligible_pending_visual_review']=approved
        q['visual_review']=dict(status='approved_exploratory_early_window'if approved else'held_not_training',reason=reasons.get(label,'Original pixels, named sample/condition, axis ticks and early positions reviewed; own author endpoint retained. Last visible glyph/trace position is a near-endpoint consistency check, not an invented exact-N measurement.'),digitization_attempts_not_independent_measurements=True,author_endpoint_changes=0,formal_new_endpoint_admissions=0)
        if label=='OPBNP':q['coordinate_quality']='unvalidated_attempts_not_scientific_observations'
        reviews.append(dict(label=label,endpoint_id=q['endpoint_id'],source_family=q['source_family'],approved=approved,reason=q['visual_review']['reason'],author_retention=q['author_retention_pct'],near_end_reading=r['last_retention'],near_end_interval=r['last_interval'],last_visible_cycle=r['last_visible_cycle'],windows=r['windows']))
    assert sum(r['approved']for r in reviews)==12
    parent=read(P11/'batch2_20261031/curve_dataset_v3e.json')
    assert not({q['endpoint_id']for q in parent}&{q['endpoint_id']for q in candidates})
    write(OUT/'curve_dataset_v3f.json',parent+candidates)
    write(OUT/'visual_review.json',dict(reviewed_curve_candidates=14,approved_early_curves=12,held_candidate_curves=2,source_without_resolved_early_curve=dict(index=6,endpoint_id='incoming:ADD_064_T01',reason='CLK main Fig6j original JPEG553x470 contains a panel only about130x100pixels. Early individual glyph centres unresolved. Upsampling does not create evidence. Author93.3% and existing A record remain unchanged.'),curves=reviews))
    protocol={
      6:('CLK100C10, mainp22/23 Fig6j', 'Symmetric2E,10000cycles at10A/g,93.3%. Low-resolution early curve held; main/SI original protection retained.'),
      7:('MF/LYS mainp3/p7 Fig7d and publisher SI FigS7d', 'Main methods2E,6MKOH; Fig7/S7 show0..1V;5A/g5000cycles. MF abstract95.89 competes with body/Fig7d95.59; retain both, select direct named body+ownfigure95.59 already used, no label change. LYS94.42 tied to its own SI curve, not MF.'),
      8:('LocalJATS p51/Fig7G; existing publisher SI p3', 'NWJPC-2 symmetric carbon SC5A/g10000/99.8%,6MKOH,ownfirst/lastcyclinginsets0..1V. Earlier SI signed-1..0V conflict remains in v5 decision; owncyclinginsets were selected. Not zinc-ion-hybrid specific-capacity Fig9.'),
      9:('Mainp8 Fig8g', 'Symmetricdevice5A/g10000cycles; body100 versus graphnear99.15 conflict held, author original remains. Abstract nearly100 qualifier also retained.'),
      10:('Mainp2 methods andp7 Fig7f/caption', 'Two equal-mass electrodes,1mol/LKOH,0..1V. Methods mention1A/g only; figure/caption and result give1and3A/g. Both author growth targets142.22/116.33 retained and associated with separate actual coloured curves. This is cyclic activation, not probability above1.'),
      11:('Mainp4 methods,p10 Fig5d,p12 conclusion', 'Two-electrode symmetric coin cell,1mol/LH2SO4,10A/g10000cycles95.5%; green leftaxisretention, orange rightaxis99.6%CE not target. Copied vsSCE plotting text does not turn a full cell into3E.'),
      12:('Mainp3 coin-cell methods,p7 Fig6d,p8', '6MKOH symmetric aqueous cell,5A/g10000cycles95.5%. Samepaper organic2.8V cell is separate. Read left retention axis, not right F/g. Early activation hump and20kSI94.9 report not deleted or merged into the10k endpoint.'),
      13:('Mainp11 Fig10a and cycling paragraph', '1Msodiumacetate symmetric carbon cell,10A/g20000cycles98.4+-0.3%. Axis85..105%, twelve actual solid disk centres, error-bar caps and joining line not counted. 10% has2points,20%3; retain10%raw but do not admit.'),
      14:('Mainp7 device section,p8 Fig6h', 'AUACW//AUACW SSC in1MKOH,30A/g10000cycles80.9%,0..1.6V existing A protocol retained. Green geometric sphere centres used; orange98.6%CE distinct. Samepaper3E93.6% distinct.'),
      15:('Mainp7 methods,p18 Fig4e,p19', 'OPBNP//OPBNP symmetric SC,5A/g10000cycles97.61 andCE98.24%. Separate from3E93.6% Fig3f and sodium-ion-battery88.8% Fig5c. Occluded blue glyph centres unresolved, no B admission.'),
      16:('Mainp5 cell assembly,p12 Fig7f,p13', 'PPC-500-1-1h symmetriccell6MKOH,10A/g20000cycles99.3%; actual magenta circles. 70.5% rate retention and221.9F/g are different measurements.'),
      17:('Mainp2/3 methods,p10/11 Fig8e', 'PR-2-based symmetricdevice6MKOH,0..1.2V,5A/g10000cycles108.8. Actualblack squares show activation; GCD inset is separate, real growth not clipped.'),
      18:('Mainp8 Fig7c/caption', 'LAC800-4 symmetric2E6MKOH,20A/g10000cycles96.1%. PDF figure is split into native image strips; page rendering preserves positions. Red star markers, inset rate bars not cyclingpoints. Previous retained BET2285 and0..1V inputs unchanged.'),
    }
    write(OUT/'protocol_review.json',dict(scope='Existing eligible A conditions retained; newly reviewed local original/SI identities, cycling curves and early-feature associations. Material/BET values inherit prior admitted evidence, not newly inferred from figures.',source_reviews=[dict(index=i,locator=v[0],decision=v[1])for i,v in protocol.items()],canonical_labels_changed=0,new_formal_admissions=0,new_untouched_external_sources=0,new_model_fits=0))
    print('Curated12 new B curves;2 held raw attempts;CLK unresolved;old55curves preserved.')
if __name__=='__main__':main()

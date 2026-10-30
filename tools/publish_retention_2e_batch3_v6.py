"""Publish audited local data increment and the compact continuation entries."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';P11=BASE/'第十一轮_双电极原文曲线补充';OUT=P11/'batch3_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')

CURRENT='当前目标继续active。第十一轮本地固定19来源/24端点已全部初审，累计19条早期曲线接入、5条仍待精读或补证。2026-10-31第3批审剩13来源/15端点：12条早期曲线、10来源组、864个相关读图位置接入新3f（非864实验），14条试读中OPC/OPBNP保留未准入，CLK低清图未造点。2E20%现26条/21来源、10%22/17；3E30/24和20/19不改。本批5682独立像素/坐标/原件/SQL/窗口核验、28保护文件；v7和旧3b/c/d/e原件、作者标签、原37、冻结保留，正式新增端点0/模型新拟合0/全新外部来源0。MF/LYS分正文与自身SI，NWJPC用本地JATS+已有Fig7G，20000圈SSC截断85%轴且10%仅2点不准入；PCNaCl142.22/116.33与PR-2108.8真实增长不裁剪。OPC图近末99.1469与正文100不相容；OPBNP蓝保持率被红CE遮挡，失败试读不是作者矛盾。另MMC/BLAC自身C(N)参考、CLK分辨率继续核实。P10旧冻结输入主R².655486/MAE3.040324/RMSE4.283168、原六项稳定.761403/2.534397/3.564467，0全面达标；3f新增尚未训练。API data.retention_research已前向3f，旧3e指针原字节归档。下一步处理5条精度/参考问题，并为扩充2E输入冻结下一次有限来源隔离验证；不重跑旧轮、不实施未批准2点提案，所有近优/A/2E/BP保留，输出始终指定圈数电容保持率。'

def main():
    audit=read(OUT/'independent_verification.json');assert audit['status']=='passed'and audit['checks']==5682
    ptrpath=ROOT/'data/current_retention_research.json';previous=ptrpath.read_bytes();prior=json.loads(previous);hist=ROOT/'data/pointer_history/current_retention_research_v3e_20261031.json'
    if hist.exists():
        # Resume this task's interrupted documentation step only after checking
        # the already-published forward pointer and exact original archive.
        receipt=read(OUT/'pointer_forward_receipt.json')
        assert sha(hist)==receipt['prior_pointer_sha256'] and sha(ptrpath)==receipt['new_pointer_sha256']
        assert prior['sha256']==audit['sqlite_sha256']
    else:
        assert prior['sha256']=='969a97610edef592ffd09d8fb8668847d238c3f85973f2242eb999f527397a7f'
        hist.write_bytes(previous);new=dict(prior);new.update(version='retention_research_v3f_20261031',database=(OUT/'cycling_research_v3f.sqlite').relative_to(ROOT).as_posix(),sha256=audit['sqlite_sha256'])
        write(ptrpath,new);write(OUT/'pointer_forward_receipt.json',dict(prior_pointer_sha256=hashlib.sha256(previous).hexdigest(),prior_pointer_archive=hist.relative_to(ROOT).as_posix(),new_pointer_sha256=sha(ptrpath),new_database_sha256=audit['sqlite_sha256'],old_database_and_canonical_store_preserved=True,new_fits=0))
    progress=read(P11/'progress.json');progress.update(status='all19_sources_initially_reviewed_19curves_connected_5held',source_reviews=19,reviewed_endpoint_rows=24,accepted_B20_curves=19,held_or_pending_reference_curves=5,unreviewed_sources=0,unreviewed_endpoint_rows=0,current_2E20_rows_sources=[26,21],current_2E10_rows_sources=[22,17],current_store='v3f',latest_batch_checks=5682,next='Resolve5held cases with original evidence or improved readout; frozen next finite2E source-isolated validation after this audited expansion. Do not rerun old3E rounds or apply pending2pointproposal; preserve all originals, authorlabels and difficultcases.')
    write(P11/'progress.json',progress)
    p=read(BASE/'research_progress.json');p.update(phase11='19of19_sources_initially_reviewed_19Bcurves_connected_5held',phase11_unreviewed_sources=0,phase11_current_2E20_rows_sources=[26,21],phase11_current_2E10_rows_sources=[22,17],phase11_reviewed_sources=19,phase11_reviewed_endpoint_rows=24,phase11_unreviewed_endpoint_rows=0,current_research_store='v3f',phase11_batch3_curves=12,phase11_batch3_new_source_groups=10,phase11_batch3_connected_positions=864,phase11_batch3_verification_checks=5682,phase11_held_curves=5,phase11_current_data_retrained=False,next=progress['next'],last_goal_turn_classification='progress',last_goal_turn_evidence=['Allremaining13local_sourceidentities/protocols reviewed;NWJPCandLYSSIsource pathsresolved','12earlycurves/10sourcegroups/864correlatedpositions connected','5682independentchecks/28protectedfiles','Fiveoriginalevidence/readoutissuesretained;nofalsefullacceptance'])
    write(BASE/'research_progress.json',p)
    source=read(OUT/'text_locator_review.json')[2]
    write(OUT/'source_resolution.json',dict(queue_index=8,identity=source['identity'],resolved_source='三电极端点扩充_20261018/new_sources/PMC13521071/main.xml',figure='文献全量利用复核_20261025/批次05_碳化系列与多电解液/evidence/Weigela_gr7.webp',existing_SI='文献全量利用复核_20261025/批次05_碳化系列与多电解液/evidence/Weigela_mmc1.pdf',reacquisition=False,new_external_source=False,main_caption='Figure7G symmetric supercapacitor cycling at5A/g; not the zinc hybrid'))
    for rel in ['docs/CURRENT_STATE.md','docs/WORKSPACE_MEMORY.md']:
        f=ROOT/rel;s=f.read_text('utf8');s,n=re.subn(r'^当前目标继续active。[^\r\n]*',CURRENT,s,count=1,flags=re.M);assert n==1;f.write_text(s,'utf8')
    f=ROOT/'AGENTS.md';s=f.read_text('utf-8-sig');s,n=re.subn(r'^- 2026-10-[0-9]+主线当前：[^\r\n]*','- 2026-10-31主线当前：第十一轮19来源/24端点初审完成，19条早期曲线累计接入、5条待精读；第3批12条/10来源组/864相关位置接入3f，5682核验/28保护文件。2E20%26/21、10%22/17，3E30/24与20/19不改。MMC/BLAC参照、CLK低清、OPC近末图文差异、OPBNP遮挡待解；OPBNP失败试读不是作者矛盾。SSC20000圈10%仅2点不准入，增长真实值保留。新增未训练，P10主.655486/3.040324/4.283168、原六项稳定.761403/2.534397/3.564467保持，0全面达标。旧库/标签/原37/v7保留、旧3e指针精确归档，所有近优/A/2E/BP与active目标保持。下一步核5条并冻结扩充2E有限验证，接续research_progress.json。',s,count=1,flags=re.M);assert n==1;f.write_text(s,'utf8')
    f=ROOT/'README.md';s=f.read_text('utf8');s,n=re.subn(r'^当前持续目标（2026-10-30）：[^\r\n]*','当前持续目标（2026-10-31）：输出仍为指定圈数电容保持率。第十一轮本地19来源/24端点均已初审，累计19条早期曲线接入、5条待精读。最新B双电极前20%为26条/21来源，前10%22条/17来源；三电极30/24与20/19保持。本批新增12条/10来源组，通过5682项核验，尚未重新训练。最近第十轮主方法R²0.655486、MAE3.040324pp，保留原六项稳定对照R²0.761403、MAE2.534397pp；目标继续进行中，尚无全面达标模型。详见[当前研究进度](保持率达标研究_v3_主线与近优组合_20261030/研究进度.html)及[最新数据依据](保持率达标研究_v3_主线与近优组合_20261030/第十一轮_双电极原文曲线补充/batch3_20261031/README.md)。',s,count=1,flags=re.M);assert n==1;f.write_text(s,'utf8')
    for rel in [BASE/'README.md']:
        text='最新更新（2026-10-31第3批）：'+CURRENT+'\n\n以下为各阶段原有记录，数据量与分数请按对应冻结输入解读。\n\n';rel.write_text(text+rel.read_text('utf8'),'utf8')
    section='\n\n## 2026-10-31 本地双电极第3批：固定队列初审完成，12条早期曲线接入3f\n\n'+CURRENT+'\n\n涉及：第十一轮/batch3_20261031的原图/SI指针、三次提取候选与核查记录、curve_dataset_v3f.json、cycling_research_v3f.sqlite及独立核验；data/current_retention_research.json及旧3e原字节指针历史；研究进度、入口README与知识库。5674项首次核验后追加4个旧库精确保护，共5682项通过。所有读图位置按相关曲线处理，来源组保持。旧PDF/唯一资料、本地仅保留的历史整理日志和未封版v8未纳入本任务提交。\n'
    f=ROOT/'docs/PROGRESS.md';f.write_text(f.read_text('utf8')+section,'utf8')
    knowledge='''# 本地证据替代、稀疏误差棒与遮挡循环图（2026-10-31）

网站无法访问时，先用已有正文PDF、JATS XML、SI原包及原始图像核对样品、体系、循环条件，再读图。本轮没有继续挑战验证页，也没有重新下载或改写原文。最新研究输入前向3f；主v7仍为原封版数据。

来源与处理：MF/LYS（10.1016/j.ijbiomac.2024.138815）分主文Fig7d及SI FigS7d；MF摘要95.89与正文及自身图95.59并存，采用后者并记录依据，旧标签保持。NWJPC-2（10.1016/j.isci.2026.117248）使用本地JATS与既有Fig7G，不混入锌离子混合器件的容量保持率。SSC（10.1021/acsomega.3c09438）Fig10a纵轴85%起，误差棒端帽与连接线不是循环观测；仅十二个可见圆心，10%窗口2点不准入。作者98.4±0.3%单列为作者报告，不把3px读图界限当实验统计误差。

PCNaCl（10.1016/j.jelechem.2026.120000）Fig7f蓝1A/g与红3A/g分别142.22/116.33%，PR-2（10.3390/coatings13071236）108.8%为真实活化增长，保持率不是概率。图中的箭头/注释与实际轨迹要分离；蓝色同色箭头曾污染试读，按原像素分带纠正，原尝试保留，没有调坐标去贴作者终值。

AUACW（10.1039/d4cp01914h）绿色球形点按实际下轮廓拟合圆心，高光只用于定位；橙色效率曲线不作保持率。DUGPC（10.1016/j.ultsonch.2024.107213）同页倍率Fig5与循环Fig6分开，左保持率与右绝对电容轴分开；有机器件不借水系条件。LAC（10.3390/molecules30010089）PDF图像被分条存储，整页渲染保留图像位置，不能把图条当作多图或丢掉循环图。

当前用途边界：12条早期曲线、10来源组、864相关读图位置接入，不是864个独立实验；相同论文多个样品/条件整来源隔离。末段检查使用原图最后可读位置且至少到97%目标圈数，是近末一致性检查，不虚构精确N点；固定3px界限不是置信区间。新增尚未训练、独立外部来源0，不能由覆盖提升推断R²提升。

五条仍待解决：MMC首个自身C(N)参考；BLAC自身参考与作者不相容；CLK低清图未辨早期点；OPC Fig8g近末99.1469与正文100不相容；OPBNP红CE遮住蓝保持率，当前几何提取不可靠。OPBNP失败试读92.84不是新科学事实或作者矛盾。对应A旧标签保持，B未准入；不能为凑齐而择值、补点或借倍率C0。

验证：本批5682项原图像素、几何、坐标、原件SHA、旧55曲线对象、SQL完整性/外键、严格窗口和来源计数检查；28个保护文件含v7与3b/c/d/e。完整依据见第十一轮/batch3_20261031/protocol_review.json、visual_review.json和independent_verification.json。历史模型审计必须用对应冻结提交/输入，滚动指针更新不代表可以改写旧冻结。
'''
    k=ROOT/'docs/knowledge/本地证据与误差棒遮挡循环图_20261031.md';assert not k.exists();k.write_text(knowledge,'utf8')
    f=ROOT/'docs/KNOWLEDGE_BASE.md';f.write_text(f.read_text('utf8')+'\n- 2026-10-31：[本地原文、稀疏误差棒与遮挡](knowledge/本地证据与误差棒遮挡循环图_20261031.md)：剩余13来源初审、12曲线/10来源组接入3f；SSC85%截断轴、MF/LYS原文与SI、真实增长、图像条带、注释污染与五条待解边界；5682核验。\n','utf8')
    print('Pointer3f and current entries published;goalactive,old data untouched.')
if __name__=='__main__':main()

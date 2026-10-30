"""Publish the audited MMC increment and frozen, not-started expanded2E plan."""
from pathlib import Path
import json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';P11=BASE/'第十一轮_双电极原文曲线补充';B=P11/'batch4_20261031';P12=BASE/'第十二轮_扩充双电极来源验证'
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
CURRENT='当前目标继续active。第十一轮固定19来源/24端点均初核，累计20条早期曲线接入、4条仍未准入；MMC另保留低精度参照限制。第4批自身首个实际C(N)红点作参照，138相关图读位置接入3g，781核验/37保护文件；近末93.332598%区间91.143649～95.572262，仅与作者95.6的一位小数舍入区间95.55～95.65相交，不能说95.6本身在区间内。原始C0误差共享到整曲线，不借倍率C0、不按终值缩放。2E20%现27/22、10%23/18，3E30/24和20/19保持，旧69曲线、v7、旧库/标签/原37/冻结不改。BLAC参照、CLK低清、OPC图文、OPBNP遮挡继续保留；OPBNP新21几何候选无早期窗口证据且图审未通过，未准入。第十二轮已冻结原16配置×六项/形状两对照、6400全新拟合，外层整来源LOSO/内层4折；预定主方案six_oneSE_family_mean，320项预检查通过，当前0拟合、未启动。下一步直接执行冻结计划，不重跑旧3E、不看外层追分、不放宽未批准2点提案；RF/GPR/XGB/静态、A、P6/BP/P10稳健/混合路线均保留。P10旧主R².655486/MAE3.040324/RMSE4.283168、六项稳定.761403/2.534397/3.564467保持，0全面达标/0全新外部来源。输出仍指定圈数电容保持率，源于既有来源的数值过线仍不能替代可靠泛化。'
def replace_line(path,pattern,value):
    raw=path.read_bytes();raw,n=re.subn(pattern,lambda _:value.encode('utf8'),raw,count=1,flags=re.M);assert n==1,path;path.write_bytes(raw)
def main():
    assert read(B/'independent_verification.json')['status']=='passed'and read(P12/'preflight_verification.json')['checks']==320
    assert read(P12/'progress.json')['status']=='frozen_not_started'and not(P12/'fit_events.jsonl').exists()
    p=read(P11/'progress.json');p.update(status='all19_reviewed_20connected_4held_MMCprecision_limit',accepted_B20_curves=20,held_or_pending_reference_curves=4,current_2E20_rows_sources=[27,22],current_2E10_rows_sources=[23,18],current_store='v3g',latest_batch_checks=781,low_precision_accepted_curves=['MMC own first C(N), author rounded-interval overlap only'],next='Run frozen P12 exactly6400 fits on expanded2E cohorts;continue4holds without altering current frozen training inputs. Preserve3E/A/BP/robust alternatives;0newexternal.')
    write(P11/'progress.json',p);p=read(BASE/'research_progress.json');p.update(current_research_store='v3g',phase11='19of19_reviewed_20Bcurves_connected_4held_MMCprecision_limit',phase11_current_2E20_rows_sources=[27,22],phase11_current_2E10_rows_sources=[23,18],phase11_held_curves=4,phase11_batch4_curves=1,phase11_batch4_positions=138,phase11_batch4_verification_checks=781,phase12='frozen_not_started',phase12_planned_fits=6400,phase12_actual_fits=0,phase12_preflight_checks=320,model_process_running=False,next=p['next'],last_goal_turn_classification='progress',last_goal_turn_evidence=['MMC own-reference138positions connected, rounding-only compatibility recorded','781data checks/37protection files','all5holds reviewed;4remainunadmitted','P12 finite6400-fit plan and independent verifier frozen with320preflightchecks;no model score seen'])
    write(BASE/'research_progress.json',p)
    for rel in ['docs/CURRENT_STATE.md','docs/WORKSPACE_MEMORY.md']:replace_line(ROOT/rel,'^当前目标继续active。[^\r\n]*'.encode(),CURRENT)
    replace_line(ROOT/'AGENTS.md',rb'^- 2026-10-[0-9]+'.decode().encode()+'主线当前：'.encode()+rb'[^\r\n]*','- 2026-10-31主线当前：3g新增MMC自身C(N)138位置、781核验/37保护文件；作者95.6只与舍入区间相容，保留低精度/共享参照限制。2E20%27/22、10%23/18；3E、v7、原69曲线/原37/标签/冻结保持。固定19来源24端点累计20早期曲线接入，BLAC/CLK/OPC/OPBNP四条继续未准入。P12原16配置×六项/形状、6400新拟合计划已冻结，320预检查，当前0拟合未启动；主six_oneSE_family_mean，整来源外层/4折内层。下一步直接运行冻结P12，不重跑旧3E，不追分改网格；所有近优/A/BP/稳健混合保留、目标active，接续research_progress.json。')
    replace_line(ROOT/'README.md','^当前持续目标（2026-10-31）：[^\r\n]*'.encode(),'当前持续目标（2026-10-31）：输出仍为指定圈数电容保持率。最新3g双电极前20%为27条/22来源，前10%23条/18来源；MMC新增参照保留精度限制，4条记录仍待核。第十二轮有限6400次拟合计划已冻结、320项预检查通过，当前尚未启动。主方案和来源隔离在看新分数前固定；尚无全面达标模型。[当前研究进度](保持率达标研究_v3_主线与近优组合_20261030/研究进度.html) · [冻结训练计划](保持率达标研究_v3_主线与近优组合_20261030/第十二轮_扩充双电极来源验证/training_plan.json)。')
    f=BASE/'README.md';f.write_bytes(('最新更新（2026-10-31第4批与P12冻结）：'+CURRENT+'\n\n以下为历史阶段记录，按对应冻结输入解读。\n\n').encode()+f.read_bytes())
    f=ROOT/'docs/PROGRESS.md';marker='## 2026-10-31 MMC自身参照增量与第十二轮有限计划冻结';assert marker.encode()not in f.read_bytes();f.write_bytes(f.read_bytes()+('\n\n'+marker+'\n\n'+CURRENT+'\n\n文件：P11/batch4_20261031原图/候选/舍入与共享参照说明、3g数据库/781独立核验；精确旧3f指针历史；P12冻结输入/16配置/6400拟合计划/环境/320预检查，三项运行与审计工具。无真实模型拟合，无未报告的新成绩；下一动作执行P12固定计划，再审查全部门槛。源文件保护与本地仅23行历史日志、未封版v8继续保持。\n').encode('utf8'))
    k=ROOT/'docs/knowledge/自身C参照误差与扩充来源预注册_20261031.md';assert not k.exists();k.write_text('''# 自身C(N)参照、舍入边界与扩充来源验证（2026-10-31）

MMC（10.1007/s10854-023-10314-z）正文p8明确2E对称器件、1MNa2SO4、0..1.6V、5A/g30000圈95.6%。PDFp9Fig8c是绝对C(N)。首个实际红点上/左轮廓拟合得自身参考36.553444F/g，3px界限对应0.418605F/g；不借同图倍率电容，不按95.6倒求C0，不断言作者基准为第1圈。所有后续归一化点共享C0的误差，不是独立随机噪声。

近末图读93.332598%，同时传播分子分母3px盒得91.143649～95.572262%。作者95.6本身未落入区间；其一位小数舍入区间95.55～95.65与读图区间仅有0.022262pp重叠。当前用途仅是带精度限制的探索早期输入，不能写成图文精确一致或正式新端点准入。作者原标签95.6、原值和全部难例保留。138图读位置对应1条曲线，不是138实验。该限定结论依赖固定读图界限，不是统计置信度。

BLAC自身C0差异仍未解决；不能选更高第二点来贴96。CLK既有SI的5幅图是FTIR/NMR/SEM及3E倍率/EIS，没有更清晰的循环副图。OPC原目录无新增SI，100/80刻度与图末再核仍不相容。OPBNP下包络圆拟合得到21个候选，图审和早期覆盖均不足，不能当新观测点；该失败试读不构成作者错误。四条继续冻结B用途。

第十二轮只检验扩充2E的27/22与23/18，不重复旧3E。沿用原16配置、六项与已批准形状表达，6400次新拟合均须完整保存；旧7来源预测不能当新27行上的对照。主六项稳定规则、整来源外层和训练内4折在看分数前固定，RF/GPR/XGB/静态及Ridge/ExtraTrees保留。形状、联合选模和近优均为预定对照；A/BP/稳健/混合历史仍有研究价值，未被这次有限比较否定。

来源平衡目标SD在20%为11.035372pp，R²>0.95实际要求同口径RMSE<2.467584pp；10%为SD10.094457pp、RMSE<2.257189pp。不能仅满足3pp就认为R²门槛已通过。全新外部来源仍0，数值过线也不能宣称可靠泛化。

证据：P11/batch4_20261031/MMC_reading_qc.json、five_case_followup.json、independent_verification.json（781项/37保护文件）；P12/training_plan.json、preflight_verification.json（320项，拟合尚未启动）。所有原件、旧69曲线对象、旧库、v7及作者标签保留。
''','utf8');f=ROOT/'docs/KNOWLEDGE_BASE.md';f.write_bytes(f.read_bytes()+'\n- 2026-10-31：[自身C参照、舍入与来源预注册](knowledge/自身C参照误差与扩充来源预注册_20261031.md)：MMC共享参考误差、舍入区间微小重叠的用途限制；四条继续未准入；扩充2E6400拟合计划、严格R²/RMSE关系与未启动状态。\n'.encode())
    # Keep the existing, verified model tables. This publication adds evidence and
    # a not-started finite study, rather than manufacturing new model results.
    old=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'show','9630a32b6a5d33f6aee90408c1309cd7b78d1b82:保持率达标研究_v3_主线与近优组合_20261030/研究进度.html']).decode('utf8')
    changes={
      '本地原文核查第3批':'本地参照复核第4批与验证计划冻结',
      '<h1>网站打不开，改用本地论文继续推进</h1>':'<h1>扩充数据已就绪，第十二轮验证计划冻结</h1>',
      '26条 / 21来源':'27条 / 22来源','前10%为22条/17来源':'前10%为23条/18来源',
      '<span class="number">本批新增12条</span>10个来源组，864个相关图读位置':'<span class="number">本批新增MMC</span>30000圈，138个相关图读位置',
      '<span class="number">5682项核验</span>28个保护文件':'<span class="number">781项核验</span>37个保护文件',
      '累计19条早期曲线接入，另5条仍需精读或补证':'累计20条早期曲线接入，另4条仍需精读或补证；MMC另保留参照精度限制',
      '最新3f研究库':'最新3g研究库',
      '<h2>这批数据具体增加了什么</h2>':'<h2>上一批的具体曲线（原记录保留）</h2>',
      '形状可计算2E20%19条、10%10条':'最新形状可计算2E20%20条、10%11条',
      '<h2>五条还不能强行接入</h2>':'<h2>四条仍待核，MMC另保留精度限制</h2>',
      '<b>MMC：</b>需核实自身C(N)初始参照。':'MMC已带限制接入探索输入，详细说明见上方。',
      '这五条的旧A标签':'这四条的旧A标签',
      '先继续处理五条参照、分辨率和遮挡问题；同时为扩充后的双电极数据冻结下一次有限候选、整来源隔离验证，检查原六项与已批准形状对照。':'下一步直接执行已冻结的第十二轮6400次拟合，分别检验六项与形状对照；四条原件问题继续保留，不能改动本轮已冻结输入。',
      '本批原55曲线对象逐条保持；SQLite完整性、外键、像素/几何、作者标签、来源组及严格窗口通过。':'第4批原69曲线对象逐条保持，781项检查通过；原始C0误差与作者舍入边界保留。',
      '保持率研究：本地第3批曲线接入':'保持率研究：MMC参照与第十二轮计划',
    }
    for a,b in changes.items():assert a in old,a;old=old.replace(a,b)
    extra='''<h2>MMC接入的依据和限制</h2><p>自身首个实际循环红点C0=36.553444F/g，3像素界限±0.418605F/g。近末归一化93.332598%，同时传播分子/参考误差得到91.143649%～95.572262%。<b>作者95.6%本身不在该区间内</b>，但其一位小数舍入区间95.55%～95.65%与读图区间仅小幅相交。因此只接入带精度限制的探索输入，不能说精确一致。未借倍率C0、未按终值缩放、未改作者95.6标签。</p><p><a href="第十一轮_双电极原文曲线补充/batch4_20261031/README.md">本批参照与四条待核说明</a> · <a href="第十一轮_双电极原文曲线补充/batch4_20261031/independent_verification.json">781项核验</a> · <a href="第十一轮_双电极原文曲线补充/batch4_20261031/MMC_overlay.png">MMC原图读点</a></p><div class="box"><b>第十二轮计划已冻结，当前0拟合、未启动。</b>双电极前20%27条/22来源，前10%23条/18来源；原16配置分别用六项和形状表达，共6400次全新拟合。主方案提前固定为六项稳定家族均值，外层整来源留出、内层4折；保留全部家族、难例与失败，不看外层追分。320项预检查通过。R²&gt;0.95还要求同口径RMSE分别低于2.468pp和2.257pp，不能只看3pp。<a href="第十二轮_扩充双电极来源验证/training_plan.json">冻结计划</a> · <a href="第十二轮_扩充双电极来源验证/preflight_verification.json">预检查</a></div>'''
    needle='<h2>上一批的具体曲线（原记录保留）</h2>';old=old.replace(needle,extra+needle);(BASE/'研究进度.html').write_bytes(old.encode())
    print('Published3g/781checks and frozen P12/6400 fits;actual model fits0.')
if __name__=='__main__':main()

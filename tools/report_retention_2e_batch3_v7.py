"""Current data coverage and separately labelled frozen model scores."""
from pathlib import Path
import html,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';B=BASE/'第十一轮_双电极原文曲线补充/batch3_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def main():
    old=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'show','37b1c8880d0a2bd29452d4c103ea7ba22c974ef3:保持率达标研究_v3_主线与近优组合_20261030/研究进度.html']).decode('utf8');style=re.search(r'<style>(.*?)</style>',old,re.S).group(1)
    result=read(BASE/'第十轮_稳健表达与来源权重/results.json');lookup={(m['route'],m['model']):m for m in result['metrics']}
    labels=[('oneSE_family_mean','第十轮预定主方法'),('P9_six_oneSE_family_mean','保留：原六项稳定规则'),('new_only_oneSE_family_mean','第十轮新配置'),('old_only_oneSE_family_mean','原六项/形状联合选择'),('nested_family::RF_early','RF早期'),('nested_family::GPR_early','GPR早期'),('nested_family::XGB_early','XGBoost早期'),('nested_family::RF_static','RF＋材料/工况'),('nested_family::GPR_static','GPR＋材料/工况'),('nested_family::XGB_static','XGBoost＋材料/工况'),('nested_family::Ridge_early','Ridge'),('nested_family::ExtraTrees_early','ExtraTrees'),('nested_family::RidgeGP_residual','Ridge均值＋GPR残差'),('near4_equal','四近优家族等权'),('early_persistence','参照：沿用早期值'),('early_linear','参照：早期斜率外推'),('training_mean','参照：训练来源平均')]
    def table(route):
        rows=[]
        for key,label in labels:
            m=lookup[route,key];rows.append(f'<tr><td>{html.escape(label)}</td><td>{m["r2"]:.3f}</td><td>{m["mae"]:.3f}</td><td>{m["rmse"]:.3f}</td><td>{m["p90_absolute_error"]:.3f}</td><td>{"数值通过"if m["numeric_pass"]else"未达标"}</td></tr>')
        return '<div class="table"><table><thead><tr><th>方法</th><th>R²</th><th>MAE/pp</th><th>RMSE/pp</th><th>90%误差/pp</th><th>验收</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
    main=lookup['B_3E_early20','oneSE_family_mean'];control=lookup['B_3E_early20','P9_six_oneSE_family_mean'];reviews=read(B/'visual_review.json')['curves'];items=[]
    for q in reviews:
        last='遮挡，试读未通过'if q['label']=='OPBNP'else f'{q["near_end_reading"]:.3f}%'
        window_label='试读未可靠'if q['label']=='OPBNP'else'/'.join(str(w['point_count'])for w in q['windows'])
        items.append('<tr><td>'+html.escape(q['label'])+'</td><td>'+str(q['author_retention'])+'%</td><td>'+last+'</td><td>'+window_label+'</td><td>'+('已接入早期研究输入'if q['approved']else'待核，未准入')+'</td></tr>')
    data_table='<div class="table"><table><thead><tr><th>样品/工况</th><th>作者保持率</th><th>近末图读</th><th>10%/20%点数</th><th>当前用途</th></tr></thead><tbody>'+''.join(items)+'</tbody></table></div>'
    body=f'''<p class="small">2026-10-31 · 本地原文核查第3批 · 数据已接入，尚未重新训练</p>
<h1>网站打不开，改用本地论文继续推进</h1>
<p class="status"><b>目标继续active，尚无全面达标模型。</b>输出始终是指定圈数和条件下的电容保持率。最新完成的是证据与早期输入扩充，新增覆盖量不能当成模型精度提升。</p>
<div class="cards"><div class="card"><span class="number">26条 / 21来源</span>当前双电极前20%输入；前10%为22条/17来源</div><div class="card"><span class="number">本批新增12条</span>10个来源组，864个相关图读位置</div><div class="card"><span class="number">5682项核验</span>28个保护文件；本批新增模型拟合0</div></div>
<div class="box"><b>固定队列19来源 / 24端点均已初审。</b>累计19条早期曲线接入，另5条仍需精读或补证。使用本地PDF、JATS XML、补充材料和已有原始图像，没有继续依赖验证页面。最新3f研究库已可调用；主v7、原文、旧3b/c/d/e、作者标签与冻结记录保留。</div>
<h2>这批数据具体增加了什么</h2><p>MF和LYS分别读取正文与自身SI；NWJPC-2找到本地JATS和已有原图；SSC与PPC补上20000圈曲线。PCNaCl两电流的142.22%/116.33%以及PR-2的108.8%是作者报告的真实增长，没有裁成100%。同一论文多个样品和工况始终归一个来源组。</p>
{data_table}<p class="small">864个位置属于12条相关曲线，不是864个独立实验。近末读图至少到目标圈数的97%，用于检查一致性，不补造精确N圈点。3像素界限不是统计置信区间。SSC前10%只有2个实际点，保留原始曲线但未进该窗口；形状可计算2E20%19条、10%10条，其余保留为空。</p>
<h2>五条还不能强行接入</h2><p><b>MMC：</b>需核实自身C(N)初始参照。<b>BLAC：</b>自身参照读图区间仍与作者96%不相容。<b>CLK：</b>原图太小，早期点中心分不清，放大图片不能产生证据。<b>OPC：</b>图末约99.147%，固定读图区间未含正文100%。<b>OPBNP：</b>红色库仑效率点遮住蓝色保持率点，几何试读仍不稳定；失败试读不是作者的新结果或图文争议。</p><p>这五条的旧A标签保留，B早期输入尚未准入。没有借用倍率C0、修改作者标签或放宽3点门槛来凑齐。</p>
<p><a href="第十一轮_双电极原文曲线补充/batch3_20261031/README.md">本批逐条说明</a> · <a href="第十一轮_双电极原文曲线补充/batch3_20261031/independent_verification.json">5682项核验</a> · <a href="第十一轮_双电极原文曲线补充/batch3_20261031/api_verification.json">数据库实际调用核验</a> · <a href="第十一轮_双电极原文曲线补充/batch3_20261031/reading_review_inventory.png">原图与读点总览</a></p>
<h2>模型成绩：仍为第十轮冻结旧输入</h2><p>上一轮9350拟合：8800新流程作业，包含550次额外Ridge均值拟合；另复用8800旧流程预测。以下模型没有见过本批新接入曲线。3E前20%是30条/24来源、10%20条/19来源；该轮2E前20%仅7条/7来源、10%5条/5来源。最新2E的26/21不能用于描述旧训练成绩。</p>
<div class="box"><b>主方法未达标，近优对照继续保留。</b>第十轮3E20%主R²={main['r2']:.3f}、MAE={main['mae']:.3f}pp、RMSE={main['rmse']:.3f}pp；原六项稳定规则{control['r2']:.3f}/{control['mae']:.3f}/{control['rmse']:.3f}。R²&gt;0.95、MAE≤2pp、RMSE≤3pp、尾部误差、比各简单基线改善至少20%和来源泛化须共同通过。真正未触碰的外部验证来源仍为0，不能声称可靠达标。</div>
{table('B_3E_early20')}
<details><summary>展开：第十轮三电极前10%（20条 / 19来源）</summary>{table('B_3E_early10')}</details>
<details><summary>展开：第十轮双电极前20%（旧7条 / 7来源）</summary>{table('B_2E_early20')}</details>
<details><summary>展开：第十轮双电极前10%（旧5条 / 5来源）</summary>{table('B_2E_early10')}</details>
<h2>继续发展的顺序</h2><p>先继续处理五条参照、分辨率和遮挡问题；同时为扩充后的双电极数据冻结下一次有限候选、整来源隔离验证，检查原六项与已批准形状对照。RF、GPR、XGBoost、材料工况组合、A直接预测及BP等路线继续保留。三电极数据本批未变，不重复重跑旧轮追分；2点稀疏方案仍未获批准，不应用。</p>
<p>现有大误差来源CCL长周期活化、CMC、OAC继续保留。新的双电极覆盖能补研究条件范围，但不能代替三电极的长周期证据，也不能代替真正新来源检验。参数优化与精读都要留下失败和不确定性。</p>
<p class="small">本批原55曲线对象逐条保持；SQLite完整性、外键、像素/几何、作者标签、来源组及严格窗口通过。第十轮871907项核验、476保护对象、3850个解析流程预测重建为原冻结输入的历史结果；树权重未重建的限制保留。旧轮重现应使用对应冻结提交，不能为适配滚动指针改写历史。</p>
<p><a href="第十一轮_双电极原文曲线补充/queue_plan.json">原固定来源队列</a> · <a href="第十一轮_双电极原文曲线补充/progress.json">当前接入进度</a> · <a href="第十轮_稳健表达与来源权重/training_plan.json">第十轮冻结计划</a> · <a href="第十轮_稳健表达与来源权重/results.json">第十轮完整结果</a> · <a href="第十轮_稳健表达与来源权重/方法依据与适用边界.md">同行方法与适用边界</a> · <a href="第四轮_选模稳定性复核/results.json">原稳定规则历史</a> · <a href="第六轮_非线性延拓与稳健学习/results.json">非线性/BP历史</a> · <a href="research_goal.json">完整持续目标</a></p>'''
    page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>保持率研究：本地第3批曲线接入</title><style>'+style+'</style></head><body><main>'+body+'</main></body></html>'
    (BASE/'研究进度.html').write_bytes(page.encode('utf8'));print('Dashboard updated;new data not fitted;goalactive.')
if __name__=='__main__':main()

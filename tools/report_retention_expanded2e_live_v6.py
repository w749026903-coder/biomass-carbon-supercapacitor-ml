"""Read actual fit checkpoints and publish a small auto-refresh progress page."""
from pathlib import Path
import json,subprocess,re,datetime,html
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第十二轮_扩充双电极来源验证'
def main():
    review=OUT/'scientific_validity_review.json'
    if review.exists() and json.loads(review.read_text('utf8')).get('status')=='confirmed_forward_corrected_v7r1_and_v3h':
        print('Study closed with semantic correction; keep latest scientific review page.');return
    p=json.loads((OUT/'progress.json').read_text('utf8'));n=p['new_fits'];total=p['planned_new_fits'];status=p['status'];stamp=datetime.datetime.now().astimezone().isoformat(timespec='seconds');running=status=='running';title='训练进行中'if running else'拟合已结束，等待独立核验';body=f'''<h1>第十二轮：{title}</h1><p>输出：指定圈数和条件下的电容保持率。数据为已暴露的开发来源，当前不代表真正新来源泛化。</p><p class="num">{n} / {total} 次拟合（{n/total:.1%}）</p><progress value="{n}" max="{total}"></progress><p>最近检查点耗时 {p.get('elapsed_seconds',0):.1f}秒 · 失败 {p.get('failures',0)} · 旧预测复用0</p><p>当前分支：{html.escape(p.get('route','已结束'))} · 外层留出来源：{html.escape(p.get('outer_source','见最终记录'))}</p><p>前20%27条/22来源；前10%23条/18来源。16配置×六项/形状表达，主方案提前固定为六项稳定规则。全部6400次完成后，再独立核验全部内层选模、来源隔离、编码器和各验收门槛，当前不展示中途最高分。</p><p>MMC参照精度限制、4条未准入记录与真实&gt;100%均保留；A/三电极及其他近优路线不由本轮单独否定。</p><p>最近读取时间：{stamp}。进度来自实际作业检查点，不是预计完成量。</p><p><a href="training_plan.json">冻结计划</a> · <a href="progress.json">原始进度</a> · <a href="../research_goal.json">完整持续目标</a></p>'''
    style='body{margin:36px auto;max-width:960px;padding:0 22px;background:#f5f7f6;color:#173c3b;font:17px/1.8 system-ui}h1{font-size:28px}.num{font-size:30px;font-weight:700}progress{width:100%;height:30px}a{color:#006d70}'
    meta='<meta http-equiv="refresh" content="10">'if running else'';page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+meta+'<title>第十二轮训练进度</title><style>'+style+'</style></head><body>'+body+'</body></html>';(OUT/'训练进度.html').write_bytes(page.encode())
    old=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'show','4866736bfd574ef9ee8e4b8c653c54d878f7730b:保持率达标研究_v3_主线与近优组合_20261030/研究进度.html']).decode('utf8')
    box=f'<div class="box"><b>第十二轮{title}：{n}/{total}次，{n/total:.1%}。</b>失败{p.get("failures",0)}，进度来自真实作业检查点；主方案和输入已冻结，尚未发布本轮分数。<a href="第十二轮_扩充双电极来源验证/训练进度.html">查看自动刷新训练进度</a></div>'
    old=re.sub(r'(</h1>)',lambda m:m[0]+box,old,count=1);old=old.replace('当前0拟合、未启动','当前'+str(n)+'/'+str(total)+'次，'+title).replace('数据已接入，尚未重新训练','数据已接入，'+title).replace('本批新增模型拟合0','本批数据已接入；训练状态见上方')
    (BASE/'研究进度.html').write_bytes(old.encode());root=json.loads((BASE/'research_progress.json').read_text('utf8'));root.update(phase12=status,phase12_actual_fits=n,phase12_process_session=38500,model_process_running=running);(BASE/'research_progress.json').write_text(json.dumps(root,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(dict(status=status,actual_checkpoint_fits=n,total=total,report='训练进度.html',observed_at=stamp),ensure_ascii=False))
if __name__=='__main__':main()

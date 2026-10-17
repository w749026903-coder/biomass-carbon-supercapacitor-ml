from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'target_metadata.py').read_text(encoding='utf-8');start=s.index("ids='''");end=s.index("'''.split()",start)+len("'''.split()")
ids=['10.1016/j.indcrop.2025.120584','10.1021/acsaem.4c01748','10.1021/acssusresmgt.4c00329','10.1021/acssusresmgt.3c00028','10.1016/j.rineng.2026.112940','10.1021/acsomega.4c06494','10.1007/s10904-026-04338-1','10.1002/eem2.70174','10.1002/slct.202506431','10.1021/acsomega.3c00816','10.3390/polym15234478','10.3390/ma17133091']
s=s[:start]+"ids='''"+'\n'.join(ids)+"'''.split()"+s[end:]
s=s.replace("bydoi={x['doi']:x for x in json.loads((ROOT/'开放与付费候选发现.json').read_text(encoding='utf-8'))}","bydoi={x['doi']:x for name in ['开放与付费候选发现.json','补充原料候选发现.json'] for x in json.loads((ROOT/name).read_text(encoding='utf-8'))}").replace('str(i+1)','str(i+51)').replace('定向候选身份与获取记录','第二轮定向身份与获取记录')
(ROOT/'target_more_metadata.py').write_text(s,encoding='utf-8')
exec(compile(s,str(ROOT/'target_more_metadata.py'),'exec'))

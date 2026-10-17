from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'expand_acquisition.py').read_text(encoding='utf-8');start=s.index("ids='''");end=s.index("'''.split()",start)+len("'''.split()")
ids=['10.3390/polym17131752','10.3390/polym17091198','10.1039/d4ra08818b','10.3390/nano13101654','10.3390/ma19132797']
s=s[:start]+"ids='''"+'\n'.join(ids)+"'''.split()"+s[end:]
s=s.replace('str(i+19)','str(i+56)').replace('追加开放全文获取记录','三电极优先第二轮全文获取记录')
exec(compile(s,str(ROOT/'fetch_three_priority_more.py'),'exec'))

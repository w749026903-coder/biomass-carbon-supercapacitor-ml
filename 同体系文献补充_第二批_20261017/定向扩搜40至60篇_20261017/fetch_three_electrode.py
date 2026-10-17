from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'expand_acquisition.py').read_text(encoding='utf-8');start=s.index("ids='''");end=s.index("'''.split()",start)+len("'''.split()")
ids=['10.1021/acsomega.2c07932','10.1021/acsomega.5c08826','10.3390/nano14080686','10.3390/bioengineering12080841','10.3390/ma17133233','10.3390/polym18182203','10.1016/j.heliyon.2023.e21804','10.3390/gels10070462','10.3390/en16093824','10.1039/d4nj04272g']
s=s[:start]+"ids='''"+'\n'.join(ids)+"'''.split()"+s[end:]
s=s.replace('str(i+19)','str(i+46)').replace('追加开放全文获取记录','三电极优先补搜获取记录')
exec(compile(s,str(ROOT/'fetch_three_electrode.py'),'exec'))

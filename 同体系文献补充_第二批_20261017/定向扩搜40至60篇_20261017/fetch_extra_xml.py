from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'expand_acquisition.py').read_text(encoding='utf-8');start=s.index("ids='''");end=s.index("'''.split()",start)+len("'''.split()")
ids=['10.1021/acsomega.3c00816','10.1021/acsomega.4c06494','10.3390/nano13172431','10.3390/polym15234478','10.3390/ma17133091']
s=s[:start]+"ids='''"+'\n'.join(ids)+"'''.split()"+s[end:]
s=s.replace('str(i+19)','str(i+41)').replace('追加开放全文获取记录','第三轮开放全文获取记录')
exec(compile(s,str(ROOT/'fetch_extra_xml.py'),'exec'))

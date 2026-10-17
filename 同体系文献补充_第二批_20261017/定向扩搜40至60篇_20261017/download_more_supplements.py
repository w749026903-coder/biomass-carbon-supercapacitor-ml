from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'download_supplements.py').read_text(encoding='utf-8').replace("if not supp:continue","if not supp or p.parent.name in {x['id'] for x in json.loads((ROOT/'扩搜补充材料获取日志.json').read_text(encoding='utf-8'))}:continue").replace("(ROOT/'扩搜补充材料获取日志.json').write_text","(ROOT/'三电极及追加补充材料获取日志.json').write_text")
exec(compile(s,str(ROOT/'download_more_supplements.py'),'exec'))

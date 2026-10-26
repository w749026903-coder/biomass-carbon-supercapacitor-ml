"""Pin the historical correction-goal snapshot for immutable historical checks.
Current cycling v0.26 counters are verified separately. No scientific file changes.
"""
from pathlib import Path
from unittest.mock import patch
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
SNAPSHOT=ROOT/'文献全量利用复核_20261027/批次19_木质素纳米纤维蛋米与烟草系列/historical_goal_at_v18.json'
def run():
    original=Path.read_text;frozen=original(SNAPSHOT,encoding='utf8');old=json.loads(frozen)
    current=json.loads(original(ROOT/'docs/DATA_CORRECTION_GOAL.json',encoding='utf8'))
    assert old['fixed_record_count']==current['fixed_record_count']==39 and old['current_pending']==38
    def pinned_read(self,*a,**kw):
        if self.resolve()==(ROOT/'docs/DATA_CORRECTION_GOAL.json').resolve():return frozen
        return original(self,*a,**kw)
    with patch.object(Path,'read_text',pinned_read):
        from verify_lignin_egg_tobacco_chain_v19 import run as historical
        historical(False)
if __name__=='__main__':run()

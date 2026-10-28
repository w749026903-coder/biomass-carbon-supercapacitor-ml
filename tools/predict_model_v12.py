"""Use the verified local research weight; never promises a design value."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import joblib
from tools.train_model_v1 import sha,read
from tools.prepare_model_v12 import RUN
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True,type=Path);args=ap.parse_args()
    card=read(RUN/'model_card.json');model_path=RUN/'model_v1_2.joblib'
    if sha(model_path)!=card['final_model_sha256']:raise ValueError('Research weight fingerprint differs')
    model=joblib.load(model_path);records=read(args.input)
    if isinstance(records,dict):records=[records]
    print(json.dumps(model.predict_with_context(records),ensure_ascii=False,indent=2,allow_nan=False))

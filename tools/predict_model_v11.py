"""Local research inference with dual units and an explicit reliability status."""
from pathlib import Path
import argparse,json,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


if __name__=='__main__':
    import joblib
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True);parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args();path=args.model.resolve()
    if ROOT not in path.parents:raise ValueError('Use a trusted project-generated model only.')
    model=joblib.load(path)
    predictions=model.predict_with_context(json.loads(args.input.read_text('utf-8')))
    # No numerical recommendation is promoted to a design decision merely by successful loading.
    output={'model_version':'1.1','prediction_unit':'percent and dimensionless ratio explicitly separated',
        'reliable_design_value':None,'research_predictions':predictions,
        'independent_validation_available':False}
    print(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False))

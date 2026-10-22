"""Call the locally fitted v1.0 model with a JSON array of correctly defined inputs."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


if __name__ == '__main__':
    import joblib
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    # Only load a trusted artifact produced by this project; joblib is executable serialization.
    model_path = args.model.resolve()
    if ROOT not in model_path.parents:
        raise ValueError('Use a trusted project-local model artifact.')
    model = joblib.load(model_path)
    inputs = json.loads(args.input.read_text('utf-8'))
    outputs = model.predict_with_context(inputs)
    text = json.dumps(outputs, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        destination = args.output.resolve()
        if ROOT not in destination.parents or destination.exists():
            raise ValueError('Use a new project-local output file.')
        destination.write_text(text, encoding='utf-8')
    else:
        print(text)

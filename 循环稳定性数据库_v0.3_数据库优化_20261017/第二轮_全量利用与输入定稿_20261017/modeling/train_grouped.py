"""Default invocation performs read-only checks, never fitting."""
import argparse
import json
from prepare_dataset import CONTRACT, preflight
from train_nested import train

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--run-name')
    parser.add_argument('--feature-set', choices=list(CONTRACT['feature_sets']), default='plus_BET')
    args = parser.parse_args()
    if args.train:
        train(args.feature_set, args.run_name)
    else:
        print(json.dumps(preflight(),ensure_ascii=False,indent=2))

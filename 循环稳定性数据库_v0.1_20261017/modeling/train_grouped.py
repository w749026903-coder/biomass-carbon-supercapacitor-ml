"""Future training entry. Default is read-only readiness checking."""
import argparse,json
from prepare_dataset import preflight
from train_nested import train,source_disjoint
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--train',action='store_true')
    parser.add_argument('--feature-set',choices=['protocol_only','plus_BET'],default='plus_BET')
    args=parser.parse_args()
    if args.train:
        train(args.feature_set)
    else:
        print(json.dumps(preflight(),ensure_ascii=False,indent=2))

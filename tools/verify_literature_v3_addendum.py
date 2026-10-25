"""Verify immutable v3 seal and the separately fingerprinted scope addendum."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'文献全量利用复核_20261025/批次03_多样品与工况'
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 report=json.loads((OUT/'addendum_manifest.json').read_text('utf8'))
 assert digest(OUT/'merge_manifest.json')==report['unchanged_primary_manifest_sha256']
 for item in report['outputs']:
  p=(ROOT/item['path']).resolve();assert ROOT in p.parents and digest(p)==item['sha256']
 primary=json.loads((OUT/'merge_manifest.json').read_text('utf8'))
 for item in primary['outputs']:assert digest(ROOT/item['path'])==item['sha256']
 scope=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
 assert scope['full_source_completion_claimed'] is False and len(scope['sources'])==4
 assert all(v['remaining'] for v in scope['sources'].values())
 print(json.dumps(dict(status='passed',primary_payloads=len(primary['outputs']),addendum_payloads=len(report['outputs']),scientific_values_changed=False,all_source_completion_claimed=False),ensure_ascii=False))
if __name__=='__main__':main()

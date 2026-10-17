"""Read-only upload checks. Never print matched credential values."""
from __future__ import annotations
import hashlib,json,re,subprocess,zipfile
from pathlib import Path

TEXT_EXT={'.py','.ps1','.json','.jsonl','.md','.txt','.html','.xml','.yaml','.yml','.toml','.ini','.cfg','.js','.mjs','.ts','.csv','.ipynb','.sql'}
LFS_EXT={'.pdf','.zip','.docx','.doc','.xlsx','.xls','.sqlite','.db'}
SECRET_RULES=[
 ('private_key',re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
 ('github_token',re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b')),
 ('openai_token',re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}\b')),
 ('aws_access_key',re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
 ('bearer_literal',re.compile(rb'(?i)\bBearer[ \t]+[A-Za-z0-9._-]{28,}\b')),
]
def git(root,*args,check=True):
    r=subprocess.run(['git','-C',str(root),*args],capture_output=True,check=False)
    if check and r.returncode:raise RuntimeError(r.stderr.decode('utf-8','replace').strip())
    return r
def project_files(root):
    names=set()
    for opts in [('--cached',),('--others','--exclude-standard')]:
        r=git(root,'ls-files','-z',*opts)
        names.update(n.decode('utf-8') for n in r.stdout.split(b'\0') if n)
    return [root/n for n in sorted(names) if (root/n).is_file()]
def scan(paths,root):
    findings=[];large=[];archives=[];total=0;lfs_bytes=0
    for p in paths:
        rel=p.relative_to(root).as_posix();size=p.stat().st_size;total+=size
        if p.suffix.lower() in LFS_EXT:lfs_bytes+=size
        if size>=100*1024*1024 and p.suffix.lower() not in LFS_EXT:large.append(rel)
        if p.suffix.lower() in TEXT_EXT or p.name in ['.gitignore','.gitattributes']:
            # Read the entire source, including large discovery JSON; findings expose only rule/path.
            blob=p.read_bytes()
            for name,pattern in SECRET_RULES:
                hit=pattern.search(blob)
                if hit:findings.append({'path':rel,'line':blob.count(b'\n',0,hit.start())+1,'rule':name})
        if p.suffix.lower()=='.zip':
            try:
                with zipfile.ZipFile(p) as z:
                    risky=[m.filename for m in z.infolist() if Path(m.filename).name.lower() in ['.env','credentials.json','cookies.json','cookies.txt','id_rsa','id_ed25519','hosts.yml']]
                if risky:archives.append({'path':rel,'credential_named_members':risky})
            except zipfile.BadZipFile:archives.append({'path':rel,'error':'invalid_zip'})
    return {'file_count':len(paths),'bytes':total,'estimated_lfs_bytes_before_dedup':lfs_bytes,'credential_pattern_findings':findings,'oversize_non_lfs_files':large,'archive_findings':archives,'scope':'Known credential patterns and credential-named archive members; not a guarantee that all sensitive content is absent.'}
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];out=scan(project_files(root),root)
    target=root/'docs/git_sync/preflight.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    raise SystemExit(bool(out['credential_pattern_findings'] or out['oversize_non_lfs_files'] or out['archive_findings']))

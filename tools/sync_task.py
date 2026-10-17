"""Complete a project task with a scoped commit and verified push; no background watcher."""
from __future__ import annotations
import argparse,datetime,json,os,subprocess,sys
from pathlib import Path
from repository_checks import git,scan

def text(root,*args):return git(root,*args).stdout.decode('utf-8','replace').strip()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ['message','summary','checks','next']:ap.add_argument('--'+k,required=True)
    ap.add_argument('--paths',nargs='+',required=True);ap.add_argument('--dry-run',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    if Path(text(root,'rev-parse','--show-toplevel')).resolve()!=root:raise RuntimeError('Repository root mismatch')
    if git(root,'diff','--cached','--quiet',check=False).returncode:raise RuntimeError('Staging area is not empty. Preserve the other task staging; do not reset it.')
    branch=text(root,'branch','--show-current')
    if not branch:raise RuntimeError('Detached HEAD; select the intended task branch explicitly first.')
    configured=json.loads((root/'project_repository.json').read_text(encoding='utf-8'))
    remote=text(root,'remote','get-url','origin')
    expected=configured['expected_origin']
    allowed={expected,expected.removesuffix('.git'),'git@github.com:'+configured['github_owner']+'/'+configured['repository_name']+'.git'}
    if remote not in allowed:raise RuntimeError('origin does not match the user-authorized project repository.')
    owned=[];files=[]
    for name in args.paths:
        p=(root/name).resolve()
        if p==root or root not in p.parents:raise RuntimeError('Explicit task paths required; root-wide staging and outside paths are not allowed.')
        if any(part in ['.git','.venv','node_modules'] for part in p.relative_to(root).parts):raise RuntimeError('Runtime or Git metadata cannot be a task path.')
        owned.append(p.relative_to(root).as_posix())
        if p.is_file():files.append(p)
        elif p.is_dir():files.extend(x for x in p.rglob('*') if x.is_file() and not any(q in x.parts for q in ['.git','.venv','node_modules','__pycache__']))
        else:raise RuntimeError('Path missing; deletions require a separate reviewed Git operation: '+name)
    if text(root,'status','--porcelain','--','docs/PROGRESS.md') and 'docs/PROGRESS.md' not in owned:
        raise RuntimeError('Progress log already has uncommitted changes; review it and explicitly include docs/PROGRESS.md in owned paths first.')
    # Exclude ignored files before scanning, and catch credential literals before any staging.
    candidates=[]
    for f in files:
        if git(root,'check-ignore','--quiet',str(f.relative_to(root)),check=False).returncode!=0:candidates.append(f)
    check=scan(list(dict.fromkeys(candidates)),root)
    if check['credential_pattern_findings'] or check['oversize_non_lfs_files'] or check['archive_findings']:raise RuntimeError(json.dumps(check,ensure_ascii=False))
    print(json.dumps({'branch':branch,'origin':remote,'owned_paths':owned,'files_checked':len(candidates),'dry_run':args.dry_run},ensure_ascii=False))
    if args.dry_run:return
    gitdir=Path(text(root,'rev-parse','--absolute-git-dir'));lock=gitdir/'task-progress-sync.lock'
    descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(descriptor,str(os.getpid()).encode());os.close(descriptor)
        # Check again after acquiring our lock; never absorb another task's staged work.
        if git(root,'diff','--cached','--quiet',check=False).returncode:raise RuntimeError('Staging changed while waiting; stop and preserve it.')
        tz=datetime.timezone(datetime.timedelta(hours=8));now=datetime.datetime.now(tz).isoformat(timespec='seconds')
        log=root/'docs/PROGRESS.md'
        entry='\n## '+now+'：'+args.summary+'\n\n- 结果：'+args.summary+'\n- 文件：'+', '.join(owned)+'\n- 验证：'+args.checks+'\n- 下一步/未决：'+getattr(args,'next')+'\n- Git：本条随任务提交；远程成功以本次命令最后的SHA核验为准。\n'
        with log.open('a',encoding='utf-8',newline='') as f:f.write(entry)
        git(root,'--literal-pathspecs','add','--',*owned,'docs/PROGRESS.md')
        git(root,'commit','-m',args.message)
        commit=text(root,'rev-parse','HEAD')
        push=git(root,'push','--set-upstream','origin',branch,check=False)
        if push.returncode:
            print(push.stderr.decode('utf-8','replace'),file=sys.stderr);raise RuntimeError('Local commit preserved: '+commit+'; remote push failed.')
        remote_line=text(root,'ls-remote','origin','refs/heads/'+branch)
        remote_sha=remote_line.split()[0] if remote_line else None
        if remote_sha!=commit:raise RuntimeError('Remote verification differs; inspect commits before claiming sync.')
        print(json.dumps({'synchronized':True,'branch':branch,'local_commit':commit,'remote_commit':remote_sha},ensure_ascii=False))
    finally:
        # This process created this exact lock; never delete Git's own index.lock.
        if lock.is_file():lock.unlink()
if __name__=='__main__':
    try:main()
    except Exception as exc:print('Sync stopped: '+str(exc),file=sys.stderr);raise SystemExit(1)

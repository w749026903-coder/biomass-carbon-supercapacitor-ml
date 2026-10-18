"""Recover declared nested SI ZIPs and use normal OS TLS for chain failures."""
from acquire_literature_supply_20261018 import OUT,ROOT,dump,pdf_identity,safeurl
from pathlib import Path,PurePosixPath
import concurrent.futures,hashlib,json,subprocess,zipfile

def fix_nested():
    fixes=[]
    for log in (OUT/'records').glob('SUP_???.json'):
        r=json.loads(log.read_text(encoding='utf-8'))
        if r['SI_obtained'] or not r.get('declared_supplement_filenames'):continue
        archive=OUT/'sources'/r['supply_id']/'primary_assets.zip'
        if not archive.exists():continue
        names={x.lower() for x in r['declared_supplement_filenames']};found=[]
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                name=PurePosixPath(info.filename).name
                if name.lower() not in names or not name.lower().endswith('.zip'):continue
                body=z.read(info);nested=zipfile.ZipFile(__import__('io').BytesIO(body));assert nested.infolist()
                for member in nested.infolist():assert not PurePosixPath(member.filename).is_absolute() and '..' not in PurePosixPath(member.filename).parts
                p=archive.parent/'assets'/name;p.parent.mkdir(exist_ok=True)
                if not p.exists():
                    with p.open('xb') as f:f.write(body)
                else:assert p.read_bytes()==body
                r['files'].append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'role':'SI','identity_basis':'Declared SI filename in exact-PMC primary package; valid nested ZIP','source_url':next(f['source_url'] for f in r['files'] if f['role']=='archive')});found.append(name)
        if found:
            fixes.append({'doi':r['doi'],'previous_status':r['SI_status'],'new_status':'obtained','reason':'Declared nested ZIP was present in the archive; now retained as a standalone SI file.','files':found});r['SI_obtained']=True;r['SI_status']='obtained';dump(log,r)
    dump(OUT/'nested_SI_recovery.json',fixes);print('nested_SI_recovered',len(fixes),flush=True)

def transport(r):
    log=OUT/'records'/(r['supply_id']+'.json');cache=OUT/'transport_cache';cache.mkdir(exist_ok=True);attempts=[]
    urls=[a['url'] for a in r['attempts'] if 'CERTIFICATE_VERIFY_FAILED' in a.get('reason','')]
    for i,url in enumerate(urls[:2]):
        target=cache/(r['supply_id']+'_'+str(i)+'.bin')
        if target.exists():continue
        # curl on this host uses normal Windows certificate validation. No -k,
        # security-option changes, shared runtime edits or account access.
        run=subprocess.run(['curl.exe','--location','--fail','--max-time','40','--proxy','http://127.0.0.1:7890','--output',str(target),url],capture_output=True)
        item={'url':url,'transport':'curl_default_TLS_validation','returncode':run.returncode}
        if run.returncode==0 and target.exists():
            body=target.read_bytes()
            try:
                identity=pdf_identity(body,r);p=OUT/'sources'/r['supply_id']/'main_repository_verified.pdf';assert not p.exists()
                with p.open('xb') as f:f.write(body)
                r['files'].append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'role':'main_pdf','identity_basis':identity,'source_url':safeurl(url)});r['main_complete']=True;r['main_pdf_obtained']=True;r['main_status']='existing_or_new_complete_fulltext';item['status']='obtained_identity_verified'
            except Exception as e:item.update(status='not_verified_pdf',reason=str(e))
        else:item.update(status='failed',reason=run.stderr.decode('utf-8','replace')[-600:])
        attempts.append(item)
        if r['main_complete']:break
    r['attempts']+=attempts;dump(log,r);return {'doi':r['doi'],'attempts':attempts,'main_complete':r['main_complete']}

if __name__=='__main__':
    fix_nested();rows=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'records').glob('SUP_???.json')];rows=[r for r in rows if not r['main_complete'] and any('CERTIFICATE_VERIFY_FAILED' in a.get('reason','') for a in r['attempts'])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(transport,rows))
    dump(OUT/'transport_followup.json',results)
    print(json.dumps([{'doi':r['doi'],'main_complete':r['main_complete']} for r in results],ensure_ascii=False),flush=True)

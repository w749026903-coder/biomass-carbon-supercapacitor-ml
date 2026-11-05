"""Freeze a DOI shortlist and expose only whitelisted structure, never target values."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import now, read, sha, write
from tools.retention_blind_reserve_v22 import BASE, ENDPOINT, db_matches, flat, plain

P22 = BASE / '第二十二轮_外部验证来源盲态预留_20261105'
CACHE = ROOT / '.local-literature-cache/P32'
OUT = BASE / '第三十二轮_盲态文献筛选扩充_20261105'
SELECTED = {
    '10.1002/gch2.202300315': 'fungal_carbon',
    '10.1039/d0na00778a': 'pomelo_seed',
    '10.1039/d2ra03949d': 'chitosan_control_check',
    '10.3390/ma15165748': 'seaweed_carbon',
    '10.3390/nano12152647': 'coffee_side_stream',
}
P22_PENDING = {'10.1002/smll.202513011', '10.3390/nano13222924', '10.1021/acsomega.1c00448'}
CHEMISTRY = {
    'three_electrode': r'three[\s\u2010-\u2013-]+electrode|3[\s\u2010-\u2013-]+electrode',
    'two_electrode': r'two[\s\u2010-\u2013-]+electrode|2[\s\u2010-\u2013-]+electrode|symmetric supercapacitor',
    'aqueous': r'\baqueous\b|\b(?:KOH|H2SO4|Na2SO4|NaOH)\b',
    'gcd': r'galvanostatic|\bGCD\b',
    'solid_gel': r'polymer gel|solid.state|\bPVA\b',
    'organic': r'acetonitrile|ionic liquid|organic electrolyte',
}
MATERIAL = {
    'pomelo': r'pomelo\s+seed', 'fungal': r'fungal|fungus|myceli', 'chitosan': r'chitosan',
    'seaweed': r'seaweed|Sargassum|sea algae', 'coffee': r'coffee', 'lignin': r'lignin',
    'polymer_resin': r'phenolic resin|resorcinol.formaldehyde|polyacrylonitrile|polyurethane',
    'commercial_carbon': r'commercial activated carbon|commercial carbon black',
    'coal_pitch': r'coal tar|coal pitch|petroleum pitch',
    'composite': r'MXene|graphene composite|TiO2|MnO2|polyaniline|polypyrrole|\bPEDOT\b',
}
CYCLING = re.compile(r'cycl(?:ing|ic|e) (?:stabilit|performance|life|durabilit)|capacitance retention|long[\s-]term cycl|charge.discharge cycles', re.I)


def freeze():
    assert not OUT.exists(), 'A blind shortlist cannot be replaced'
    candidates = read(CACHE / 'novel_titles.json')
    meta = read(CACHE / 'lite.json')
    seen22 = read(P22 / 'metadata_freeze.json')
    p22_hashes = {row['doi']:row['sha256'] for row in read(P22/'structural_screen.json')['results']}
    assert set(SELECTED) <= set(candidates) and len(meta['rows'])==162
    counts = db_matches(set(SELECTED)|P22_PENDING)
    rows = []
    for doi, kind in SELECTED.items():
        x = candidates[doi]
        title = plain(x['title'])
        assert not re.search(r'%|\b[0-9,]+\s+cycles\b',title,re.I)
        for field in (doi,title.rstrip('.')):
            probe = subprocess.run(['rg','-ilF','-g','*.md','-g','*.json','-g','*.csv','-g','*.txt','-g','*.xml',field,'.'],
                                   cwd=ROOT,capture_output=True,check=False)
            assert probe.returncode in (0,1),field
            assert not probe.stdout,field
        assert not any(counts[doi].values())
        rows.append(dict(doi=doi,pmcid=x['pmcid'],title=title,authors=x['authorString'],date=x['firstPublicationDate'],
                         kind=kind,exact_source_catalog_counts=counts[doi],archive='P32',url=ENDPOINT+x['pmcid']+'/fullTextXML'))
    for x in seen22['candidates']:
        if x['doi'] in P22_PENDING:
            assert not any(counts[x['doi']].values())
            rows.append(dict(doi=x['doi'],pmcid=x['pmcid'],title=x['title'],authors=x['authors'],date=x['date'],
                             kind='previously_sealed_scope_review',exact_source_catalog_counts=counts[x['doi']],archive='P22',
                             prior_sha256=p22_hashes[x['doi']]))
    assert len(rows)==8
    guard = [Path(__file__),P22/'metadata_freeze.json',P22/'structural_screen.json',BASE/'research_goal.json',
             ROOT/'data/current_retention_research.json',ROOT/'data/current_training_latest.json']
    OUT.mkdir()
    plan = dict(frozen_at=now(),primary_metadata_service='Europe PMC lite',metadata_queries=meta['queries'],
                metadata_unique_doi_pmcid=len(meta['rows']),preselection_novel_titles=len(candidates),candidates=rows,
                correction_plan='Pomelo correction metadata DOI 10.1039/d4na90016b is paired; check correction type without exposing prose.',
                exposure_boundary='Title, authors, DOI, fixed yes/no signals and figure ordinal only. No sentence, label, figure image, '
                                  'capacitance numbers or endpoints emitted. Geometry remains sealed.',
                protected={x.relative_to(ROOT).as_posix():sha(x) for x in guard})
    write(OUT/'metadata_freeze.json',plan)
    write(OUT/'freeze_receipt.json',dict(plan_sha256=sha(OUT/'metadata_freeze.json'),endpoint_values_at_freeze=0))


def fetch(url):
    a = build_opener(ProxyHandler({'https':'http://127.0.0.1:7890'}))
    with a.open(url,timeout=18) as f:
        return f.read(8*1024*1024)


def flags(text, keywords):
    return {k:bool(re.search(p,text,re.I)) for k,p in keywords.items()}


def screening(row):
    doi, pmcid = (row[k] for k in ('doi','pmcid'))
    path = ROOT/'.local-literature-cache'/row['archive']/f'{pmcid}_sealed_fulltext.xml'
    try:
        raw = fetch(row['url']) if row['archive']=='P32' else path.read_bytes()
        doc = ET.fromstring(raw)
    except (HTTPError, URLError, ET.ParseError, TimeoutError) as e:
        return dict(doi=doi,status='asset_unavailable',http=getattr(e,'code',None),failure_type=type(e).__name__)
    assert any(n.get('pub-id-type')=='doi' and flat(n).lower()==doi for n in doc.iter('article-id')),pmcid
    if row['archive']=='P32':
        with path.open('xb') as f:
            f.write(raw)
    else:
        assert sha(path)==row['prior_sha256'],pmcid
    methods = []
    for section in doc.findall('./body//sec'):
        title = section.find('title')
        if title is not None and re.search(r'method|experimental|materials|fabrication|preparation|electrochemical',flat(title),re.I):
            methods.extend(flat(n) for n in section.findall('./p'))
    body = doc.find('./body')
    assert body is not None
    candidate_figures = []
    for i,fig in enumerate(body.findall('.//fig'),1):
        cap = fig.find('caption')
        if cap is not None and CYCLING.search(flat(cap)):
            candidate_figures.append(dict(ordinal=i,graphic_present=fig.find('.//graphic') is not None,
                                          caption_flags=flags(flat(cap),CHEMISTRY)))
    return dict(doi=doi,pmcid=pmcid,status='sealed_identity_verified',sha256=sha(path),
                local=path.relative_to(ROOT).as_posix(),method_paragraphs=len(methods),
                method_flags=flags(' '.join(methods),CHEMISTRY),material_cues=flags(flat(body),MATERIAL),
                candidate_figures=candidate_figures,supplement_count=len(body.findall('.//supplementary-material')))


def correction_flags():
    pmcid = 'PMC10863725'
    raw = fetch(ENDPOINT+pmcid+'/fullTextXML')
    doc = ET.fromstring(raw)
    assert any(n.get('pub-id-type')=='doi' and flat(n).lower()=='10.1039/d4na90016b' for n in doc.iter('article-id'))
    path = CACHE/f'{pmcid}_sealed_correction.xml'
    with path.open('xb') as f:
        f.write(raw)
    s = flat(doc.find('./body'))
    words = {'credit_or_attribution':r'credit|licen[cs]|acknowledge|copyright|permission',
             'figure_or_image':r'\bfig(?:ure)?\.?\s*[0-9]|images?|graphics?',
             'cycling_or_retention':r'cycl(?:ing|e)|retention|durability',
             'label_or_result':r'typo|incorrect|data|measurement|result|units?'}
    return dict(doi='10.1039/d4na90016b',pmcid=pmcid,sha256=sha(path),
                local=path.relative_to(ROOT).as_posix(),cues=flags(s,words))


def screen():
    plan_path = OUT/'metadata_freeze.json'
    plan = read(plan_path)
    assert sha(plan_path)==read(OUT/'freeze_receipt.json')['plan_sha256']
    assert all(sha(ROOT/p)==h for p,h in plan['protected'].items())
    assert not (OUT/'structural_screen.json').exists()
    with ThreadPoolExecutor(max_workers=4) as p:
        results = list(p.map(screening,plan['candidates']))
    correction = correction_flags()
    write(OUT/'structural_screen.json',dict(metadata_sha256=sha(plan_path),results=results,correction=correction,
         endpoint_values_emitted=0,full_curves_displayed=0,verified_early_inputs=0,new_fits=0,accepted_external_sources=0))


if __name__ == '__main__':
    {'freeze':freeze,'screen':screen}[sys.argv[1]]()

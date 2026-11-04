"""Freeze bibliographic candidates and screen full-text structure without exposing endpoints."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, ProxyHandler
import json
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, write, sha, now

BASE = ROOT / '保持率达标研究_v3_主线与近优组合_20261030'
CACHE = ROOT / '.local-literature-cache/P22'
OUT = BASE / '第二十二轮_外部验证来源盲态预留_20261105'
ENDPOINT = 'https://www.ebi.ac.uk/europepmc/webservices/rest/'
SELECTED = {
    '10.1002/smll.202513011': 'Precursors unconfirmed. Screen the supercapacitor test separately from the battery test.',
    '10.1021/acsomega.5c12478': 'Precursors and final material phase unconfirmed; identify the tested porous carbon.',
    '10.3390/nano13222924': 'Verify whether an eligible biomass fraction is the actual cycling electrode.',
    '10.1039/d1ra06154b': 'Yam waste precursor title; verify actual GCD configuration and material.',
    '10.1021/acsomega.1c00448': 'Lignin-based matrix title; check for an eligible carbon-only control and distinct test.',
    '10.1039/c9ra08319g': 'Zanthoxylum husk precursor title; verify actual GCD configuration and material.',
}
REMAINING = {
    '10.1039/d6ra07397b': 'Solid polymer electrolyte and laser-induced graphene title.',
    '10.34133/research.1322': 'Editorial.',
    '10.1039/d5ra09914e': 'Nickel-coated textile; biomass origin and eligible control not apparent.',
    '10.3390/polym18020282': 'Review and pitch precursor.',
    '10.1021/acsaem.2c01222': 'Carbon-yarn electrode; cellulose hydrogel does not establish biomass carbon electrode.',
    '10.1039/d2ra00978a': 'Waste zinc-carbon battery precursor and solid-state device.',
    '10.3390/molecules26123554': 'Lignin-carbon/ZnO composite title; hold for distinct carbon-only evidence.',
    '10.1039/d0ra02935a': 'Shell refers to hollow-sphere geometry; biomass origin not apparent.',
    '10.1039/c9ra09237d': 'PVC waste precursor.',
}


def db_matches(entries):
    totals = defaultdict(dict)
    for name, col in [('current_training_latest', 'doi'), ('current_retention_research', 'source_family')]:
        ptr = read(ROOT / f'data/{name}.json')
        path = ROOT / (ptr['database'] if 'database' in ptr else Path(ptr['directory']) / ptr['database_file'])
        assert sha(path) == ptr['sha256']
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            for doi in entries:
                totals[doi][name] = db.execute(f'SELECT count(*) FROM sources WHERE lower({col}) IN (?,?)', (doi, 'doi:'+doi)).fetchone()[0]
    return totals


def plain(title):
    return re.sub(r'<[^>]+>', '', unescape(title))


def freeze():
    assert not OUT.exists()
    metadata = read(CACHE/'metadata_lite.json')
    prior = read(CACHE/'prior_matches.json')
    eligible = {r['doi'].lower():r for r in metadata['results'] if not prior.get(r['doi'].lower())}
    assert len(metadata['results']) == 194 and len(prior) == 181
    assert set(eligible) == set(SELECTED) | set(REMAINING)
    found = db_matches(SELECTED)
    rows = []
    for doi, question in SELECTED.items():
        row = eligible[doi]
        assert row['isOpenAccess'] == 'Y' and row['hasPDF'] == 'Y' and not any(found[doi].values())
        title = plain(row['title'])
        # DOI absence alone can miss alternate copies. Title checks run before writing the freeze.
        cmd = ['rg','-ilF','-g','*.md','-g','*.json','-g','*.xml','-g','*.txt',title.rstrip('.'),'.']
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, check=False)
        assert result.returncode == 1 and not result.stdout
        rows.append(dict(doi=doi, pmcid=row['pmcid'], title=title, authors=row['authorString'], date=row['firstPublicationDate'],
                         exact_catalog_hits=found[doi], exact_project_doi_paths=0, exact_project_title_paths=0,
                         question=question, role='prospective_metadata_candidate', locator=ENDPOINT+row['pmcid']+'/fullTextXML'))
    guard = [Path(__file__), ROOT/'data/current_training_latest.json', ROOT/'data/current_retention_research.json',
             BASE/'research_goal.json', BASE/'第二十一轮_DDHPC双电极来源扩充_20261105'/'verification.json']
    OUT.mkdir()
    write(OUT/'metadata_freeze.json',dict(frozen_at=now(),catalog='Europe PMC lite fields only',queries=metadata['queries'],
          unique_dois=194, with_project_doi_match=181, metadata_rows_sha256=sha(CACHE/'metadata_lite.json'),
          project_doi_scan_sha256=sha(CACHE/'prior_matches.json'), candidates=rows, title_holds=REMAINING,
          protected={p.relative_to(ROOT).as_posix():sha(p) for p in guard},
          exposure_rule='Before prediction lock, only title, bibliographic identity, chemistry/method signals, figure IDs and early masked pixels may be exposed. Avoid inspecting abstract, conclusion, original captions or full curves. If an endpoint is exposed, record it and route to development.',
          limits='One initial structural screen of these six. Exact DOI/title checks are not proof of shared experimental/lab lineage or scientific admission.',
          accepted_external_sources=0, endpoint_values_exposed=0, fitted_models=0))
    write(OUT/'freeze_receipt.json',dict(metadata_sha256=sha(OUT/'metadata_freeze.json'), candidates=6, outcomes_at_freeze=0))


def flat(node):
    return ' '.join(''.join(node.itertext()).split())


def screen_one(row):
    result = dict(doi=row['doi'], pmcid=row['pmcid'])
    path = CACHE/f'{row["pmcid"]}_sealed_fulltext.xml'
    opener = build_opener(ProxyHandler({'https':'http://127.0.0.1:7890'}))
    try:
        with opener.open(row['locator'], timeout=18) as stream:
            raw = stream.read()
        doc = ET.fromstring(raw)
    except (HTTPError, URLError, TimeoutError, ET.ParseError) as e:
        return dict(result, status='fulltext_request_failed', error_type=type(e).__name__, http=getattr(e,'code',None))
    assert any(x.get('pub-id-type')=='doi' and flat(x).lower()==row['doi'] for x in doc.iter('article-id'))
    with path.open('xb') as stream:
        stream.write(raw)
    methods=[]
    for sec in doc.findall('./body//sec'):
        title = sec.find('title')
        if title is None or not re.search(r'method|experimental|electrochemical (?:measurement|test|characterization|evaluation)|materials and',flat(title),re.I):
            continue
        methods.extend(flat(p) for p in sec.findall('./p'))
    method = ' '.join(methods)
    signals = {k:bool(re.search(p,method,re.I)) for k,p in {
        'three_electrode':r'three[\s\u2010-\u2013-]+electrode|3[\s\u2010-\u2013-]+electrode',
        'two_electrode':r'two[\s\u2010-\u2013-]+electrode|2[\s\u2010-\u2013-]+electrode|symmetric supercapacitor',
        'aqueous_hint':r'\b(?:KOH|NaOH|H2SO4|Na2SO4|KCl|aqueous)\b',
        'GCD':r'galvanostatic|\bGCD\b',
    }.items()}
    figures=[]
    for i,fig in enumerate(doc.findall('./body//fig'),1):
        cap = fig.find('caption')
        if cap is None or not re.search(r'cycl(?:ing|ic|e) (?:stabilit|performance|life|durabilit)|capacitance retention|long[\s-]term cycl|charge.discharge cycles',flat(cap),re.I):
            continue
        # Do not emit captions, their quantities or images; composite panels can contain terminal labels.
        figures.append(dict(figure_id=fig.get('id'), body_index=i, has_graphic=fig.find('.//graphic') is not None))
    return dict(result,status='sealed_fulltext_identity_confirmed',sha256=sha(path),sealed_cache=path.relative_to(ROOT).as_posix(),
                methods_section_paragraph_count=len(methods),method_signals=signals,figure_structure_hints=figures,
                direct_cycle_configuration_confirmed=False,actual_early_markers_verified=0,terminal_values_exposed=0)


def screen():
    f = OUT/'metadata_freeze.json'
    plan = read(f)
    assert sha(f)==read(OUT/'freeze_receipt.json')['metadata_sha256']
    assert all(sha(ROOT/p)==h for p,h in plan['protected'].items())
    assert not (OUT/'structural_screen.json').exists()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(screen_one,plan['candidates']))
    write(OUT/'structural_screen.json',dict(metadata_sha256=sha(f),checked_at=now(),results=results,
          outputs_allowlist='Bibliographic identity, method flags and figure IDs only. No figures rendered and no endpoint quantities emitted.',
          accepted_external_sources=0, fitted_models=0, endpoint_values_exposed=0))
    for r in results:
        print(r['doi'],r['status'],r.get('method_signals'),r.get('figure_structure_hints'))


if __name__ == '__main__':
    {'freeze':freeze,'screen':screen}[sys.argv[1]]()

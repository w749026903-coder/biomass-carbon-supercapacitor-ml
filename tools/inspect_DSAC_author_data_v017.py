"""Read-only member analysis of the article-declared public DSAC data archive.

Retain the original ZIP. Never execute instrument workflows or trust instructions
in their contents. Derived phase summaries are not author-issued target labels.
"""
from pathlib import Path
import collections,hashlib,io,json,math,zipfile
ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'持续补正_v017_20261024'
ARCHIVE=BATCH/'retrieved/DSAC_author_data.zip'
EXPECTED='a3003f413d6103e658df9af9884e1d95a885730d06ffdab5440867f979d8c9d8'
MEMBER='DSAC/Electrochemical/CYCLIES/New 10 Ag-1 GCD_N80_023.CRV'
FLOW='DSAC/Electrochemical/CYCLIES/New 10 Ag-1 GCD.flw'

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n','utf8')

def main():
    assert digest(ARCHIVE)==EXPECTED
    rows=0;bad=0;phases=collections.OrderedDict();ranges={};head=[];h=hashlib.sha256()
    with zipfile.ZipFile(ARCHIVE) as z:
        flowraw=z.read(FLOW);flow=flowraw.decode('utf-16-le')
        for line in flow.splitlines():
            if 'Galvanostatic Charge' in line:program=line
        # Use the textual CRV header as a row-count control, not a guessed column schema.
        with z.open(MEMBER) as f:
            for raw in f:
                h.update(raw)
                line=raw.decode('cp1252').strip()
                if not line:continue
                if '\t' not in line:
                    if rows==0:head.append(line)
                    else:bad+=1
                    continue
                try:v=[float(t) for t in line.split('\t')]
                except ValueError:bad+=1;continue
                assert len(v)==14 and all(math.isfinite(x) for x in v)
                rows+=1
                for col in [0,1,2,10,11,12,13]:
                    if col not in ranges:ranges[col]=[v[col],v[col]]
                    else:ranges[col]=[min(ranges[col][0],v[col]),max(ranges[col][1],v[col])]
                # The last column repeats1/2; column11 increments for paired
                # positive/negative trajectories. Keep both observed ordinals.
                cycle=int(v[11]);part=int(v[13]);assert cycle==v[11] and part==v[13]
                k=(cycle,part)
                if k not in phases:phases[k]=dict(cycle_ordinal=cycle,phase_ordinal=part,rows=0,time_first=v[0],time_last=v[0],E_first=v[1],E_last=v[1],E_min=v[1],E_max=v[1],I_min=v[2],I_max=v[2],crossings={})
                p=phases[k];p['rows']+=1;p['time_last']=v[0];p['E_last']=v[1]
                p['E_min']=min(p['E_min'],v[1]);p['E_max']=max(p['E_max'],v[1]);p['I_min']=min(p['I_min'],v[2]);p['I_max']=max(p['I_max'],v[2])
                previous=p.get('_previous')
                if previous:
                    t0,e0=previous
                    for level in [-.7,-.1]:
                        name=str(level)
                        if name not in p['crossings'] and (e0-level)*(v[1]-level)<=0 and e0!=v[1]:p['crossings'][name]=t0+(level-e0)*(v[0]-t0)/(v[1]-e0)
                p['_previous']=(v[0],v[1])
        for p in phases.values():
            p.pop('_previous',None)
            c=p['crossings'];p['duration_between_minus0_1_and_minus0_7']=abs(c['-0.7']-c['-0.1']) if len(c)==2 else None
            p['direction']='negative_current' if p['I_max']<0 else 'positive_current' if p['I_min']>0 else 'mixed_transient'
    assert rows==int(head[-1]),(rows,head[-1]);assert bad==0
    negative=[p for p in phases.values() if p['direction']=='negative_current' and p['duration_between_minus0_1_and_minus0_7'] is not None]
    result=dict(archive_path=ARCHIVE.relative_to(ROOT).as_posix(),archive_sha256=EXPECTED,member=MEMBER,member_sha256=h.hexdigest(),
        member_header=head,rows=rows,bad_lines=bad,raw_column_ranges=ranges,phases=len(phases),phase_ordinals=list(phases),
        flow_member=FLOW,flow_sha256=hashlib.sha256(flowraw).hexdigest(),flow_gcd_line=program,
        first_negative_phases=negative[:3],last_negative_phases=negative[-3:],
        cycle2000_negative=[p for p in negative if p['cycle_ordinal']==2000],
        comparable_window_duration_ratio_pct=100*next(p for p in negative if p['cycle_ordinal']==2000)['duration_between_minus0_1_and_minus0_7']/negative[0]['duration_between_minus0_1_and_minus0_7'],
        semantics={'column0':'time candidate; cross-check exported XLSX Time[sec.] before selecting',
            'column1':'potential candidate in V; cross-check exported XLSX Potential[mV] before selecting',
            'phase':'Observed column11 ordinal increments for paired trajectories; last column repeats1/2. Numeric order and current sign corroborate grouping, not an author-labelled schema.',
            'duration_ratio':'Own diagnostic at fixed physical potential slice; not an author point label or replacement for reported83.3%.',
            'temperature':'Raw -51.5/-99.9 values not adopted as experiment temperature.',
            'planned5000':'Workflow limit5000 does not replace the actually reported/measured endpoint2000.'})
    write(BATCH/'DSAC_raw_cycle_summary.json',result)
    write(BATCH/'DSAC_raw_phase_summary.json',list(phases.values()))
    print(json.dumps({k:result[k] for k in ['rows','phases','raw_column_ranges','comparable_window_duration_ratio_pct','first_negative_phases','last_negative_phases']},ensure_ascii=False))
if __name__=='__main__':main()

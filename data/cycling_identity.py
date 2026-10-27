"""Versioned canonical identity lookup without modifying historical grouping code."""
from data.literature_groups import normalize_doi

def cycling_endpoints_by_doi(rows):
    """Canonical lookup only; preserve every original row and reject identity dissent."""
    import re
    grouped={};unresolved=[]
    for row in rows:
        identities=set()
        for field in ['doi','identity_key','source_group']:
            raw=row.get(field)
            if not isinstance(raw,str)or not raw.strip():continue
            value=normalize_doi(raw)
            if re.fullmatch(r'10\.\d{4,9}/\S+',value):identities.add(value)
        if len(identities)>1:raise ValueError('Conflicting DOI fields for '+row['endpoint_id'])
        if not identities:unresolved.append(row['endpoint_id']);continue
        key=next(iter(identities));grouped.setdefault(key,[]).append(row)
    return dict(by_doi=grouped,unresolved_endpoint_ids=sorted(unresolved),semantics='Identity candidates only; sameDOI does not establish same test, approval or independence')


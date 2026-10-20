"""Read-only, page-addressed inspection of an intake SQLite batch."""
from pathlib import Path
import argparse,json,re,sqlite3


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--batch',type=Path,required=True)
    ap.add_argument('--ids',nargs='+',required=True)
    ap.add_argument('--query',default=r'cycling stability|cyclic stability|capacitance retention|retained?\s+\d|\d[\d, ]{2,}\s*(?:charge.discharge\s*)?cycles')
    ap.add_argument('--context',type=int,default=350)
    ap.add_argument('--limit',type=int,default=8)
    ap.add_argument('--pages',nargs='*',type=int)
    ap.add_argument('--min-page',type=int,default=1)
    a=ap.parse_args()
    db=sqlite3.connect((a.batch/'batch.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    index={r['document_id']:r for r in json.loads((a.batch/'intake_index.json').read_text(encoding='utf-8'))}
    for raw in a.ids:
        ident=raw if raw.startswith('ADD_') else f'ADD_{int(raw):03}'
        r=index[ident]
        print('\nDOCUMENT',ident,r['input_locations'][0]['filename'],'DOI',r['first_page_dois'])
        count=0
        for page,text in db.execute('select page_number,text from pages where document_id=? and page_number>=? order by page_number',(ident,a.min_page)):
            if a.pages is not None:
                if page in a.pages:print('PAGE',page,text)
                continue
            text=' '.join(text.split())
            last=-10000
            for hit in re.finditer(a.query,text,re.I):
                if hit.start()-last<a.context:continue
                print('p'+str(page),text[max(0,hit.start()-a.context):hit.end()+a.context])
                last=hit.start();count+=1
                if count>=a.limit:break
            if count>=a.limit:break
    db.close()


if __name__=='__main__':main()

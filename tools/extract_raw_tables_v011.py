"""Index original tables as UNREVIEWED candidates, never training observations.

JATS/Word rows retain raw cells/spans; PDF layout detection is explicitly tentative.
Duplicate PDF forms with primary XML tables are marked, not counted as new papers.
"""
from pathlib import Path
import collections, hashlib, io, json, re, sqlite3, zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '全库复检与特征补提取_20261021'


def clean(element):
    return ' '.join(''.join(element.itertext()).split())


def local(tag):
    return tag.split('}')[-1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def xml_tables(payload):
    root = ET.fromstring(payload)
    result = []
    for n, table in enumerate([e for e in root.iter() if local(e.tag) == 'table-wrap'], 1):
        caption = next((clean(e) for e in list(table) if local(e.tag) == 'caption'), '')
        rows = []
        for tr in table.iter():
            if local(tr.tag) != 'tr':
                continue
            cells = [{'text':clean(td),'tag':local(td.tag),'colspan':td.get('colspan','1'),'rowspan':td.get('rowspan','1')} for td in list(tr) if local(td.tag) in ['th','td']]
            if cells:
                rows.append(cells)
        if rows:
            result.append(('XML table-wrap ' + (table.get('id') or str(n)), caption, rows, 'native_XML_cells'))
    return result


def word_tables(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    result = []
    for n, table in enumerate([e for e in root.iter() if local(e.tag)=='tbl'],1):
        rows = []
        for tr in list(table):
            if local(tr.tag)!='tr':continue
            cells=[{'text':clean(tc),'tag':'word_tc','colspan':'unknown_raw','rowspan':'unknown_raw'} for tc in list(tr) if local(tc.tag)=='tc']
            if cells:rows.append(cells)
        if rows:result.append(('DOCX table'+str(n),'Original Word table; inspect surrounding document for caption/units',rows,'native_Word_cells'))
    return result


class NativeHTMLTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.result=[];self.counter=0;self.hidden=0

    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.hidden+=1
        if tag=='table':
            self.counter+=1
            self.stack.append({'id':dict(attrs).get('id',str(self.counter)),'rows':[],'row':None,'cell':None,'caption':[],'in_caption':False})
        if not self.stack:return
        item=self.stack[-1]
        if tag=='caption':item['in_caption']=True
        elif tag=='tr':item['row']=[]
        elif tag in ['td','th']:
            a=dict(attrs);item['cell']={'text':'','tag':tag,'colspan':a.get('colspan','1'),'rowspan':a.get('rowspan','1')}

    def handle_data(self,data):
        if not self.stack or self.hidden:return
        item=self.stack[-1]
        if item['in_caption']:item['caption'].append(data)
        elif item['cell'] is not None:item['cell']['text']+=data

    def handle_endtag(self,tag):
        if tag in ['script','style']:self.hidden=max(0,self.hidden-1)
        if not self.stack:return
        item=self.stack[-1]
        if tag in ['td','th'] and item['cell'] is not None:
            item['cell']['text']=' '.join(item['cell']['text'].split())
            if item['row'] is not None:item['row'].append(item['cell'])
            item['cell']=None
        elif tag=='tr' and item['row'] is not None:
            if item['row']:item['rows'].append(item['row'])
            item['row']=None
        elif tag=='caption':item['in_caption']=False
        elif tag=='table':
            self.stack.pop();rows=item['rows']
            if len(rows)>=2 and max(map(len,rows),default=0)>=2 and sum(bool(re.search(r'\d',cell['text'])) for row in rows for cell in row)>=3:
                caption=' '.join(' '.join(item['caption']).split()) or 'Native HTML table; inspect surrounding article caption/units'
                self.result.append(('HTML table id='+item['id'],caption,rows,'native_HTML_cells_requires_context_binding'))


def pdf_tables(path_or_bytes):
    import pdfplumber
    result=[]
    with pdfplumber.open(io.BytesIO(path_or_bytes) if isinstance(path_or_bytes,bytes) else path_or_bytes) as pdf:
        for n,page in enumerate(pdf.pages,1):
            text=page.extract_text() or ''
            captions=re.findall(r'(?:Table|TABLE)\s+[S\d][^\n]{0,170}',text)
            if not captions:
                page.close();continue
            tables=page.find_tables()
            if not tables:
                tables=page.find_tables({'vertical_strategy':'text','horizontal_strategy':'lines','min_words_vertical':2})
            for k,table in enumerate(tables,1):
                data=table.extract()
                if len(data)<2 or max(map(len,data),default=0)<2:
                    continue
                numeric=sum(bool(re.search(r'\d',str(cell or ''))) for row in data for cell in row)
                if numeric<3:continue
                cells=[[{'text':str(cell or ''),'tag':'pdf_layout_cell','colspan':'unresolved','rowspan':'unresolved'} for cell in row] for row in data]
                loc='PDF p'+str(n)+' table_candidate'+str(k)+' bbox='+json.dumps([round(x,2) for x in table.bbox])
                result.append((loc,' | '.join(captions),cells,'automatic_PDF_layout_requires_visual_binding'))
            page.close()
    return result


def main():
    index=OUT/'full_corpus_search_native.sqlite'
    c=sqlite3.connect(index);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
    if (ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021/merge_manifest.json').exists():
        raise FileExistsError('Never change a sealed search index.')
    c.executescript('''
    create table if not exists raw_tables_v11(table_id text primary key,source_sha256 text references sources(sha256),locator text,caption text,parser_kind text,table_role text,status text check(status='automatic_unreviewed'),training_eligible integer check(training_eligible=0));
    create table if not exists raw_table_rows_v11(row_id integer primary key,table_id text references raw_tables_v11,row_ordinal integer,cells_json text,row_text text,unique(table_id,row_ordinal));
    create table if not exists raw_table_scans_v11(source_sha256 text primary key references sources(sha256),format text,status text,table_count integer,error text);
    create table if not exists raw_archive_members_v11(archive_sha256 text references sources(sha256),member_sha256 text,member_name text,status text,primary key(archive_sha256,member_name));
    create virtual table if not exists raw_table_search_v11 using fts5(row_text,content='raw_table_rows_v11',content_rowid='row_id');
    ''')
    sources=[dict(s) for s in c.execute("select * from sources where format in('xml','pdf','docx','zip','html','htm') order by case format when 'xml' then 0 when 'docx' then 1 when 'pdf' then 2 else 3 end,sha256")]
    all_sha={s['sha256'] for s in sources}
    xml_table_dois={r[0] for r in c.execute("select distinct i.identity_key from identity_sources i join raw_table_scans_v11 r on i.sha256=r.source_sha256 where r.format='xml' and r.table_count>0")}
    for n,s in enumerate(sources,1):
        if c.execute('select 1 from raw_table_scans_v11 where source_sha256=?',(s['sha256'],)).fetchone():continue
        p=Path(s['path']) if s['path'] else None
        tables=[];status='complete';error=None
        try:
            if not p or not p.is_file():raise FileNotFoundError('Original not locally accessible; inherited text remains searchable')
            if sha(p)!=s['sha256']:raise ValueError('Original fingerprint changed')
            if s['format']=='xml':tables=xml_tables(p.read_bytes())
            elif s['format']=='docx':tables=word_tables(p.read_bytes())
            elif s['format'] in ['html','htm']:
                parser=NativeHTMLTables();parser.feed(p.read_text('utf-8-sig',errors='replace'));tables=parser.result
            elif s['format']=='pdf':
                identities={r[0] for r in c.execute('select identity_key from identity_sources where sha256=?',(s['sha256'],))}
                is_main=bool(c.execute("select 1 from identity_sources where sha256=? and role in('main','main_XML_metadata')",(s['sha256'],)).fetchone())
                if is_main and identities & xml_table_dois:
                    status='duplicate_main_format_primary_XML_tables_indexed_native_text_also_searched'
                else:tables=pdf_tables(p)
            else:
                with zipfile.ZipFile(p) as archive:
                    for member in archive.infolist():
                        ext=Path(member.filename).suffix.lower()
                        if member.is_dir() or ext not in ['.pdf','.docx','.xml']:continue
                        if member.file_size>64*1024*1024:
                            c.execute('insert or ignore into raw_archive_members_v11 values(?,?,?,?)',(s['sha256'],'',member.filename,'over64MiB_manual_followup'));continue
                        payload=archive.read(member);fingerprint=hashlib.sha256(payload).hexdigest()
                        if fingerprint in all_sha:
                            state='same_content_indexed_as_direct_source'
                        else:
                            state='native_member_tables_scanned'
                            found=xml_tables(payload) if ext=='.xml' else word_tables(payload) if ext=='.docx' else pdf_tables(payload)
                            tables.extend([('ZIP '+member.filename+' SHA256='+fingerprint+' / '+loc,caption,rows,parser) for loc,caption,rows,parser in found])
                        c.execute('insert or ignore into raw_archive_members_v11 values(?,?,?,?)',(s['sha256'],fingerprint,member.filename,state))
            for loc,caption,rows,parser in tables:
                table_id=hashlib.sha256((s['sha256']+'\n'+loc).encode()).hexdigest()[:24]
                role='comparison_or_summary_candidate' if re.search(r'comparison|previous|literature|summary',caption,re.I) else 'own_or_context_not_yet_bound'
                c.execute('insert or ignore into raw_tables_v11 values(?,?,?,?,?,?,?,?)',(table_id,s['sha256'],loc,caption,parser,role,'automatic_unreviewed',0))
                for i,row in enumerate(rows):
                    c.execute('insert or ignore into raw_table_rows_v11(table_id,row_ordinal,cells_json,row_text) values(?,?,?,?)',(table_id,i,json.dumps(row,ensure_ascii=False),' | '.join(cell['text'] for cell in row)))
            if s['format']=='xml' and tables:
                xml_table_dois.update(r[0] for r in c.execute('select identity_key from identity_sources where sha256=?',(s['sha256'],)))
        except Exception as exc:
            status='table_parse_unresolved';error=type(exc).__name__+':'+str(exc)[:350]
        c.execute('insert into raw_table_scans_v11 values(?,?,?,?,?)',(s['sha256'],s['format'],status,len(tables),error));c.commit()
        progress={'phase':'raw_table_candidate_index','completed_source_files':n,'total_source_files':len(sources),'automatic_admissions':0,'model_fits':0}
        (OUT/'table_progress.json').write_text(json.dumps(progress,ensure_ascii=False),'utf-8')
        if n%10==0:print(json.dumps(progress),flush=True)
    c.execute("insert into raw_table_search_v11(raw_table_search_v11) values('rebuild')");c.commit()
    result={'source_states':[dict(r) for r in c.execute('select format,status,count(*) as sources,sum(table_count) as tables from raw_table_scans_v11 group by format,status')],
            'unreviewed_table_candidates':c.execute('select count(*) from raw_tables_v11').fetchone()[0],
            'raw_table_rows':c.execute('select count(*) from raw_table_rows_v11').fetchone()[0],
            'scientific_admissions':0,'model_fits':0,'warning':'Raw native cells/layout candidates, not verified independent tests; original units and review status retained.'}
    assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
    assert not c.execute('pragma foreign_key_check').fetchall()
    (OUT/'raw_table_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8');c.close()
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()

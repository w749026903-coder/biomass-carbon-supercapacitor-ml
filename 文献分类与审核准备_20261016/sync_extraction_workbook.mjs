import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const dir=path.dirname(fileURLToPath(import.meta.url));
const audit=path.join(dir,'..','文献完整解压与统一管理_20261016');
const file=path.join(dir,'文献分类总表.xlsx');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const extras=wb.worksheets.getItem('额外资料65');
const before=process.argv[2]==='preview';
if(before){
  console.log((await wb.inspect({kind:'table',range:'额外资料65!A4:F4',include:'values,formulas',maxChars:1000})).ndjson);
}else{
  const data=JSON.parse(await fs.readFile(path.join(dir,'工作簿数据.json'),'utf8'));
  const rows=extras.getRange('A9:A73').values;
  const byId=new Map(data.extras.map(x=>[x.id,x]));
  let changed=0;
  for(let i=0;i<rows.length;i++){
    const item=byId.get(rows[i][0]);
    if(!item)throw new Error('Unknown extra record '+rows[i][0]);
    const row=i+9;
    const current=extras.getRange(`N${row}`).values[0][0];
    if(current!==item.local_pdf){
      extras.getRange(`N${row}`).values=[[item.local_pdf]];
      extras.getRange(`D${row}`).values=[[item.fulltext_status]];
      changed++;
    }
  }
  if(changed!==28)throw new Error('Expected 28 changed extra records, got '+changed);
  extras.getRange('D4').values=[[data.extras.filter(x=>!x.local_pdf).length]];
  wb.recalculate();
  const totals=await wb.inspect({kind:'table',range:'主清单120!A4:F4',include:'values,formulas',tableMaxRows:1,tableMaxCols:6,maxChars:1500});
  const remaining=await wb.inspect({kind:'table',range:'额外资料65!A4:F4',include:'values,formulas',tableMaxRows:1,tableMaxCols:6,maxChars:1500});
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:1500});
  await fs.writeFile(path.join(audit,'工作簿检查.ndjson'),[totals.ndjson,remaining.ndjson,errors.ndjson].join('\n'));
  console.log(totals.ndjson);console.log(remaining.ndjson);console.log(errors.ndjson);
  const output=await SpreadsheetFile.exportXlsx(wb);
  await output.save(file);
  console.log('UPDATED 28 local paths, 28 statuses, ZIP-only count=0');
}
for(const [range,label] of [['A1:F13','汇总'],['L44:P48','路径']]){
  const blob=await wb.render({sheetName:'额外资料65',range,scale:1.1,format:'png'});
  await fs.writeFile(path.join(audit,`工作簿_${before?'更新前':'更新后'}_${label}.png`),new Uint8Array(await blob.arrayBuffer()));
}

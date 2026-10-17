import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const cat=path.dirname(fileURLToPath(import.meta.url)),root=path.join(cat,'..');
const out=path.join(root,'文献整理_20261017');
const plan=JSON.parse(await fs.readFile(path.join(out,'整理计划.json'),'utf8'));
const replacements=[];
for(const [old,next] of Object.entries(plan.old_to_new_paths)){
  replacements.push([old,next],[old.replaceAll('\\','/'),next.replaceAll('\\','/')]);
}
replacements.sort((a,b)=>b[0].length-a[0].length);
const translate=text=>{for(const [old,next] of replacements)text=text.replaceAll(old,()=>next);return text;};
const canonical=new Map(JSON.parse(await fs.readFile(path.join(out,'当前唯一文献位置.json'),'utf8')).map(x=>[x.id,x.local_pdf]));
const edit=process.argv[2]==='edit';
const files=[
  {file:path.join(cat,'文献分类总表.xlsx'),views:[['主清单120','L8:P11','分类路径']],sheets:['主清单120','额外资料65','问题登记']},
  {file:path.join(root,'训练适用性审核_20261016','训练用途审核总表.xlsx'),views:[['训练用途122','G9:J12','训练路径']],sheets:['训练用途122']}
];
const report=[];
for(const spec of files){
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(spec.file));
  let changed=0;
  if(edit){
    for(const name of spec.sheets){
      const s=wb.worksheets.getItem(name),used=s.getUsedRange(),matrix=used.values;
      for(let r=0;r<matrix.length;r++)for(let c=0;c<matrix[r].length;c++){
        const value=matrix[r][c];if(typeof value!=='string')continue;
        const next=translate(value);
        if(next!==value){used.getCell(r,c).values=[[next]];changed++;}
      }
    }
    for(const [name,first,last,col] of spec.sheets.length===3?
       [['主清单120',9,128,'N'],['额外资料65',9,73,'N']]:[['训练用途122',10,131,'I']]){
      const s=wb.worksheets.getItem(name),ids=s.getRange(`A${first}:A${last}`).values;
      for(let i=0;i<ids.length;i++){
        const exact=canonical.get(ids[i][0]);if(!exact)continue;
        const cell=s.getRange(`${col}${first+i}`);
        if(cell.values[0][0]!==exact){cell.values=[[exact]];changed++;}
      }
    }
    if(spec.sheets.length===3){
      wb.worksheets.getItem('额外资料65').getRange('A6').values=[['65份为历史已审内容，其中1份2022年版本已移出当前文献库；分类与冻结状态不变。']];
    }else{
      const s=wb.worksheets.getItem('训练用途122');
      s.getRange('A8').values=[['2026-10-17：当前文献库121篇，另1份2022年版本已移出归档；122份为历史审核范围。']];
      s.getRange('J131').values=[['年份排除，已移出文献库']];
    }
    wb.recalculate();
    const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:1200});
    const output=await SpreadsheetFile.exportXlsx(wb);await output.save(spec.file);
    report.push({file:spec.file,changedPathCells:changed,errors:errors.ndjson});
  }
  for(const [sheetName,range,label] of spec.views){
    const blob=await wb.render({sheetName,range,scale:1.1,format:'png'});
    await fs.writeFile(path.join(out,`${edit?'整理后':'整理前'}_${label}.png`),new Uint8Array(await blob.arrayBuffer()));
  }
}
if(edit){await fs.writeFile(path.join(out,'工作簿路径更新核验.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));}
else console.log('Rendered pre-edit views');

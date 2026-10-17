import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const dir=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(dir,'工作簿数据.json'),'utf8'));
const wb=Workbook.create();
const navy='#273A4C',gray='#5A6672',amber='#FFF2D6',red='#FCE6E3';

function sheetBase(name, title, cols, rows, widths, tableName) {
  const s=wb.worksheets.add(name);s.showGridLines=false;
  const end=String.fromCharCode(64+cols.length),last=8+rows.length;
  const all=s.getRange(`A1:${end}${last}`);
  all.format.font={name:'Arial',size:10.5,color:'#24303A'};
  all.format.verticalAlignment='center';
  s.getRange('A2').values=[[title]];
  s.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:navy};
  s.getRange(`A3:${end}3`).format.borders={bottom:{style:'thin',color:'#AAB7C0'}};
  s.getRange(`A8:${end}8`).values=[cols];
  if(rows.length)s.getRange(`A9:${end}${last}`).values=rows;
  const table=s.tables.add(`A8:${end}${last}`,true,tableName);table.showFilterButton=true;
  s.getRange(`A8:${end}8`).format={fill:navy,font:{name:'Arial',size:10.5,bold:true,color:'#FFFFFF'},rowHeight:32,wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};
  s.getRange(`A9:${end}${last}`).format.rowHeight=78;
  s.getRange(`A9:${end}${last}`).format.wrapText=true;
  for(let i=0;i<widths.length;i++)s.getRangeByIndexes(0,i,last,1).format.columnWidth=widths[i];
  s.freezePanes.freezeRows(8);s.freezePanes.freezeColumns(2);
  s.getRange('A1').format.rowHeight=10;
  return s;
}

const headers=['编号','年份','分类','全文状态','题名','准入状态','材料分层','DOI','测试体系线索','指标定位线索','补充材料','分类依据','具体问题或阅读用途','原文位置','PDF页数','版本'];
const mapRow=x=>[x.id,x.year??null,x.shelf.substring(3),x.fulltext_status,x.title,x.quality_gate,x.material_family,x.doi??'',x.electrode_hint,x.metric_hint,x.supplement_status,x.basis,x.note,x.local_pdf??(x.archive_entry?'D:/文献/1.zip 内 '+x.archive_entry:''),x.pages??null,x.version];
const widths=[9,8,25,15,78,30,42,36,36,42,28,28,75,75,10,35];
const main=sheetBase('主清单120','生物质衍生碳文献分类',headers,data.main.map(mapRow),widths,'MainCatalog');
main.getRange('A4:F4').values=[['候选篇数',120,'已取得全文',57,'待补全文',63]];
main.getRange('B4').formulas=[['=COUNTA(A9:A128)']];
main.getRange('D4').formulas=[['=COUNTIFS(D9:D128,"已取得全文")']];
main.getRange('F4').formulas=[['=COUNTIFS(D9:D128,"待补全文")']];
main.getRange('B4:F4').format.rowHeight=26;
main.getRange('B4').format.font={bold:true,color:navy,size:14};
main.getRange('D4').format.font={bold:true,color:navy,size:14};
main.getRange('F4').format.font={bold:true,color:navy,size:14};
main.getRange('A6').values=[['范围：2023年至今。分类用于安排阅读，实验数据尚未通过逐条审核。']];
main.getRange('A6').format.font={italic:true,color:gray,size:10};
main.getRange('D9:D128').conditionalFormats.addCustom('$D9="待补全文"',{fill:amber});
main.getRange('F9:F128').conditionalFormats.addCustom('$A9="R088"',{fill:red,font:{bold:true,color:'#9C2C24'}});
main.getRange('B9:B128').setNumberFormat('0');main.getRange('O9:O128').setNumberFormat('0');

const extra=sheetBase('额外资料65','清单外资料与版本核对',headers,data.extras.map(mapRow),widths,'ExtraDocuments');
extra.getRange('A4:F4').values=[['按PDF内容去重',data.extras.length,'仅在压缩包',data.extras.filter(x=>!x.local_pdf).length,'不自动并入主清单','']];
extra.getRange('A6').values=[['范围外、待核和冻结资料仍保留出处。缺年份表示未核实，不能按0年处理。']];
extra.getRange('A6').format.font={italic:true,color:gray,size:10};
extra.getRange('F9:F73').conditionalFormats.addCustom('OR(ISNUMBER(SEARCH("冻结",$F9)),ISNUMBER(SEARCH("早于2023",$F9)))',{fill:red,font:{color:'#9C2C24'}});
extra.getRange('B9:B73').setNumberFormat('0');extra.getRange('O9:O73').setNumberFormat('0');

const issues=sheetBase('问题登记','需要先核实的来源与字段',
 ['问题号','论文或来源','问题类型','已定位证据','处理方式'],
 data.issues.map(x=>[x.issue_id,x.paper_id,x.topic,x.evidence,x.action]),[10,38,26,98,90],'IssueRegister');
issues.getRange('A4:D4').values=[['已登记问题',data.issues.length,'本轮实验数据准入',0]];
issues.getRange('A6').values=[['疑点保留证据并暂停相关数据使用，不根据高低性能或模型分数删记录。']];
issues.getRange('A6').format.font={italic:true,color:gray,size:10};
issues.getRange(`A9:E${8+data.issues.length}`).format.rowHeight=85;

wb.recalculate();
const inspected=await wb.inspect({kind:'table',range:'主清单120!A4:F4',include:'values,formulas',tableMaxRows:1,tableMaxCols:6,maxChars:2200});
console.log(inspected.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:30},maxChars:1200});
await fs.writeFile(path.join(dir,'工作簿公式检查.ndjson'),errors.ndjson??'','utf8');
for(const [name,range,out] of [['额外资料65','A1:F13','工作簿预览_额外资料.png']]) {
  const blob=await wb.render({sheetName:name,range,scale:1.3,format:'png'});
  await fs.writeFile(path.join(dir,out),new Uint8Array(await blob.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(dir,'文献分类总表.xlsx'));
console.log('EXPORTED 文献分类总表.xlsx');

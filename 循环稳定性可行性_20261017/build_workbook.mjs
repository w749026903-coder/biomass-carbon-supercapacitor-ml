import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const base=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(base,'outputs','cycling-feasibility-20261017');
await fs.mkdir(out,{recursive:true});
const rows=JSON.parse(await fs.readFile(path.join(base,'循环稳定性逐记录候选.json'),'utf8'));
const sources=JSON.parse(await fs.readFile(path.join(base,'来源覆盖与缺口.json'),'utf8'));
const stats=JSON.parse(await fs.readFile(path.join(base,'统计摘要.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('概览');
const data=wb.worksheets.add('循环数据');
const coverage=wb.worksheets.add('来源覆盖');
const font='Microsoft YaHei';
const blue='#243E5A', gray='#64748B';
function styleTable(sh,values,widths,name){
  const nr=values.length,nc=values[0].length;
  const grid=sh.getRangeByIndexes(0,0,nr,nc);grid.values=values;
  grid.format.font={name:font,size:10,color:'#172B3A'};
  grid.format.rowHeight=25;grid.format.verticalAlignment='center';
  const hdr=sh.getRangeByIndexes(0,0,1,nc);
  hdr.format={fill:blue,font:{name:font,size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:40,wrapText:true};
  for(let c=0;c<nc;c++)sh.getRangeByIndexes(0,c,nr,1).format.columnWidth=widths[c]??16;
  const table=sh.tables.add(grid,true,name);table.showFilterButton=true;
  sh.freezePanes.freezeRows(1);sh.showGridLines=false;
  return grid;
}
const scopeText={carbon_candidate:'碳材料候选',carbon_control:'纯碳对照',separate_system:'分体系',Zn_hybrid:'锌离子混合器件',
 carbon_metal_residue_pending:'盐/金属残留待核',carbon_originality_pending:'原始样品复用待核',metal_or_polymer_composite:'金属或聚合物复合',
 metal_composite:'金属复合',Ti_composite:'含Ti复合',NiO_composite:'NiO复合',Ni_composite:'含Ni复合',Ni_CNT_composite:'Ni/CNT复合',
 carbon_field_freeze:'原有字段冻结',Fe_composite:'含Fe复合',Sm_composite:'含Sm复合',Ni_Mo_sulfide_composite:'Ni/Mo硫化物复合',
 Fe_involvement_pending:'Fe参与状态待核',RGO_composite:'RGO复合',Fe_ZnO_composite:'Fe/ZnO复合',Li_capacitor_half_cell:'锂半电池'};
const header=['记录ID','论文编号','样品/器件','材料ID（暂定）','循环次数','保持率','数值关系','电极体系','循环方法','电流密度 (A/g)',
 '面积电流 (mA/cm²)','扫速 (mV/s)','电解液','浓度值','浓度单位','电压下限 (V)','电压上限 (V)','BET (m²/g)','总孔体积 (cm³/g)',
 'N (at.%)','O (at.%)','问题待核','材料范围','基本条件配齐','正式准入','来源问题说明','DOI','PDF页序','原文/SI路径'];
const values=[header,...rows.map(r=>[r.record_id,r.paper_id,r.sample,r.material_id,r.cycle_count,r.retention_pct===null?null:r.retention_pct/100,
 r.retention_pct===null?'待核':{eq:'报告点值',approx:'近似',gt:'大于下限'}[r.retention_relation],r.system,r.method,r.current_density_A_g,r.current_density_mA_cm2,
 r.scan_rate_mV_s,r.electrolyte,r.concentration_value,r.concentration_unit,r.voltage_lower_V,r.voltage_upper_V,r.BET_m2_g,
 r.total_pore_volume_cm3_g,r.N_at_pct,r.O_at_pct,r.conflict?'是':'否',scopeText[r.material_scope]??r.material_scope,
 r.provisional_core_conditions?1:0,0,sources.find(s=>s.id===r.paper_id).notes,r.doi,(r.supplement_index?'SI ':'')+r.pdf_pages.join(','),r.evidence_path])];
styleTable(data,values,[17,12,34,40,13,13,15,24,32,18,20,16,23,12,16,17,17,17,22,14,14,13,27,18,14,100,43,18,115],'CyclingCandidates');
data.freezePanes.freezeColumns(2);
data.getRange(`A2:AC${rows.length+1}`).format.rowHeight=42;
data.getRange(`C2:D${rows.length+1}`).format.wrapText=true;
data.getRange(`Z2:AC${rows.length+1}`).format.wrapText=true;
data.getRange(`F2:F${rows.length+1}`).setNumberFormat('0.00%');
for(const col of ['J','K','L','N','P','Q','R','S','T','U'])data.getRange(`${col}2:${col}${rows.length+1}`).setNumberFormat('0.####');
data.getRange(`E2:E${rows.length+1}`).setNumberFormat('#,##0');
const cvals=[['论文编号','原用途类','本轮状态','候选终点行','有数值与次数','暂定材料数','基本条件行','问题与下一步','题名','DOI','原文路径'],
 ...sources.map(s=>[s.id,s.category,s.status,s.endpoint_rows,s.numeric_endpoint_rows,s.provisional_material_keys,s.basic_condition_rows,s.notes,s.title,s.doi,s.path])];
styleTable(coverage,cvals,[12,12,38,16,18,18,16,100,115,42,115],'SourceCoverage');
coverage.freezePanes.freezeColumns(1);
coverage.getRange(`A2:K${sources.length+1}`).format.rowHeight=42;
coverage.getRange(`H2:K${sources.length+1}`).format.wrapText=true;

summary.showGridLines=false;summary.tabColor=blue;
summary.getRange('B2:H2').format.font={name:font,size:15,bold:true,color:blue};
summary.getRange('B2').values=[['循环稳定性数据可行性']];
summary.getRange('B3:H3').format.borders={bottom:{style:'thin',color:blue}};
summary.getRange('B4:H22').format.font={name:font,size:10,color:'#172B3A'};
summary.getRange('B4:H22').format.rowHeight=27;
summary.getRange('B4:D4').values=[['统计口径','本轮数量','说明']];
summary.getRange('B4:D4').format={fill:blue,font:{name:font,size:10,bold:true,color:'#FFFFFF'}};
const metrics=[
 ['当前论文',stats.scanned_current_papers,'按当前唯一文献位置清单'],
 ['实验来源候选论文',stats.original_experiment_candidate_sources,'39篇A类与17篇B类'],
 ['循环候选终点',null,'含待核、短程、CV与分体系条目'],
 ['候选材料编号',stats.extracted_candidates.material_keys,'论文内合并，跨论文独立性未终审'],
 ['明确GCD碳材料候选',stats.carbon_GCD_candidates.endpoint_rows,'20个暂定材料，19篇来源'],
 ['基本条件已配齐',null,'15个暂定材料，15篇来源'],
 ['加BET及电压已配齐',stats.paired_basic_conditions_BET_voltage.endpoint_rows,'8个暂定材料，尚非训练准入'],
 ['再加总孔体积',stats.paired_basic_conditions_BET_totalpore_voltage.endpoint_rows,'4个暂定材料，尚非训练准入'],
 ['正式训练准入',null,'本轮未训练，也未解除原冻结']
];
summary.getRange('B5:D13').values=metrics;
summary.getRange('C7').formulas=[[`=COUNTA('循环数据'!A2:A${rows.length+1})`]];
summary.getRange('C10').formulas=[[`=COUNTIF('循环数据'!X2:X${rows.length+1},1)`]];
summary.getRange('C13').formulas=[[`=SUM('循环数据'!Y2:Y${rows.length+1})`]];
summary.getRange('C5:C13').setNumberFormat('#,##0');
summary.getRange('B15').values=[['结论']];summary.getRange('B15').format.font.bold=true;
summary.getRange('B16').values=[['方向可继续；当前同体系材料量偏小，先补输入与协议，再定向扩充。']];
summary.getRange('B17').values=[['两电极对称GCD：16个终点、14个暂定材料、13篇来源。']];
summary.getRange('B18').values=[['三电极GCD：7个终点、7个暂定材料、7篇来源。']];
summary.getRange('B19').values=[['空白表示尚未配对或未定位，不能直接解释为原文缺失；保持率>100%保留。']];
summary.getRange('B20').values=[['同一材料不同节点共用材料ID。两/三电极、CV/GCD和复合体系分别处理。']];
summary.getRange('B21').values=[['统计为本轮提取快照，输入完整行数是已核录下限，不是整库可获得量上限。']];
summary.getRange('B22').values=[['2026-10-17。本表依据本地原文和SI；121份正文哈希核验，9页原图复核。']];
summary.getRange('A1:A22').format.columnWidth=3;
summary.getRange('B1:B22').format.columnWidth=32;
summary.getRange('C1:C22').format.columnWidth=15;
summary.getRange('D1:D22').format.columnWidth=64;
summary.getRange('E1:H22').format.columnWidth=12;
wb.recalculate();
const inspected=await wb.inspect({kind:'table',range:'概览!B4:D13',include:'values,formulas',tableMaxRows:12,tableMaxCols:3,maxChars:4000});
await fs.writeFile(path.join(base,'工作簿核验.ndjson'),inspected.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
await fs.writeFile(path.join(base,'工作簿错误扫描.ndjson'),errors.ndjson);
for(const [sheetName,range,key] of [['概览','A1:H22','overview'],['循环数据','A1:L9','records'],['来源覆盖','A1:H8','sources']]){
 const preview=await wb.render({sheetName,range,scale:1.4,format:'png'});
 await fs.writeFile(path.join(base,`预览_${key}.png`),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(out,'循环稳定性数据可行性.xlsx'));
console.log(JSON.stringify({output:path.join(out,'循环稳定性数据可行性.xlsx'),records:rows.length,sources:sources.length,summary:inspected.ndjson,errors:errors.ndjson}));

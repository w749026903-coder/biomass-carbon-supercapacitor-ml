from pathlib import Path
import collections, hashlib, json, re, sys
from docx import Document

sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent;CAT=ROOT/'文献分类与审核准备_20261016'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
docs=read(OUT/'正文证据定位.json');byid={x['id']:x for x in docs}
groups={
 'A':('主要实验数据来源候选','R005 R012 R013 R017 R018 R028 R031 R032 R033 R036 R053 R061 R062 R069 R078 R085 R087 R091 R092 R093 R102 R103 R104 R105 R106 R107 R108 R111 R112 R117 SRC005 SRC025 SRC028 SRC035 SRC093 SRC099 SRC112 SRC120 SRC121'),
 'B':('分体系或限定字段使用','R001 R020 R024 R035 R042 R043 R045 R047 R048 R056 R081 R095 R097 R115 SRC101 SRC102 SRC115'),
 'C':('暂缓实验数据使用','R038 R088 SRC022 SRC023 SRC071 SRC073 SRC086 SRC094 SRC100 SRC104 SRC106 SRC107 SRC110 SRC111'),
 'D':('方法与背景参考','R002 R007 R008 R009 R010 R011 R021 R027 R037 R041 R057 SRC018 SRC019 SRC069 SRC070 SRC072 SRC074 SRC077 SRC080 SRC083 SRC085 SRC087 SRC097 SRC118'),
 'E':('当前训练无直接用途','SRC002 SRC026 SRC027 SRC030 SRC032 SRC075 SRC078 SRC081 SRC082 SRC084 SRC088 SRC089 SRC090 SRC091 SRC092 SRC095 SRC096 SRC098 SRC103 SRC105 SRC108 SRC109 SRC114 SRC116 SRC117 SRC119 SRC122'),
 'F':('年份不符，不使用','SRC113')
}
assign={pid:code for code,(_,ids) in groups.items() for pid in ids.split()}
assert set(assign)==set(byid),(set(byid)-set(assign),set(assign)-set(byid))
assert sum(len(x[1].split()) for x in groups.values())==122
# These judgments describe what the actual PDF can contribute. Old-list membership is not an input.
# Tuple: positive evidence/role, restrictions, PDF pages inspected for that decision.
notes={
'R005':('正文有作者新做的4个桃木验证样品PW-400–1/400–3/650–1/650–3，工艺和1 A/g电容能逐项配对。',
         '只把新实验段作为原始数据来源；二手汇总覆盖2021–2025，需逐条追溯后仅保留2023年至今，不整体导入。',[2,3,4,10]),
'R012':('油棕叶水热碳化及KOH比例系列；有孔结构、三电极/器件测试和不同盐浓度对照，本地有19页SI。',
         'mol/kg的m不能写成mol/L的M；CV与GCD电容、LiCl与LiTFSI及不同浓度分别记录，不取摘要数值直接合并。',[3,7,10]),
'R013':('杜仲木活性炭有一步/两步活化与时间系列EUAC1-30至EUAC1-70，能研究工艺影响。',
         '三电极碳电容与锌离子混合器件分开；不能把CV扫速当GCD电流密度。',[3,8,10]),
'R017':('正文有生物质预碳化、KOH比例系列和自身电化学结果，可安排制备—性能配对。',
         '3电极与2电极分别录入；比较表中其他文献不是本篇新样品，部分表征/测试细节在尚未取得的SI。',[3,13,15,16]),
'R018':('甘蔗渣500°C、3/4/5/10 h的C-1至C-4系列，正文给三电极CV随扫速变化的数据。',
         '主要已定位数值基于CV，保留mV/s，不把226.7 F/g误记成1 A/g下的GCD标签；需查活化剂质量比例。',[2,3,4,12,13]),
'R028':('Enhydra fluctuant叶碳有800/900/1000°C系列，正文有电极及对称器件的倍率数据。',
         '关键测试细节在SI；三电极与器件、CV和GCD各自保留分母与条件，不能合并成同一个标签。',[2,5,7]),
'R031':('Cyperus pangorei碳有明确三电极体系，正文同时给CV和GCD条件及电容数值；图5已视觉查看。',
         '25 mV/s与25 A/g都是原文出现的不同测试条件，不能因数值同为476就视为同一条记录或擅改单位；原始电流/活性质量需逐行核定。',[2,4,5,7]),
'R032':('向日葵秸秆ONPC-x温度系列及PC/ONC对照；有三电极和对称器件结果。',
         '制备、表征与测试细节部分在SI；只录本研究样品，不录文献比较条目。',[2,3,6]),
'R033':('芹菜绿叶/黄叶和700/800/900°C系列，正文给样品间电容比较。',
         '制备/表征及部分测试放在SI；高电容不是排除理由，但753 F/g等具体值仍需质量负载、公式与曲线复核。',[2,3]),
'R036':('细菌纤维素/葡萄糖酸钾APC-600/700/800及PC对照，正文有三电极、器件数据。',
         'SI尚缺，电极制备细节不能补猜；52.2 F/g器件值和437 F/g电极值分开。',[2,4,6,7]),
'R053':('姜荷花叶炭PCE活化系列，有两电极、循环/能量性能和自身报告值。',
         '正文存在以1 A描述测试的写法，必须查清绝对电流与质量归一化，不能自动写成1 A/g。',[2,3,9,10]),
'R061':('DSBC-600及DSAC-700/800/900系列；工艺、孔结构和GCD结果能追踪。',
         '先核样品代码与前驱体、质量基准；“No data was used”的数据声明不等于没有正文实验，也不等于原始文件已公开。',[3,8,9]),
'R062':('TPC-650/750/850等温度对照，正文列出572/410/348 F/g等样品配对数据。',
         '正文使用single-electrode口径；不能把单电极换算值当成整器件电容。',[2,4,6,7]),
'R069':('RCS-AC分别在KOH/H2SO4/Na2SO4中测试，适合核电解液因素。',
         '不同电解液的结果仍可能是同一种材料，不能当多个制备样品；三/两电极数据分开，PDF文字重复不得重复导入。',[2,9,11]),
'R078':('芦苇残渣500/600/700/800°C系列，明确碳化、活化、活性物质质量及各样品电化学表现。',
         '碳化温度与后续活化温度是两个步骤；按样品和测试条件关联，不只取最佳样品。',[2,5,6]),
'R085':('NPCA-T-n系列同时改变温度和磷酸脲/纤维素比例，有孔结构和电容记录。',
         'CO2吸附量不当电容标签；温度与比例组合只录实际出现的样品，不展开成未做的全因子实验。',[2,9,10]),
'R087':('AC与氧功能化OFAC的制备和三电极结果可以形成化学处理对照。',
         '92.05与550 F/g等结果应对应同一测试条件核查；引言引用值不作作者新实验。',[3,8,10]),
'R091':('葵花籽壳HPCS温度/活化比例系列，正文有工艺、电极负载及性能数据。',
         'YP50是商业比较材料，不填成葵花籽壳；HPCS单电极与对称器件数据分开，SI仍需补。',[2,8,9]),
'R092':('微藻SPAC、磺化及碘掺杂体系，正文有不同电解液及测试方式的数据。',
         'CV、GCD、EIS推导的电容不混为同一标签；0.06 A/g等原报告条件保留。',[2,3,9,11]),
'R093':('椰糠/膨化米/杏鲍菇三类前驱体和1/2/3 h系列，样品命名及性能有出处。',
         '先核器件电容是否使用单电极折算口径；不把9种制备组合的不同电流点当更多独立材料。',[2,3,12]),
'R102':('DS-700/750/800温度系列，有KOH预处理、CO2物理活化与对称器件结果。',
         'CV与GCD标签分开；KOH溶液浓度不能冒充活化剂/原料质量比。',[3,9,12]),
'R103':('酶解木质素LAC温度/碱比系列，明确列出7个样品代码及电极、器件结果。',
         '测试细节在SI，单/双电极及活化剂比例基准需逐行核定；不是只有最佳LAC800-4能录。',[6,8,9]),
'R104':('向日葵相关生物质SSC系列有多种活化剂/温度条件，并报告均值及离散度。',
         '重复测试的均值±标准差不拆成多个独立制备样品；两种电解液及其口径分别录入。',[2,3,10]),
'R105':('银杏叶GC与不同KHCO3配比GCK系列，正文可关联工艺、孔结构和电容。',
         'GCK-3是样品代码，不直接把3当质量比；方法中2 g原料对应实际活化剂质量，测试细节部分在SI。',[2,4,7,8]),
'R106':('谷子壳FMC/FMCA的未活化/活化对照，正文有三电极和对称器件测试。',
         '未活化碳和活化碳分别建样品；82.94 F/g器件值不混为三电极电容，需核KOH比和质量分母。',[3,4,13,15]),
'R107':('蒜皮酶解/超声系列；本地SI的S1/S3有6种材料孔结构，S2/S4有对应30个电容—电流点。',
         '6种材料不是30种；SI电极口径需与正文三/两电极及Csingle/Ccell公式对应，S7文献比较表不能作为新实验批量导入。',[2,3,8,9]),
'R108':('落叶松再生纤维素CRTW系列有可定位电极/器件电容和循环数据。',
         '面积电流mA/cm²、面积电容F/cm²与质量电容F/g必须各存原口径；关键制备/电化学方法在尚未取得的SI。',[2,8,10]),
'R111':('废竹纤维ACK温度系列，正文有活化处理、孔结构和电极/器件数据。',
         '492 F/g电极与283 F/g器件的计算分母须查；能量密度不能与单电极折算电容直接共用同一公式。',[2,3,8,9]),
'R112':('洋葱花种皮与稻草对照，具有明确碳化/KOH活化和不同体系电容。',
         '200.37 F/g三电极与158 F/g器件等数据分别录入，循环1000次也不当独立材料。',[2,11,12,14]),
'R117':('稻草/桉树ACRS与ACEW在600/700/800°C制备，能对照原料和温度，给水系/离子液器件结果。',
         '水系与离子液、三电极与对称器件分开；首次上线2023与2024卷期不能计成两篇。',[3,4,11,13]),
'SRC005':('香蕉皮/硅胶模板碳：正文有MC-S系列、800°C工艺、3 M KOH和CV/GCD，另有本地SI。',
         '纠正旧“尚未确认有电容测试”的描述；23.14 F/g是CV值，7.91 F/g是0.05 A/g的GCD值，性能低也保留。',[1,3,8,9]),
'SRC025':('椰树壳炭CC及六种钾基活化剂AC1–AC6，对比活化剂与孔结构/电容。',
         'KMnO4用作活化剂不能自动当Mn复合物；p5 EDAX仅报告C/O，仍保留金属残留核查项，不声称证明绝对无Mn。',[3,5,9,11]),
'SRC028':('玉米秸秆/大豆秸秆与熔盐组合NK/ZK/ZN-C/S，正文列样品、工艺和三电极/器件数据。',
         'Zn盐活化后洗涤与残留状态需记录；材料/电极/器件的归一化口径分别核，不因出现盐就自动排除。',[2,3,8,9]),
'SRC035':('桂花碳O-PC-600至900及无活化对照，明确电极负载和电容记录。',
         'ZnCl2/NaCl是制备条件，需核残留而不是直接判为金属复合材料；SI尚缺。',[2,6,8]),
'SRC093':('食品工业三类废物BW1–BW3对应AC1–AC3，正文有700°C、KOH比和半电池/全电池结果。',
         '不同废物组成须从原文对应，不能只填“混合生物质”；0.5 mA/cm²不是0.5 A/g。',[3,12,13]),
'SRC099':('印尼文正式版首页列2026-04-24在线；萝卜叶DLK/DLK-P两类单体炭，正文有两电极CV及109/53.4 F/cm³。',
         '保留体积指标；40个电极圆片不是40种制备材料。Na2SO4浓度和体积/电极基准未核清，不凭密度强换F/g。',[1,2,3,5,6]),
'SRC112':('玉米秸秆CSK-X-Y按活化温度/保温时间命名，给三电极和对称器件数据。',
         '温度与时间两列分别记录，157 F/g单电极与76 F/g器件分开，数据声明为依申请不等于原始数据已到手。',[3,9,11]),
'SRC120':('未熟大蕉皮K7/K8/Z7/Z8按KOH/ZnCl2及700/800°C分组，正文有器件性能。',
         '活化剂字母与温度需保持组合；三电极与Swagelok两电极以及参比写法需分别核定。',[4,15,16]),
'SRC121':('枣核DSAC有明确950°C活化、孔结构及三电极数据，测试条件可定位。',
         '首页明确450 F/g全器件值是estimated；只把原始三电极实验列为候选，推算450 F/g和能量/功率不当实测器件标签。高1800 F/g本身不是删数据理由。',[1,3,8]),
'R001':('除机器学习外有新制蜜瓜皮HDP-AC实验段，可单独审查它是否提供新增原始实验。',
         'S1二手166行继续禁止整体导入；须查新HDP-AC和作者前作是否复用底层样品，及611 F/g的单/双电极分母。',[1,3,4,8,12]),
'R020':('啤酒糟活性炭与NdFeB功能化、正/负电位窗口及对称/非对称器件对照。',
         '含金属功能化体系单列；纯AC对照若条件/来源清楚可回收用于碳材料子库，不能整篇舍弃。',[3,4,15,17]),
'R024':('HPAC未复合碳与TiO2/三聚氰胺/硅源改性DHPAC的对照有明确制备与性能。',
         '不把含Ti的DHPAC归纯非金属掺杂；优先核HPAC碳对照与DHPAC组成各自的标签。',[4,11,15]),
'R035':('核桃壳WS-dAC及NiO含量系列，CV/GCD均有自身实验对照。',
         '纯WS-dAC对照可单独审核，NiO复合样品保留负载量；173/205 F/g的GCD与254/279 F/g的CV分开。',[2,3,8]),
'R042':('咖啡渣碳/Ni(OH)2复合有电极与器件数据，可供复合体系或碳对照抽取。',
         '需记录Ni(OH)2含量、碳来源和正负极；电池型电极若用C/g或mAh/g不能无条件换成F/g。',[2,8,9]),
'R043':('树皮碳、MWCNT和Ni体系，有对照及柔性非对称器件。',
         '纯碳、CNT辅助及Ni复合分层；固体/凝胶电解液、单电极/器件、柔性弯曲条件各自记录。',[5,7,11]),
'R045':('芦苇/三聚氰胺掺杂比和温度系列可提供工艺与低电流性能对照。',
         'p10结论把164写成mF/g，p3还同时出现164与158 F/g的20 A/g描述；20 A/g/倍率相关字段暂冻，不擅自纠正。低电流及其他样品需独立核对。',[3,6,10]),
'R047':('榕树枝碳FAPC-0与Fe簇含量系列及器件性能，可用作金属参与效应数据。',
         '纯碳FAPC-0与Fe修饰样品分层；制备和测试详情在SI，不能按题名漏掉碳对照。',[2,4,5]),
'R048':('MS-AC及Sm掺杂的工艺、三电极和器件对照。',
         'Sm复合样品单列，优先核未掺杂MS-AC的前驱体与完整条件，不能将器件182 F/g与560 F/g电极值拼接。',[3,4,12]),
'R056':('蒜皮GPBC碳和镍钼双金属硫化物复合，有非对称器件结果。',
         '纯GPBC对照若具测试可用于碳子库；硫化物复合电池型电极容量及器件电容分别记录。',[2,3,10]),
'R081':('木质素Fe配位/三聚氰胺系列，含无Fe对照SN6C@900，具制备与三/两电极数据。',
         'Fe辅助制备与最终金属残留身份需查SI/成分；在核清前保留金属参与标记，不直接叫“纯N/S掺杂碳”。',[3,4,6,7,10,11]),
'R095':('椰壳熔盐无渣/加冶金渣对照，有59.9/135 F/g等报告值。',
         '渣引入Zn/Co等成分的样品分层，纯熔盐碳对照可独立审核，DFT模拟点不当实验材料。',[2,7,8]),
'R097':('纤维素CNF/RGO气凝胶的冻结方向对照具有电容与应变传感双用途。',
         'RGO复合体系单列，传感指标不当储能标签；BCRCA/UCRCA/NCRCA按实际配方保留。',[2,6,8]),
'R115':('非碳化木质素沉积于商业活性炭的复合有独立电化学对照，可作聚合物/碳扩展体系资料。',
         '不等同“木质素碳化得到的碳”。商业AC前驱体未证实，当前不能直接进入生物质衍生碳核心子库。',[1,2,3,8]),
'SRC101':('油棕空果串AC与Fe-ZnO复合、非对称硬币及柔性器件都有工艺和数值结果。',
         'AC碳对照、Fe-ZnO复合、柔性器件分别建层；需核质量分母、负载量和两极配比。',[2,16]),
'SRC102':('玉米秸秆Fenton预处理和不同KOH比对照，能用于工艺/残留金属影响研究。',
         'p6明确报告痕量稳定形态Fe残留；记录残留状态，不能标成绝对无金属。LCA产率/环境负担不当电容测试值。',[2,5,6,7,9]),
'SRC115':('造纸黑液AC600/650/700等样品有孔结构与储能实验，提供可追溯碳材料特征。',
         '正文实际测试为锂离子电容器正极对锂半电池；67.3 mAh/g与推算F/g不能混进普通水系EDLC。用于锂离子电容器专门子库或孔结构任务。',[1,2,3,8]),
'R038':('有椰壳碳和橙汁活化系列；材料方向相关。',
         'p3报告两电极6 M KOH在0–3 V测试，并把2–50 μm称为介孔；有效窗口与孔径口径待核，暂停直接导入性能。椰壳是前驱体、橙汁是活化剂，两个名称本身不是原料矛盾。',[2,3,5,9]),
'R088':('生物质碳相关实验，但已有关键单位冻结。',
         '首页389.3 cm²/g与21.93 g/cm²已图像确认；未取得原文澄清前不修成常见单位、不导入。',[1]),
'SRC022':('烟叶碳/金属发热丝/MnO2非对称器件具有制备及电化学记录。',
         '当前PDF无可靠发表日期/正式版本标识；同时为复合体系。先核日期和版本再决定，不能因为不在旧名单就说无用。',[4,5,23]),
'SRC023':('混合生物质N掺杂碳原始实验与方向相关。',
         '既有冻结：p7表2孔径列标题与脚注矛盾；保持冻结，需原始依据澄清后才解除具体字段。',[7]),
'SRC071':('导电聚合物/复合材料机器学习，可读方法，非当前核心生物质碳实验来源。',
         '既有冻结：样本量62/64及统计/引用报告问题；不作为当前训练数据来源。',[1]),
'SRC073':('石墨烯/聚合物机器学习论文，原始数据可靠性待补。',
         '既有冻结：摘要残留mean ± SD to be reported；不把未经报告的统计量填为已验证。',[1]),
'SRC086':('镍钴硫化物实验/机器学习体系，非已确认生物质碳。',
         '既有冻结：数据来源/独立样本量和导电率描述矛盾；不可直接导入或照搬模型验证。',[1]),
'SRC094':('白桦木BWC温度/活化比系列，有孔结构与自身电容实验。',
         'SSRN预印本，正式出版与时间/版本待核；商业YP-80F对照不能归作白桦木新制样品。',[8,9,18,20,21]),
'SRC100':('壳聚糖/SiO2/Fe体系存在自身电化学实验和Raman数据。',
         'p2为400°C空气煅烧、随后水热Fe改性，正文仍称聚合物壳聚糖基体；是否属于可比的衍生碳相未核清，先暂停核心碳库导入。',[2,6,9,12,13]),
'SRC104':('水烟烟草废物HTWB的温度/硫代硫酸钠比系列，正文直接列6个样品的电容。',
         'Research Square预印本，需核发布日期和最终版对应；保留为潜在来源，不作为已核正式期刊实验直接准入。',[3,6,16]),
'SRC106':('枣椰花粉碳虽用于脱盐，但确有三电极CV/GCD，可有条件贡献电化学数据。',
         'p14电容8.7→85.1 F/g随扫速5→100 mV/s上升，却在同段写“decrease”；图像确认且为SSRN预印本，需原始曲线/版本澄清，不能只因题名脱盐而直接排除。',[7,14]),
'SRC107':('月桂叶BLPC-700/800/900有自身超电容与钠离子电池结果。',
         'SSRN版本/日期待核；电池容量不得混入电容，商业或文献比较样品不作新增材料。',[5,10,16]),
'SRC110':('竹炭NaOH活化原始实验，制备与表格均有信息。',
         'p5质量0.06 g，表8(p14)0.50 A却被概述作0.5 A/g；833.33 F/g、1 V对应的0.1157 Wh/kg有1000倍质量单位问题。表2放电时间与表8也不一致；暂停导入，不直接替作者修数。',[3,4,5,14,18]),
'SRC111':('竹笋壳BBC系列有原始制备及电容、器件数据。',
         '版本/日期不明；p1/p10为11.11 Wh/kg、252 W/kg，p11结论颠倒成252 Wh/kg、11.11 W/kg。相关器件标签冻结，须核正式版及原图。',[1,3,10,11]),
'R002':('原料/工艺描述符建模参考；正文195条是文献汇总，不是作者195种新制样品。',
         '若利用附表必须回原始DOI、日期、材料和测试条件；与SRC087共享底层数据不能当独立新增批次。',[2]),
'R007':('能量密度预测、描述符和解释分析可作方法参考。',
         '为文献汇总；需逐条追源年份/材料，禁止把汇总发表年2026套给旧数据，PW与电容计算关系须按预测场景判断。',[1,6,11]),
'R057':('PCA可作变量关联/数据展示的参考，数据明确来自既有文献。',
         '不能把PCA表和其引用原文都计样本；文中众数填补的值不是新的实测值，不能直接抄入原始实验库。',[3,4,6]),
'SRC018':('高质量负载2与10 mg/cm²、电极厚度/传输控制可作测试设计背景。',
         'p2原料为商业YP-50F，未证实生物质来源；ZIHC体系不同，不自动把其数据视作当前生物质合成实验。',[1,2]),
'SRC019':('电解液浓度、CO2处理及电压窗口对电容影响，可帮助定义测试条件。',
         'p2用商业YP-50F，不是本研究制备生物质炭；保留方法背景，不能用其条件代填其他论文缺失条件。',[2]),
'SRC072':('碳电极物性描述符及多模型比较参考，采用文献数据。',
         '没有独立新增生物质制备样品；需逐条原始来源筛年份和材料。',[1,2,9]),
'SRC074':('电沉积工艺—性能建模及实验设计参考。',
         'PANI电极不是生物质衍生碳，原始实验也不应并入当前核心训练；借鉴流程不代表已审计其验证方法。',[3,4]),
'SRC077':('孔分布/密度与离子液电容的描述符方法有参考价值，也有原始CDC实验。',
         'p7原料明确为金属碳化物，不是生物质；67个CDC不能并入当前生物质训练数据。',[5,7,8]),
'SRC083':('多测试条件、物性描述符以及文献数据库组织方式可参考。',
         '4899条来自147个原始引用；不同电流点不等于独立材料，且包含早年来源，不能整体当2023年新增实验。',[1,3,14]),
'SRC087':('按来源评估的讨论值得参考，适合检查随机拆分是否夸大泛化。',
         'p6明示使用1-s2.0-S2352152X2402560X-mmc1.xlsx，p33参考[32]就是R002；同一底层数据不是新实验。接受稿需核正式状态，方法本身尚未独立复现。',[1,2,6,33]),
'SRC113':('椰壳碳有实验内容，但当前文件为2022-08-02预印本。',
         '不符合2023年至今；不能用同题2023正式版的年份套用当前文件，不进入当前训练来源。',[1,2])
}
review_ids='R008 R009 R010 R011 R021 R027 R037 R041 SRC069 SRC070 SRC080 SRC085'.split()
for pid in review_ids:
    notes[pid]=('综述汇集制备路线、材料或电化学机制，可帮助建立字段和找到原始研究。',
                '正文对比表与引用值均不是新的独立实验；如追溯数据，必须读取2023年至今的原始研究并与已有来源去重。',[1,2])
notes['SRC097']=('DES分离/脱木质素的工艺背景，可帮助理解前处理变量。','没有与本研究材料一一对应的超级电容标签，不把脱木质素结果直接补作其他论文的输入。',[1])
notes['SRC118']=('烟蒂资源化综述可用于找原始制炭文献。','没有新制碳样品—性能配对；原料污染/吸附数据不当超电容标签，引用年份须回原文。',[1])
out_of_scope={
 'SRC002':'椰壳商业碳水伏发电，目标是湿度/水流引起的电压与功率，不是超电容充放电性能。',
 'SRC026':'纳米流体换热/导热率机器学习，研究对象和输出都不匹配。',
 'SRC027':'Fe/N/S碳ORR与锌空气电池，未定位自身超电容性能配对，前驱体也不是已确认生物质。',
 'SRC030':'Co-MOF/镍泡沫预印本，无已确认生物质衍生碳；当前不作为材料训练数据。',
 'SRC032':'石墨氧化还原rGO/TiO2，虽有电容但没有已确认生物质前驱体。',
 'SRC075':'MXene物性DFT/机器学习综述，缺当前生物质碳实验标签。',
 'SRC078':'MXene储能/转化综述，不是当前生物质碳原始实验来源。',
 'SRC081':'Li2TiO3机械性质预测，材料和目标不对应。',
 'SRC082':'无机化合物热力学稳定性/电子构型建模，不能提供本项目的样品或性能标签。',
 'SRC084':'神经信号仿生超级电容器应用综述，无当前制备—储能性能配对。',
 'SRC088':'无粘结碳电极用于解耦水电解，未找到本研究所需超电容标签。',
 'SRC089':'软木活性炭用于工业染料吸附，虽有BET但缺配对超电容测试，不能据BET编造标签。',
 'SRC090':'煤基多孔碳锌离子混合电容器；煤不是生物质。',
 'SRC091':'湿气诱导发电综述/机制，不提供本项目超电容原始实验。',
 'SRC092':'Al-MOF衍生碳，未确认生物质前驱体；不能因材料也叫碳就并入。',
 'SRC095':'钴纳米材料书籍章节/网页打印件，无当前生物质碳样品与性能配对。',
 'SRC096':'全固态钠电池回收/溶剂选择性，不是碳超级电容实验。',
 'SRC098':'Mo2Ti2C3 MXene/PANI复合，没有生物质来源，不属于当前材料范围。',
 'SRC103':'热解油生物石墨用于锂离子电池负极，mAh/g电池容量不能代替超电容标签。',
 'SRC105':'生物炭/海藻酸水凝胶用于止血，缺超电容标签；卷期2027也不能单独用于推断首次上线日期。',
 'SRC108':'1T-MoS2/BBD功能化超电容，非生物质碳。',
 'SRC109':'MXene选择性离子分离/脱盐综述，无当前生物质原始超电容样品。',
 'SRC114':'rGO/Ni-MOF自组装，未确认生物质碳前驱体。',
 'SRC116':'生物炭去除农药，缺对应超级电容性能。',
 'SRC117':'生物质组分炭用于PFAS吸附，引用了超电容DOI也不等于本篇进行了相应实验。',
 'SRC119':'合成酚醛树脂衍生碳，虽然有F/g性能但未确认生物质来源。',
 'SRC122':'椰壳缺陷碳用于OER/HER，过电位/催化稳定性不是本项目超电容标签。'
}
for pid,reason in out_of_scope.items():notes[pid]=(reason,'不进入当前生物质碳超级电容训练数据；如未来另设任务，再重新评估。',[1,2])
assert set(notes)==set(byid),(set(byid)-set(notes))

# Page-grounded snippets are locators, not independently recalculated measurements.
def pick_evidence(x,pages):
    parts=re.split(r'\n===== PDF PAGE (\d+) =====\n',Path(x['fulltext_file']).read_text(encoding='utf-8'))
    page_map={int(parts[i]):re.sub(r'\s+',' ',parts[i+1]) for i in range(1,len(parts),2)}
    items=[]
    for page in pages:
        if page not in page_map:continue
        text=page_map[page]
        pats=(r'\d[\d.,]*\s*(?:F\s*[/·⋅]?\s*g|F\s*/\s*cm|mF\s*cm)',
              r'\b(?:denoted|abbreviated|designated|carbonized|activated|three.electrode|two.electrode)\b',
              r'(?i)review|ABSTRACT|Abstract')
        m=next((m for pat in pats if (m:=re.search(pat,text,re.I))),None)
        pos=m.start() if m else 0
        items.append({'pdf_page':page,'locator_excerpt':text[max(0,pos-100):min(len(text),pos+450)]})
    return items

rows=[]
for x in docs:
    code=assign[x['id']];positive,restriction,pages=notes[x['id']]
    item={k:x[k] for k in ['id','title','doi','year','local_pdf','sha256','pages','version','source_record_id']}
    if x['id'] in ['SRC099','SRC069']:
        item['year']=2026;item['year_basis']='PDF首页年份/出版日期，未依赖DOI字符串'
    item.update({'use_category':code,'use_label':groups[code][0], 'useful_for_experimental_extraction':code in 'AB',
                 'reason':positive,'restrictions':restriction,'evidence_pdf_pages':pages,
                 'evidence':pick_evidence(x,pages),
                 'eligibility_level':'文献级用途筛查；非逐测试记录准入',
                 'eligible_for_database':False,'independent_material_count_audited':None,
                 'auxiliary_method_use':x['id'] in ['R001','R005'],
                 'old_list_membership_used_as_filter':False})
    rows.append(item)
rows.sort(key=lambda x:(x['use_category'],x['id']))
counts=dict(collections.Counter(x['use_category'] for x in rows))
assert counts=={'A':39,'B':17,'C':14,'D':24,'E':27,'F':1},counts

# Actual source examples: 4 experimental rows from R005, with unambiguous p4/p10 pairing.
pilot=[]
for sample,temp,hours,cap in [('PW-650–1',650,1,362.2),('PW-650–3',650,3,346.6),
                              ('PW-400–3',400,3,353.3),('PW-400–1',400,1,276.0)]:
    pilot.append({'paper_id':'R005','doi':byid['R005']['doi'],'sample_label_original':sample,
                  'precursor':'Peach Wood','carbonization_temperature_C':temp,'carbonization_time_h':hours,
                  'carbonization_heating_rate_C_min':3,'activation_temperature_C':600,'activation_time_h':1,
                  'activation_heating_rate_C_min':3,'activation_agent':'KOH', 'activation_ratio':2,
                  'activation_ratio_basis_original':'mass ratio of KOH to biomass precursor',
                  'carbonization_atmosphere':None,'activation_atmosphere':None,
                  'atmosphere_note':'验证段未明确写出所用气氛，不能根据文献汇总筛选规则代填N2',
                  'electrode_configuration':'three-electrode','electrolyte':'KOH','electrolyte_concentration_mol_L':6,
                  'reference_electrode':'Hg/HgO','counter_electrode':'Pt','method':'GCD',
                  'current_density_A_g':1,'reported_specific_capacitance_F_g':cap,
                  'specific_capacitance_origin':'原文报告，未从曲线独立重算',
                  'source_pdf_pages':{'preparation_and_test':4,'reported_values':10},
                  'eligible_for_database':False,
                  'remaining_checks':'活化比基准究竟按原料还是预炭化物需保留原意；气氛、活性物质质量/电压窗口及补充公式需核。'})
dump(OUT/'R005_4个原始实验样例_待逐记录准入.json',pilot)

si_path=Path(r'D:\文献\补充材料_2023至今\R107__mmc1.docx')
tables=Document(si_path).tables
materials={}
for index in [0,2]:
    for row in tables[index].rows[1:]:
        cells=[c.text.strip() for c in row.cells]
        materials[cells[0]]={'paper_id':'R107','sample_label_original':cells[0],
                            'SSA_m2_g':float(cells[1]),'micropore_surface_area_m2_g':float(cells[2]),
                            'pore_volume_cm3_g':float(cells[3]),'micropore_volume_cm3_g':float(cells[4]),
                            'average_pore_size_nm':float(cells[5]),
                            'source_table':f'S{index+1}', 'source_file':str(si_path),'eligible_for_database':False}
tests=[]
for index in [1,3]:
    for row in tables[index].rows[2:]:
        cells=[c.text.strip() for c in row.cells]
        for current,value in zip([0.1,0.5,1.0,5.0,10.0],cells[1:]):
            tests.append({'paper_id':'R107','sample_label_original':cells[0],
                          'current_density_A_g':current,'reported_specific_capacitance_F_g':float(value),
                          'electrode_configuration':'待将SI表与正文三/两电极结果逐项对应',
                          'source_table':f'S{index+1}','source_file':str(si_path),
                          'eligible_for_database':False})
assert len(materials)==6 and len(tests)==30
assert next(x['reported_specific_capacitance_F_g'] for x in tests if x['sample_label_original']=='DUGPC' and x['current_density_A_g']==1)==408.77
dump(OUT/'R107_SI_6材料30测试_报告值样例.json',{'materials':list(materials.values()),'tests':tests,
     'note':'S1/S3为材料孔结构，S2/S4为不同电流下报告值；30个测试点属于6个材料。电极/质量分母待与正文式1–3逐条核定；不是正式训练表。'})

issues=[
 {'id':'TQ01','papers':['SRC110'],'topic':'绝对电流/电流密度与能量单位冲突','pages':[5,14,18],
  'evidence':'表2质量0.06 g；表8最后一行为I=0.50 A、Δt=100 s、C=833.33 F/g，概述却称0.5 A/g；能量写0.1157 Wh/kg。',
  'check':'0.50/0.06=8.333 A/g；若按文中C=833.33 F/g和1 V，C×V²/7.2≈115.74 Wh/kg，与0.1157约差1000倍。这里只作量纲核对，不生成修复后的训练值。',
  'action':'暂停性能字段；表2的放电时间又标estimated且与表8不同，需要正式澄清。'},
 {'id':'TQ02','papers':['SRC111'],'topic':'能量/功率数值在结论互换','pages':[1,10,11],
  'evidence':'p1/p10为11.11 Wh/kg、252 W/kg；p11写252 Wh/kg、11.11 W/kg，已图像确认。','action':'版本/日期和对应器件字段暂停；不把结论数值导入。'},
 {'id':'TQ03','papers':['SRC106'],'topic':'CV数值排序与同段文字相反','pages':[14],
  'evidence':'5/10/20/50/100 mV/s对应8.7/15.4/24.1/52.8/85.1 F/g，却同段写随扫速升高decrease，已图像确认；SSRN预印本。',
  'action':'需核原曲线、公式和版本，不凭预期趋势改排列，不因是脱盐论文就一概判无数据价值。'},
 {'id':'TQ04','papers':['R045'],'topic':'高电流电容单位/值矛盾','pages':[3,10],
  'evidence':'p10结论为164 mF/g；p3同时出现20 A/g下164与158 F/g。','action':'冻结高电流/倍率有关字段，低电流202.8 F/g等也需与正文图表独立对应；其他材料信息仍可审。'},
 {'id':'TQ05','papers':['R038'],'topic':'电压窗口和孔径类别需核','pages':[2,3,5,9],
  'evidence':'两电极6 M KOH、0–3 V；p3把2–50 μm称介孔。橙汁是活化剂、椰壳是前驱体，不把两个名字误判成原料冲突。',
  'action':'暂停直接导入性能；SEM尺度与BET孔径区分，不能自动将μm改nm或3 V改1 V。'},
 {'id':'TQ06','papers':['SRC121'],'topic':'推算器件值不得标成实测','pages':[1,3,8],
  'evidence':'首页450 F/g明确为estimated full-device；p3实验为三电极。','action':'三电极原始实验可审；450 F/g及相关器件能量/功率必须保留推算状态，不训练成实测器件标签。'},
 {'id':'TQ07','papers':['R002','SRC087'],'topic':'同一底层汇总数据重复','pages':{'SRC087':[6,33],'R002':[2]},
  'evidence':'SRC087明示使用1-s2.0-S2352152X2402560X-mmc1.xlsx，参考[32]的DOI为10.1016/j.est.2024.112974，即R002。',
  'action':'不能计两批新实验；任何二手行需回到原始材料DOI后去重、筛年份并分组验证。'},
 {'id':'TQ08','papers':['R001','R005','R007','R057','SRC072','SRC083','SRC087'],'topic':'新论文不能刷新底层旧数据年份','pages':[],
  'evidence':'多篇数据来自既有文献；R005明确收集2021–2025，R057从前作表格取数且填补缺失；R001 S1已有重复和旧来源。',
  'action':'二手数据不整体导入。R005独立4个桃木新实验可另审；R001新蜜瓜皮段需查与前作重复，不因是ML论文整篇丢弃。'},
 {'id':'TQ09','papers':['R108','SRC093','SRC099'],'topic':'质量/面积/体积口径不可直接拼接','pages':{'R108':[8,10],'SRC093':[12],'SRC099':[3,5]},
  'evidence':'出现F/g、F/cm²、F/cm³与A/g、mA/cm²；不是同一分母。','action':'均可作为不同任务的候选，保留单位和条件，缺密度/负载时不换算。'},
 {'id':'TQ10','papers':['R088','SRC023','SRC071','SRC073','SRC086'],'topic':'原有冻结继续有效','pages':[],
  'evidence':'见已定位的R088单位问题及既有禁止入库/问题登记记录。','action':'本次用途筛查不自动解冻；范围相关、期刊年份符合也不等于记录已可训练。'}
]
dump(OUT/'训练相关问题登记.json',issues)
dump(OUT/'逐份训练用途审核.json',rows)
summary={'date':'2026-10-17','scope':'所有已有全文按内容去重122份；忽略是否在旧120篇名单',
         'pdf_contents_reviewed':122,'supplements_read':4,'new_pdf_pages_visually_checked':14,
         'categories':{k:{'label':groups[k][0],'count':counts[k]} for k in groups},
         'experimental_source_candidates':counts['A']+counts['B'],
         'formal_training_records_approved':0,'pilot_materials':{'R005':4,'R107_SI':6},
         'pilot_reported_test_values':{'R005':4,'R107_SI':30},
         'limitation':'文献级用途筛查，结合正文检索、关键方法/结果核读和14页图像复核；未逐篇复算所有曲线，未完成逐记录准入，也未做新的全库撤稿/勘误联网核查。',
         'target_metric_not_locked':True,'model_not_selected_or_trained':True}
dump(OUT/'审核汇总.json',summary)

cards=OUT/'逐份证据卡';cards.mkdir(exist_ok=True)
safe=lambda s:str(s).replace('|','／').replace('\n',' ')
for row in rows:
    text=[f'# {row["id"]}：{row["title"]}','',f'用途：{row["use_label"]}。',
          f'年份：{row["year"] or "待核"}。DOI：{row["doi"] or "未确认"}。',
          f'[打开原PDF](<{row["local_pdf"]}>)','',row['reason'],'',row['restrictions'],'',
          '本次为文献用途筛查，未逐测试记录批准进入训练库；缺失条件不得补猜。','',
          '## 原文定位','',f'PDF页序：{", ".join(map(str,row["evidence_pdf_pages"]))}。']
    for e in row['evidence']:text+=['',f'### PDF第{e["pdf_page"]}页检索定位','',e['locator_excerpt']]
    text+=['','摘录为阅读定位，可能带原PDF字形编码；不直接作为数值录入结果。',
           f'文件SHA256：{row["sha256"]}','']
    (cards/(row['id']+'.md')).write_text('\n'.join(text),encoding='utf-8')

report=['# 全部已有文献的训练用途审核','','完成：2026-10-17。目录名保留20261016作为开始日期。','',
        '本轮检查全部122份不同PDF内容，不以是否属于旧120篇名单为条件。已阅读/检索正文与现有4份补充材料，对关键单位和表图问题另做14页图像复核。', '',
        '## 结论','',
        '**56份有继续提取实验数据的价值：39份主要来源候选，17份需按材料/器件体系分层或限定字段使用。另14份暂缓，24份作方法/背景参考，27份与当前训练不直接匹配，1份为2022年旧版本。**','',
        '这是文献级用途判断，不是56篇都已产生可训练数据。122份PDF内容也不必然是122个独立底层研究；逐材料、逐测试的正式准入目前为0，真实样本总数需要录入后才能给出。','',
        '| 用途 | 份数 | 怎么用 |','|---|---:|---|',
        '| 主要实验数据来源候选 | 39 | 提取本研究的制备样品、物性和测试结果；仍须逐条核测试条件/出处 |',
        '| 分体系或限定字段使用 | 17 | 复合材料、金属参与、锂离子电容器或仅部分可靠字段单列；保留纯碳对照 |',
        '| 暂缓实验数据使用 | 14 | 单位/计算/版本/碳相身份存在未解问题，先保留证据 |',
        '| 方法与背景参考 | 24 | 借鉴字段、验证和机理，二手表不冒充新实验 |',
        '| 当前训练无直接用途 | 27 | 无匹配前驱体或超电容性能标签，保持原文件 |',
        '| 年份不符 | 1 | 2022预印本不使用，不能套用同题正式版年份 |','',
        '[逐份审核总表](训练用途审核总表.xlsx) · [机器可读完整审核](逐份训练用途审核.json)','',
        '## 本轮纠正了哪些判断','',
        '- SRC005香蕉皮模板碳：原先未确认有电容测试；本次正文p3、p8–9确认制备、样品、3 M KOH及CV/GCD。电容较低也有训练价值，保留。',
        '- R005机器学习论文：不能只作方法文献。p4和p10有作者新做的4个桃木样品，能配对工艺和测试值；二手汇总2021–2025仍不得整表导入。',
        '- SRC099印尼文论文：首页明确2026-04-24，p3、p5有萝卜叶DLK/DLK-P、两电极CV和体积电容。体积指标可另建任务，不能因不是F/g而说无用。',
        '- SRC106脱盐论文：确有电化学测试；不是按脱盐题名一概丢弃。当前因为p14数值排序与文字矛盾以及版本问题暂缓。',
        '- SRC115黑液炭：实际为锂离子电容器正极/对锂测试。材料数据有用，但mAh/g及其推算F/g不能直接并入水系EDLC。',
        '- R035、R047、R056、R081等含金属/复合论文：纯碳对照可能有用，按具体样品筛选，不能整篇按题名删除。',
        '- SRC025用KMnO4活化，p5 EDAX报告C/O；不能仅因用过金属盐就判成金属复合。相反SRC102正文p6报告痕量Fe残留，要保存这个属性。','',
        '## 已经找到的真实数据实例','',
        'R005的4个新制桃木样品，正文p4工艺、p10报告值，三电极、6 M KOH、GCD、1 A/g：','',
        '| 样品 | 预碳化温度°C | 预碳化时间h | 活化温度°C | 活化时间h | 原文电容F/g |',
        '|---|---:|---:|---:|---:|---:|']
for r in pilot:report.append(f'| {r["sample_label_original"]} | {r["carbonization_temperature_C"]} | {r["carbonization_time_h"]} | 600 | 1 | {r["reported_specific_capacitance_F_g"]} |')
report+=['','原报告条件已配对，尚未独立重算放电曲线。气氛、质量/电压窗口及活化比基准等缺口在样例JSON中留空或标明，未假填为N2。',
         '[4个样品的来源样例](R005_4个原始实验样例_待逐记录准入.json)','',
         'R107本地SI中6个材料的孔结构与30个电流—电容报告值：','',
         '| 样品 | BET m²/g | 总孔体积cm³/g | 平均孔径nm | 1 A/g报告电容F/g |',
         '|---|---:|---:|---:|---:|']
for r in materials.values():
    cap=next(t['reported_specific_capacitance_F_g'] for t in tests if t['sample_label_original']==r['sample_label_original'] and t['current_density_A_g']==1)
    report.append(f'| {r["sample_label_original"]} | {r["SSA_m2_g"]} | {r["pore_volume_cm3_g"]} | {r["average_pore_size_nm"]} | {cap} |')
report+=['','SI的S1/S3是孔结构，S2/S4是0.1、0.5、1、5、10 A/g下的报告值。这里的30条是6种材料的多条件测试，不是30个材料；电极/质量分母还需与正文式1–3逐项确认。',
         '[6材料30测试的报告值样例](R107_SI_6材料30测试_报告值样例.json)','',
         '## 影响训练的具体问题','']
for issue in issues:
    report += [f'### {issue["id"]}：{issue["topic"]}','',
               '涉及：'+', '.join(issue['papers'])+'。'+issue['evidence'],'']
    if issue.get('check'):report += [issue['check'],'']
    report += [issue['action'],'']
report+=['## 下一步的录入顺序','',
         '先用R005、R107、SRC005、R012、R078、R091、R093、R104、SRC035、SRC112建立第一批真实记录。选择依据是样品—工艺—测试的可追溯性和字段覆盖，不按高性能筛选。',
         '同时保留比电容、倍率保持、循环保持、能量/功率等候选指标。先统计各指标的真实材料数、来源数和完整条件，再选择预测问题，不预定模型。','',
         '以原始研究DOI和材料ID分组，相关电流/电解液测试不得随机分到训练和测试两侧。R002/SRC087等共享底层汇总按原始实验来源去重；综述/机器学习的年份不能刷新底层旧研究。',
         '制备前预测与制备后物性预测是不同问题。BET/XPS等作为输入前要明确预测时是否可获得；放电时间等计算电容所需量不能充当制备前输入。若能量由电容、电压计算，不能把公式重述当材料发现。','',
         '## 完整逐份清单','',
         '每个编号链接到证据卡，卡片附原PDF路径、页码、用途和具体限制。文件名和PDF原件未改动。','']
for code,(label,_) in groups.items():
    report += [f'### {label}（{counts[code]}份）','', '| 编号 | 年份 | 题名与原PDF | 用途依据 | 限制 |','|---|---|---|---|---|']
    for r in rows:
        if r['use_category']!=code:continue
        report.append(f'| [{r["id"]}](逐份证据卡/{r["id"]}.md) | {r["year"] or "待核"} | [{safe(r["title"])}](<{r["local_pdf"]}>) | {safe(r["reason"])} | {safe(r["restrictions"])} |')
    report+=['']
report+=['## 审核边界','',summary['limitation'],
         '未导入正式训练库、未运行训练、未以性能高低删除文献或数据。2023年至今的要求不变；版本未明者保留待核。所有文献级eligible_for_database仍为false，因为正式准入必须落到具体材料和测试记录。','']
(OUT/'训练用途审核报告.md').write_text('\n'.join(report),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))

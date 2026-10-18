"""Render the sanitized development retrospective without external dependencies."""
from pathlib import Path
import html,re
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'docs/retrospective/参赛开发全流程复盘-公开脱敏版.md'
OUT=SOURCE.with_suffix('.html')
raw=SOURCE.read_text();lines=raw.splitlines();title=lines[0].lstrip('# ')
def inline(s):
 s=html.escape(s)
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:'<a href="'+m[2].replace('../../README.md','https://github.com/jiangenjing/anker-OntoCare')+'">'+m[1]+'</a>',s)
 s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
 return re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
parts=[];toc=[];i=1;section=False
while i<len(lines):
 line=lines[i].strip()
 if not line:i+=1;continue
 if line.startswith('## '):
  if section:parts.append('</section>')
  ident='part-'+str(len(toc)+1);text=line[3:];toc.append((ident,text));parts.append('<section id="'+ident+'"><h2>'+inline(text)+'</h2>');section=True;i+=1;continue
 if line.startswith('### '):parts.append('<h3>'+inline(line[4:])+'</h3>');i+=1;continue
 if line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].strip().startswith('|'):
   row=lines[i].strip();i+=1
   if re.fullmatch(r'[| :\-]+',row):continue
   rows.append([c.strip() for c in row.strip('|').split('|')])
  parts.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>');continue
 if line.startswith('- ') or re.match(r'^\d+\. ',line):
  ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
  while i<len(lines) and (re.match(r'^\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
   text=re.sub(r'^\d+\. |^- ','',lines[i]);items.append('<li>'+inline(text)+'</li>');i+=1
  parts.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
 para=[line];i+=1
 while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','- ')) and not re.match(r'^\d+\. ',lines[i]):para.append(lines[i].strip());i+=1
 parts.append('<p>'+inline(' '.join(para))+'</p>')
if section:parts.append('</section>')
stages=['选择场景','体验调研','补充学习','搭建原型','案例迭代','评测核查','部署路演','赛后整理']
timeline='<ol class="timeline">'+''.join('<li><span>'+str(n+1).zfill(2)+'</span><strong>'+x+'</strong></li>' for n,x in enumerate(stages))+'</ol>'
css='''*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:85px}body{margin:0;background:#f5f7f9;color:#223844;font:16px/1.9 -apple-system,BlinkMacSystemFont,"PingFang SC",system-ui,sans-serif}a{color:#007e91;text-decoration:none}a:hover{text-decoration:underline}header{background:white;border-bottom:1px solid #dce5e9;position:sticky;top:0;z-index:3}.top{max-width:1260px;margin:auto;padding:15px 26px;display:flex;justify-content:space-between;align-items:center;gap:18px}.top strong{font-size:20px}.top nav{display:flex;gap:22px;font-size:13px}.hero{background:#102b37;color:#f4fdff}.hero-inner{max-width:1200px;padding:50px 26px 35px;margin:auto}.eyebrow{font-size:11px;letter-spacing:2px;color:#58d6df;font-weight:700}h1{font-size:clamp(28px,3.5vw,43px);line-height:1.4;max-width:950px;margin:15px 0 19px}.hero p{color:#c0d8e3;font-size:14px;margin:0}.timeline{display:flex;list-style:none;padding:0;gap:12px;overflow-x:auto;margin:30px 0 0;padding-bottom:10px}.timeline li{min-width:120px;flex:1;background:#1a3b49;border:1px solid #2d596a;border-radius:9px;padding:13px 12px}.timeline span{display:block;color:#55d8df;font-size:12px}.timeline strong{font-size:14px;font-weight:600}.timeline-note{font-size:11px!important;color:#86abbc!important}.layout{max-width:1200px;margin:32px auto 70px;padding:0 26px;display:grid;grid-template-columns:230px minmax(0,1fr);gap:30px}.toc{position:sticky;top:95px;align-self:start;background:white;border:1px solid #e0e7eb;border-radius:12px;padding:18px;font-size:12px}.toc summary{font-size:14px;font-weight:700;cursor:pointer}.toc nav{display:grid;gap:9px;margin-top:14px}.toc a{color:#577582;line-height:1.7}article{min-width:0;padding:30px 36px;background:white;border:1px solid #dfe7ec;border-radius:13px}article>p{font-size:14px;color:#607b88}section{padding-top:25px;scroll-margin-top:80px}h2{font-size:22px;line-height:1.5;margin:15px 0 18px;border-top:1px solid #e4ecef;padding-top:24px}h3{font-size:18px;margin:25px 0 13px}p{margin:15px 0;font-size:15px}li{font-size:15px;margin:10px 0}ul,ol{padding-left:22px}strong{color:inherit}code{font-size:13px;background:#edf3f6;padding:2px 5px;border-radius:4px}.table-wrap{overflow:auto;margin:22px 0;border:1px solid #dce8ed;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:13px;min-width:400px;line-height:1.8}th,td{text-align:left;padding:13px 16px;border-bottom:1px solid #e6edf0}th{background:#eef5f7;color:#315a6b}tbody tr:last-child td{border-bottom:0}.end{display:flex;flex-wrap:wrap;gap:12px;margin-top:40px;padding-top:20px;border-top:1px solid #e4ecef;font-size:13px}.end a{border:1px solid #cbdde5;padding:8px 13px;border-radius:7px}footer{text-align:center;font-size:12px;padding:20px;color:#78909c}@media(max-width:850px){.layout{grid-template-columns:1fr;gap:16px}.toc{position:static}.toc nav{grid-template-columns:1fr 1fr}article{padding:22px}.top nav{gap:13px}.hero-inner{padding-top:34px}.timeline li{min-width:115px}}@media(max-width:500px){body{font-size:15px}.top{padding:12px 18px}.top strong{font-size:18px}.top nav a:last-child{display:none}.hero-inner{padding:30px 20px 25px}h1{font-size:29px}.layout{padding:0 16px;margin-top:20px}article{padding:18px}h2{font-size:20px}p,li{font-size:14px}.toc nav{grid-template-columns:1fr}table{min-width:380px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{header,.toc,.end{display:none}.layout{display:block;padding:0}.hero{background:#edf3f6;color:#223844}.hero p{color:#496671}.timeline li{background:#edf3f6;color:#223844;border-color:#c0d5df}.eyebrow{color:#277a8d}article{border:0}.hero-inner{padding:20px}h2{break-after:avoid}tr{break-inside:avoid}}'''
page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><link rel="icon" href="data:,"><style>'+css+'</style></head><body><header><div class="top"><strong>OntoCare · 开发复盘</strong><nav><a href="../../index.html">项目图文页</a><a href="https://github.com/jiangenjing/anker-OntoCare#readme">仓库说明</a><a href="https://github.com/jiangenjing/anker-OntoCare">GitHub ↗</a></nav></div></header><div class="hero"><div class="hero-inner"><span class="eyebrow">LEARNING · BUILDING · REFLECTING</span><h1>'+html.escape(title)+'</h1><p>从个人分享整理的公开版 · 保留学习、验证与交付过程</p>'+timeline+'<p class="timeline-note">可横向滑动查看完整流程</p></div></div><main class="layout"><details class="toc" open><summary>阅读目录</summary><nav>'+''.join('<a href="#'+i+'">'+html.escape(t)+'</a>' for i,t in toc)+'</nav></details><article>'+''.join(parts)+'<div class="end"><a href="'+SOURCE.name+'">下载公开版Markdown</a><a href="https://github.com/jiangenjing/anker-OntoCare#联系与实习意向">联系与实习意向</a><a href="../../index.html">返回图文项目介绍</a></div></article></main><footer>个人经历公开整理版 · 不包含原录音与私人沟通记录</footer><script>if(matchMedia("(max-width:850px)").matches)document.querySelector(".toc").removeAttribute("open");</script></body></html>'
OUT.write_text(page)
print('Generated',OUT.name,'sections',len(toc))

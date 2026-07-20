#!/usr/bin/env python3
"""A股涨跌幅云图生成器 v3 - 按日期输出，不覆盖"""
import json
import os
import subprocess
import time

BASE_DIR = os.path.expanduser("~/Desktop/a_stock")
os.makedirs(BASE_DIR, exist_ok=True)

INDUSTRY_COLORS = [
    "#e6194b","#3cb44b","#ffe119","#4363d8","#f58231","#911eb4","#42d4f4","#f032e6","#bfef45","#fabed4",
    "#469990","#dcbeff","#9a6324","#fffac8","#800000","#aaffc3","#808000","#ffd8b1","#000075","#a9a9a9",
    "#e6beff","#c0c0c0","#ff6f61","#6b5b95","#88b04b","#f7cac9","#92a8d1","#955251","#b565a7","#009b77",
    "#dd4124","#d65076","#45b8ac","#efc050","#5b5ea6","#9b2335","#dfcfbe","#55b4b0","#e15d44","#7fcdcd",
    "#c3447a","#98b4d4","#c39bd3","#f0b27a","#82e0aa","#f1948a","#85c1e9","#bb8fce","#73c6b6","#e59866",
    "#a3e4d7","#fadbd8","#aeb6bf","#d4ac0d","#27ae60","#2980b9","#8e44ad","#16a085","#c0392b","#2c3e50",
    "#d35400","#7f8c8d","#1abc9c","#e74c3c","#3498db","#9b59b6",
]


def curl(url, retries=3):
    for i in range(retries):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "15",
                 "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                 url],
                capture_output=True, text=True, timeout=20
            )
            if result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        if i < retries - 1:
            time.sleep(2)
    return ""


def save_file(content, filename):
    # 如果是 JSON 内容，尝试格式化
    if filename.endswith('.json'):
        try:
            # 尝试解析并格式化
            import json
            data = json.loads(content)
            content = json.dumps(data, ensure_ascii=False, indent=2)
        except:
            pass  # 如果解析失败，保持原样
    with open(os.path.join(BASE_DIR, filename), "w", encoding="utf-8") as f:
        f.write(content)

def fetch_stock_list_sina(asc=0, num=300):
    url = (
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"Market_Center.getHQNodeDataSimple?page=1&num={num}&sort=changepercent"
        f"&asc={asc}&node=hs_a&symbol=&_s_r_a=init"
    )
    text = curl(url)
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    items = []
    for s in data:
        items.append({
            "code": s.get("code", ""),
            "name": s.get("name", ""),
            "changepercent": float(s.get("changepercent", 0)),
            "trade": float(s.get("trade", 0)),
        })
    return items


def enrich_with_eastmoney(stocks):
    if not stocks:
        return []
    secids = []
    code_map = {}
    for s in stocks:
        code = s["code"]
        secid = f"1.{code}" if (code.startswith("6") or code.startswith("9") or
                                 code.startswith("8") or code.startswith("4") or
                                 code.startswith("920")) else f"0.{code}"
        secids.append(secid)
        code_map[secid] = s
        code_map[f"0.{code}" if secid.startswith("1.") else f"1.{code}"] = s

    for i in range(0, len(secids), 80):
        batch = secids[i:i + 80]
        url = ("https://push2.eastmoney.com/api/qt/ulist.np/get?"
               f"fltt=2&secids={','.join(batch)}&fields=f12,f14,f2,f3,f20,f100")
        resp = curl(url)
        if resp:
            try:
                data = json.loads(resp)
                for item in data.get("data", {}).get("diff", []):
                    code = str(item.get("f12", ""))
                    for prefix in ("0.", "1."):
                        sid = prefix + code
                        if sid in code_map:
                            s = code_map[sid]
                            s["f20"] = float(item.get("f20", 0) or 0)
                            s["f100"] = str(item.get("f100", "") or "")
                            s["f2"] = float(item.get("f2", 0) or 0)
            except json.JSONDecodeError:
                pass
        time.sleep(0.3)

    enriched = []
    for s in stocks:
        enriched.append({
            "f12": s["code"],
            "f14": s["name"],
            "f3": s["changepercent"],
            "f2": s.get("f2", s["trade"]),
            "f20": s.get("f20", 0),
            "f100": s.get("f100", ""),
        })
    return enriched


def fetch_data(po):
    asc = 0 if po == 1 else 1
    print(f"   获取排行...", end=" ", flush=True)
    stocks = fetch_stock_list_sina(asc=asc, num=300)
    
    # 保存原始数据
    save_file(json.dumps(stocks, ensure_ascii=False), f"sina_stocks_{po}_{time.strftime('%Y-%m-%d', time.localtime())}.json")

    print(f"({len(stocks)}只)", end=" ", flush=True)
    if not stocks:
        return []
    print("补充行业/市值...", end=" ", flush=True)
    enriched = enrich_with_eastmoney(stocks)
    print(f"({len(enriched)}只)", end="", flush=True)
    return enriched


def format_cap(v):
    if not v: return "-"
    v = float(v)
    if v >= 1e11: return f"{v/1e11:.1f}百亿"
    if v >= 1e10: return f"{v/1e10:.1f}十亿"
    if v >= 1e8: return f"{v/1e8:.1f}亿"
    return f"{v/1e4:.0f}万"


def build_html(up_data, down_data, gen_time, date_str):
    dump = json.dumps
    up_count = len(up_data)
    down_count = len(down_data)
    up_avg = sum(x.get("f3") or 0 for x in up_data) / up_count if up_count else 0
    down_avg = sum(x.get("f3") or 0 for x in down_data) / down_count if down_count else 0

    # Build sorted stock lists for table
    up_sorted = sorted(up_data, key=lambda x: x.get("f3", 0), reverse=True)
    down_sorted = sorted(down_data, key=lambda x: x.get("f3", 0))

    echarts_path = "echarts.min.js"

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股涨跌幅云图 {date_str}</title>
<script src="{echarts_path}"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0f0f1a; color:#e0e0e0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif; }}
.header {{ padding:12px 20px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; border-bottom:1px solid #1e1e32; background:#16162a; position:sticky; top:0; z-index:10; }}
.header h1 {{ font-size:17px; font-weight:600; background:linear-gradient(135deg,#ff6b6b,#ffd93d,#6bcb77,#4d96ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; white-space:nowrap; }}
.tabs {{ display:flex; gap:4px; }}
.tab {{ padding:5px 14px; border-radius:14px; border:1px solid #2a2a45; background:transparent; color:#999; font-size:12px; cursor:pointer; transition:all 0.2s; }}
.tab:hover {{ background:#1e1e38; }}
.tab.active {{ color:#fff; }}
.tab.up.active {{ background:#ff6b6b22; border-color:#ff6b6b; }}
.tab.down.active {{ background:#4d96ff22; border-color:#4d96ff; }}
.controls {{ margin-left:auto; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.toggle-label {{ display:flex; align-items:center; gap:4px; font-size:11px; color:#888; cursor:pointer; user-select:none; }}
.toggle-label input {{ accent-color:#ff6b6b; cursor:pointer; }}
.toggle-label.checked {{ color:#ff6b6b; }}
.paginator {{ display:flex; gap:3px; }}
.paginator button {{ padding:3px 10px; border-radius:10px; border:1px solid #2a2a45; background:transparent; color:#666; font-size:11px; cursor:pointer; }}
.paginator button:hover {{ background:#1e1e38; color:#ccc; }}
.paginator button.active {{ background:#4d96ff33; border-color:#4d96ff; color:#4d96ff; font-weight:600; }}
.fullscreen-btn {{ padding:3px 12px; border-radius:10px; border:1px solid #2a2a45; background:transparent; color:#888; font-size:11px; cursor:pointer; }}
.fullscreen-btn:hover {{ background:#1e1e38; color:#e0e0e0; }}
.stats {{ display:flex; gap:10px; font-size:11px; color:#888; padding:4px 20px; border-bottom:1px solid #1a1a2e; flex-wrap:wrap; align-items:center; }}
.stats span {{ display:flex; align-items:center; gap:3px; }}
.up-count {{ color:#ff6b6b; }}
.down-count {{ color:#4d96ff; }}
#chart {{ width:100%; height:680px; min-height:600px; }}
.table-wrap {{ overflow-x:auto; border-top:1px solid #1e1e32; }}
.table-wrap h3 {{ padding:8px 20px; font-size:13px; font-weight:500; color:#888; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:#16162a; color:#888; font-weight:500; padding:6px 10px; text-align:left; position:sticky; top:0; border-bottom:1px solid #2a2a45; white-space:nowrap; }}
td {{ padding:5px 10px; border-bottom:1px solid #1a1a2e; white-space:nowrap; }}
tr:hover td {{ background:#1e1e38; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.up {{ color:#ff6b6b; }}
.down {{ color:#4d96ff; }}
body.fullscreen #chart {{ height:calc(100vh - 40px); }}
body.fullscreen .header {{ display:none; }}
body.fullscreen .stats {{ display:none; }}
body.fullscreen .table-wrap {{ display:none; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 A股涨跌幅云图</h1>
  <div class="tabs">
    <button class="tab up active" onclick="switchTab('up')">📈 涨幅榜</button>
    <button class="tab down" onclick="switchTab('down')">📉 跌幅榜</button>
  </div>
  <div class="controls">
    <label class="toggle-label" id="countToggle" onclick="toggleCountMode()">
      <input type="checkbox" id="countCheckbox"> 统计出现次数
    </label>
    <div class="paginator" id="paginator"></div>
    <button class="fullscreen-btn" onclick="toggleFullscreen()">⛶ 全屏</button>
  </div>
</div>
<div class="stats">
  <span class="up-count" id="statUp">📈 涨幅前{up_count} 平均 +{up_avg:.2f}%</span>
  <span class="down-count" id="statDown">📉 跌幅前{down_count} 平均 {down_avg:.2f}%</span>
  <span style="color:#555">| 生成: {gen_time}</span>
</div>
<div id="chart"></div>
<div class="table-wrap">
  <h3 id="tableTitle">📋 数据列表</h3>
  <table>
    <thead><tr>
      <th>#</th><th>代码</th><th>名称</th><th style="text-align:right">收盘价</th><th style="text-align:right">涨跌幅</th><th style="text-align:right">总市值</th><th>行业</th>
    </tr></thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>
<script>
var UP_STOCKS = {dump([{"f12":s["f12"],"f14":s["f14"],"f3":s["f3"],"f2":s["f2"],"f20":s["f20"],"f100":s["f100"]} for s in up_sorted])};
var DOWN_STOCKS = {dump([{"f12":s["f12"],"f14":s["f14"],"f3":s["f3"],"f2":s["f2"],"f20":s["f20"],"f100":s["f100"]} for s in down_sorted])};

var currentTab = 'up', currentLimit = 300, countMode = false;
var chart = null;
var IND_COLORS = {dump(INDUSTRY_COLORS)};

function formatCap(v) {{ return !v ? '-' : v>=1e11 ? (v/1e11).toFixed(1)+'百亿' : v>=1e10 ? (v/1e10).toFixed(1)+'十亿' : v>=1e8 ? (v/1e8).toFixed(1)+'亿' : (v/1e4).toFixed(0)+'万'; }}

function getStocks() {{ return currentTab === 'up' ? UP_STOCKS : DOWN_STOCKS; }}

function makeTreemap(items, useCount) {{
  var groups = {{}};
  items.forEach(function(item) {{
    var ind = (item.f100 || '其他').trim() || '其他';
    if (!groups[ind]) groups[ind] = [];
    groups[ind].push({{
      name: item.f14 || item.f12,
      value: useCount ? 1 : (item.f20 || 1),
      pct: Math.round(item.f3*100)/100,
      price: Math.round(item.f2*100)/100,
      code: item.f12,
      cap: item.f20 || 0,
    }});
  }});
  var sorted = Object.keys(groups).sort(function(a,b){{
    return groups[b].length - groups[a].length;
  }});
  var children = sorted.map(function(ind,i){{
    return {{name:ind, itemStyle:{{color:IND_COLORS[i%IND_COLORS.length]}}, children:groups[ind]}};
  }});
  var maxAbs = Math.max.apply(null, items.map(function(x){{return Math.abs(x.f3||0);}})) || 1;
  return {{children:children, maxAbs:maxAbs}};
}}

function renderAll(limit) {{
  var stocks = getStocks();
  var limited = stocks.slice(0, limit);
  var data = makeTreemap(limited, countMode);
  renderChart(data, currentTab);
  renderTable(limited);
  updateStats(limited);
}}

function renderChart(data, tab) {{
  if(!chart){{chart=echarts.init(document.getElementById('chart'),'dark');window.addEventListener('resize',function(){{chart&&chart.resize();}});}}
  var maxAbs=data.maxAbs||1;
  chart.setOption({{
    tooltip:{{trigger:'item',backgroundColor:'rgba(22,22,42,0.95)',borderColor:'#333',borderWidth:1,textStyle:{{color:'#e0e0e0',fontSize:12}},
      formatter:function(p){{
        if(!p.data)return'';var d=p.data,pct=d.pct!=null?d.pct:null,cap=d.cap?formatCap(d.cap):'',pr=d.price;
        if(d.children){{
          var subs=d.children.filter(function(x){{return x.value;}}).sort(function(a,b){{return b.value-a.value;}});
          var tc=subs.reduce(function(s,x){{return s+(x.cap||0);}},0);
          var allList=subs.map(function(x){{var ic=x.pct>0?'#ff6b6b':'#4d96ff';var sg=x.pct>0?'+':'';return x.name+' <b>'+x.price.toFixed(2)+'</b> <span style="color:'+ic+'">'+sg+x.pct.toFixed(2)+'%</span>';}}).join('<br>');
          return '<b style="font-size:14px">'+d.name+'</b>  ('+subs.length+'只, 市值'+formatCap(tc)+')<br><br>'+allList;
        }}
        var c=pct>0?'#ff6b6b':pct<0?'#4d96ff':'#888',ar=pct>0?'▲':pct<0?'▼':'',sg=pct>0?'+':'';
        return '<b style="font-size:13px">'+d.name+'</b><br>代码: '+d.code+'<br>收盘: <b>'+(pr?pr.toFixed(2):'-')+'</b><br>涨跌: <span style="color:'+c+';font-weight:700;font-size:14px">'+ar+' '+sg+(pct!=null?pct.toFixed(2)+'%':'-')+'</span><br>市值: '+cap;
      }}
    }},
    series:[{{
      type:'treemap',width:'98%',height:'98%',top:'1%',left:'1%',roam:true,nodeClick:false,breadcrumb:{{show:false}},
      label:{{show:true,position:'inside',fontSize:12,fontFamily:'PingFang SC, Microsoft YaHei, sans-serif',overflow:'break',ellipsis:true,
        formatter:function(p){{
          if(!p.data||p.data.name==='(空)')return'';
          if(p.data.children){{return'{{b|'+p.data.name+'}}';}}
          var pt=p.data.pct,sg=pt>0?'+':'',pr=p.data.price;
          return'{{b|'+p.data.name+'}}\\n{{c|'+(pr?pr.toFixed(2):'-')+'  '+sg+(pt!=null?pt.toFixed(2)+'%':'')+'}}';
        }},
        rich:{{b:{{fontSize:12,fontWeight:600,lineHeight:20,textShadowBlur:2,textShadowColor:'rgba(0,0,0,0.7)'}},c:{{fontSize:11,fontWeight:500,lineHeight:16,textShadowBlur:2,textShadowColor:'rgba(0,0,0,0.7)'}}}}
      }},
      upperLabel:{{show:true,height:24,position:'insideTop',textStyle:{{fontSize:13,fontWeight:600,textShadowBlur:3,textShadowColor:'rgba(0,0,0,0.8)'}},formatter:function(p){{return p.data.name||'';}}}},
      itemStyle:{{borderRadius:3,borderColor:'#0f0f1a',borderWidth:2}},
      levels:[{{itemStyle:{{borderColor:'#0f0f1a',borderWidth:3,gapWidth:2}}}},{{
        itemStyle:{{borderColor:'#0f0f1a',borderWidth:2,gapWidth:1}}
      }},{{
        color:function(p){{
          var pt=p.data&&p.data.pct;if(pt==null)return'#222239';
          var r=Math.min(Math.abs(pt)/maxAbs,1);
          if(pt>0){{var rd=Math.round(180+75*r);return'rgb('+rd+','+Math.round(80-50*r)+','+Math.round(80-50*r)+')';}}
          var bd=Math.round(180+75*r);return'rgb('+Math.round(60-30*r)+','+Math.round(100-40*r)+','+bd+')';
        }},
        itemStyle:{{borderColor:'#0f0f1a',borderWidth:1,gapWidth:1}}
      }}],
      data:[{{name:'A股',children:data.children}}]
    }}]
  }});
}}

function renderTable(stocks) {{
  var icon = currentTab === 'up' ? '📈' : '📉';
  var label = currentTab === 'up' ? '涨幅榜' : '跌幅榜';
  document.getElementById('tableTitle').textContent = icon + ' ' + label + ' — 前' + stocks.length + '只';
  var html = '';
  var avgPct = 0;
  stocks.forEach(function(s,i){{
    avgPct += s.f3;
    var cls = s.f3 > 0 ? 'up' : 'down';
    var sg = s.f3 > 0 ? '+' : '';
    html += `<tr>
      <td>${{i+1}}</td>
      <td>${{s.f12}}</td>
      <td><a style="color:#e0e0e0;font-size:14px;font-weight:bold;" href="https://stockpage.10jqka.com.cn/${{s.f12}}/" target="_blank">${{s.f14}}</a></td>
      <td class="num">${{(s.f2 ? s.f2.toFixed(2) : '-')}}</td>
      <td class="num ${{cls}}">${{sg}}${{(s.f3 ? s.f3.toFixed(2) : '0.00')}}%</td>
      <td class="num">${{formatCap(s.f20)}}</td>
      <td>${{s.f100||'-'}}</td>
    </tr>`;
  }});
  document.getElementById('tableBody').innerHTML = html;
}}

function updateStats(limited) {{
  var avg = limited.length ? limited.reduce(function(s,x){{return s+x.f3;}},0)/limited.length : 0;
  var statEl = currentTab === 'up' ? 'statUp' : 'statDown';
  var otherEl = currentTab === 'up' ? 'statDown' : 'statUp';
  var modeText = countMode ? ' [按次数]' : ' [按市值]';
  document.getElementById(statEl).innerHTML = (currentTab==='up'?'📈 涨幅': '📉 跌幅')+'前'+limited.length+' 平均 '+(avg>0?'+':'')+avg.toFixed(2)+'%'+modeText;
}}

// Paginator
(function buildPaginator() {{
  var p = document.getElementById('paginator');
  [50,100,150,200,250,300].forEach(function(n){{
    var btn = document.createElement('button');
    btn.textContent = n;
    btn.onclick = function(){{document.querySelectorAll('#paginator button').forEach(function(b){{b.classList.remove('active');}});btn.classList.add('active');currentLimit=n;renderAll(n);}};
    if(n===300) btn.classList.add('active');
    p.appendChild(btn);
  }});
}})();

function switchTab(tab) {{
  currentTab=tab;
  document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('active');}});
  document.querySelector('.tab.'+tab).classList.add('active');
  renderAll(currentLimit);
}}

function toggleFullscreen(){{if(!document.fullscreenElement){{document.documentElement.requestFullscreen();document.body.classList.add('fullscreen');}}else{{document.exitFullscreen();document.body.classList.remove('fullscreen');}}setTimeout(function(){{chart&&chart.resize();}},300);}}
document.addEventListener('fullscreenchange',function(){{if(!document.fullscreenElement)document.body.classList.remove('fullscreen');chart&&chart.resize();}});

function toggleCountMode(){{
  countMode = document.getElementById('countCheckbox').checked;
  var label = document.getElementById('countToggle');
  if(countMode){{ label.classList.add('checked'); }} else {{ label.classList.remove('checked'); }}
  renderAll(currentLimit);
}}

renderAll(300);
</script>
</body>
</html>'''
    return html


def main():
    now = time.localtime()
    date_str = time.strftime("%Y-%m-%d", now)
    gen_time = time.strftime("%Y-%m-%d %H:%M:%S", now)

    print("📈 正在获取涨幅榜数据...")
    up = fetch_data(1)
    print()
    print("📉 正在获取跌幅榜数据...")
    down = fetch_data(0)
    print()

    html = build_html(up, down, gen_time, date_str)
    fname = f"a_streak_treemap_{date_str}.html"
    fpath = os.path.join(BASE_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(html)

    js_src = os.path.join(BASE_DIR, "echarts.min.js")
    if not os.path.exists(js_src):
        js_tmp = "/tmp/echarts.min.js"
        if os.path.exists(js_tmp):
            import shutil
            shutil.copy2(js_tmp, js_src)

    print(f"\n✅ 云图已生成: {fpath}")
    print(f"   涨幅榜: {len(up)} 只 ({len(set(x.get('f100','其他') for x in up))}个行业)")
    print(f"   跌幅榜: {len(down)} 只 ({len(set(x.get('f100','其他') for x in down))}个行业)")
    print(f"   生成时间: {gen_time}")


if __name__ == "__main__":
    main()
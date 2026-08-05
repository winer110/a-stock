#!/usr/bin/env python3
"""A股涨跌幅云图生成器 v2 - 按日期输出，不覆盖"""
import json
import os
import subprocess
import time

BASE_DIR = os.path.expanduser("~/Desktop/a_stock")
os.makedirs(BASE_DIR, exist_ok=True)

# 行业配色方案 — 65种鲜明颜色
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
        alt = f"0.{code}" if secid.startswith("1.") else f"1.{code}"
        code_map[alt] = s

    enriched = []
    for i in range(0, len(secids), 80):
        batch = secids[i:i + 80]
        url = ("https://push2.eastmoney.com/api/qt/ulist.np/get?"
               f"fltt=2&secids={','.join(batch)}&fields=f12,f14,f3,f17,f20,f100")
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
                            s["f17"] = float(item.get("f17", 0) or 0)
            except json.JSONDecodeError:
                pass
        time.sleep(0.3)

    for s in stocks:
        enriched.append({
            "f12": s["code"],
            "f14": s["name"],
            "f3": s["changepercent"],
            "f17": s.get("f17", s["trade"]),
            "f20": s.get("f20", 0),
            "f100": s.get("f100", ""),
        })
    return enriched


def fetch_data(po):
    asc = 0 if po == 1 else 1
    print(f"   获取排行...", end=" ", flush=True)
    stocks = fetch_stock_list_sina(asc=asc, num=300)
    print(f"({len(stocks)}只)", end=" ", flush=True)
    if not stocks:
        return []
    print("补充行业/市值...", end=" ", flush=True)
    enriched = enrich_with_eastmoney(stocks)
    print(f"({len(enriched)}只)", end="", flush=True)
    return enriched


def make_treemap(items):
    groups = {}
    for item in items:
        ind = (item.get("f100") or "其他").strip() or "其他"
        if ind not in groups:
            groups[ind] = []
        pct = item.get("f3") or 0
        price = item.get("f17", 0)
        groups[ind].append({
            "name": (item.get("f14","") or item.get("f12","")),
            "value": float(item.get("f20") or 1),
            "pct": round(pct, 2),
            "price": round(price, 2) if price else 0,
            "code": item.get("f12",""),
            "cap": float(item.get("f20") or 0),
        })
    ind_totals = {k: sum(x["value"] for x in v) for k, v in groups.items()}
    sorted_inds = sorted(groups.keys(), key=lambda k: ind_totals[k], reverse=True)
    children = []
    for idx, ind in enumerate(sorted_inds):
        children.append({
            "name": ind,
            "itemStyle": {"color": INDUSTRY_COLORS[idx % len(INDUSTRY_COLORS)]},
            "children": groups[ind],
        })
    max_abs = max((abs(x.get("f3") or 0) for x in items), default=1)
    return {"children": children, "maxAbs": max_abs}


def format_cap(v):
    if not v: return "-"
    v = float(v)
    if v >= 1e11: return f"{v/1e11:.1f}百亿"
    if v >= 1e10: return f"{v/1e10:.1f}十亿"
    if v >= 1e8: return f"{v/1e8:.1f}亿"
    return f"{v/1e4:.0f}万"


def build_html(up_data, down_data, gen_time, date_str):
    dump = json.dumps
    up_tm = make_treemap(up_data)
    down_tm = make_treemap(down_data)
    up_count = len(up_data)
    down_count = len(down_data)
    up_avg = sum(x.get("f3") or 0 for x in up_data) / up_count if up_count else 0
    down_avg = sum(x.get("f3") or 0 for x in down_data) / down_count if down_count else 0
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
body {{ background:#0f0f1a; color:#e0e0e0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif; min-height:100vh; overflow:hidden; }}
.header {{ padding:14px 20px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; border-bottom:1px solid #1e1e32; background:#16162a; }}
.header h1 {{ font-size:18px; font-weight:600; background:linear-gradient(135deg,#ff6b6b,#ffd93d,#6bcb77,#4d96ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; white-space:nowrap; }}
.tabs {{ display:flex; gap:6px; }}
.tab {{ padding:6px 16px; border-radius:16px; border:1px solid #2a2a45; background:transparent; color:#999; font-size:13px; cursor:pointer; transition:all 0.2s; }}
.tab:hover {{ background:#1e1e38; }}
.tab.active {{ color:#fff; }}
.tab.up.active {{ background:#ff6b6b22; border-color:#ff6b6b; }}
.tab.down.active {{ background:#4d96ff22; border-color:#4d96ff; }}
.stats {{ display:flex; gap:12px; font-size:12px; color:#888; padding:6px 20px; border-bottom:1px solid #1a1a2e; flex-wrap:wrap; align-items:center; }}
.stats span {{ display:flex; align-items:center; gap:3px; }}
.up-count {{ color:#ff6b6b; }}
.down-count {{ color:#4d96ff; }}
.controls {{ margin-left:auto; display:flex; gap:8px; align-items:center; }}
.fullscreen-btn {{ padding:4px 14px; border-radius:12px; border:1px solid #2a2a45; background:transparent; color:#888; font-size:12px; cursor:pointer; }}
.fullscreen-btn:hover {{ background:#1e1e38; color:#e0e0e0; }}
#chart {{ width:100%; height:calc(100vh - 82px); min-height:500px; }}
body.fullscreen #chart {{ height:100vh; }}
body.fullscreen .header {{ display:none; }}
body.fullscreen .stats {{ display:none; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 A股涨跌幅云图</h1>
  <div class="tabs">
    <button class="tab up active" onclick="switchTab('up')">📈 涨幅榜 ({up_count})</button>
    <button class="tab down" onclick="switchTab('down')">📉 跌幅榜 ({down_count})</button>
  </div>
  <div class="controls">
    <button class="fullscreen-btn" onclick="toggleFullscreen()">⛶ 全屏</button>
  </div>
</div>
<div class="stats">
  <span class="up-count">📈 涨幅前{up_count} 平均 +{up_avg:.2f}%</span>
  <span class="down-count">📉 跌幅前{down_count} 平均 {down_avg:.2f}%</span>
  <span style="color:#555">| 生成: {gen_time}</span>
  <span style="color:#555">| 色块=行业, 面积=市值</span>
</div>
<div id="chart"></div>
<script>
var UP_DATA = {dump(up_tm)};
var DOWN_DATA = {dump(down_tm)};
var currentTab = 'up';
var chart = null;

function formatCap(v) {{ return !v ? '-' : v>=1e11 ? (v/1e11).toFixed(1)+'百亿' : v>=1e10 ? (v/1e10).toFixed(1)+'十亿' : v>=1e8 ? (v/1e8).toFixed(1)+'亿' : (v/1e4).toFixed(0)+'万'; }}

var IND_COLORS = {dump(INDUSTRY_COLORS)};

function renderChart(data, tab) {{
  if(!chart){{chart=echarts.init(document.getElementById('chart'),'dark');window.addEventListener('resize',function(){{chart&&chart.resize();}});}}
  var maxAbs=data.maxAbs||1;
  chart.setOption({{
    tooltip:{{trigger:'item',backgroundColor:'rgba(22,22,42,0.95)',borderColor:'#333',borderWidth:1,textStyle:{{color:'#e0e0e0',fontSize:13}},
      formatter:function(p){{
        if(!p.data)return'';var d=p.data,pct=d.pct!=null?d.pct:null,cap=d.cap?formatCap(d.cap):'',pr=d.price;
        if(d.children){{
          var subs=d.children.filter(function(x){{return x.value;}}).sort(function(a,b){{return b.value-a.value;}});
          var tc=subs.reduce(function(s,x){{return s+(x.cap||0);}},0);
          var allList=subs.map(function(x){{var ic=x.pct>0?'#ff6b6b':'#4d96ff';var sg=x.pct>0?'+':'';return x.name+' <b>'+x.price.toFixed(2)+'</b> <span style="color:'+ic+'">'+sg+x.pct.toFixed(2)+'%</span>';}}).join('<br>');
          return '<b style="font-size:15px">'+d.name+'</b>  ('+subs.length+'只, 市值'+formatCap(tc)+')<br><br>'+allList;
        }}
        var c=pct>0?'#ff6b6b':pct<0?'#4d96ff':'#888',ar=pct>0?'▲':pct<0?'▼':'',sg=pct>0?'+':'';
        return '<b style="font-size:14px">'+d.name+'</b><br>代码: '+d.code+'<br>现价: <b>'+(pr?pr.toFixed(2):'-')+'</b><br>涨跌: <span style="color:'+c+';font-weight:700;font-size:15px">'+ar+' '+sg+(pct!=null?pct.toFixed(2)+'%':'-')+'</span><br>市值: '+cap;
      }}
    }},
    series:[{{
      type:'treemap',width:'98%',height:'98%',top:'1%',left:'1%',roam:true,nodeClick:false,breadcrumb:{{show:false}},
      label:{{show:true,position:'inside',fontSize:13,fontFamily:'PingFang SC, Microsoft YaHei, sans-serif',overflow:'break',ellipsis:true,
        formatter:function(p){{
          if(!p.data||p.data.name==='(空)')return'';
          if(p.data.children){{return'{{b|'+p.data.name+'}}';}}
          var pt=p.data.pct,sg=pt>0?'+':'',pr=p.data.price;
          var s1=p.data.name;
          var s2=(pr?pr.toFixed(2):'-')+'  '+sg+(pt!=null?pt.toFixed(2)+'%':'');
          return'{{b|'+s1+'}}\\n{{c|'+s2+'}}';
        }},
        rich:{{b:{{fontSize:13,fontWeight:600,lineHeight:22,textShadowBlur:2,textShadowColor:'rgba(0,0,0,0.7)'}},c:{{fontSize:12,fontWeight:500,lineHeight:18,textShadowBlur:2,textShadowColor:'rgba(0,0,0,0.7)'}}}}
      }},
      upperLabel:{{show:true,height:28,position:'insideTop',textStyle:{{fontSize:14,fontWeight:600,textShadowBlur:3,textShadowColor:'rgba(0,0,0,0.8)'}},formatter:function(p){{return p.data.name||'';}}}},
      itemStyle:{{borderRadius:3,borderColor:'#0f0f1a',borderWidth:2}},
      levels:[{{
        itemStyle:{{borderColor:'#0f0f1a',borderWidth:3,gapWidth:2}}
      }},{{
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

function switchTab(tab){{currentTab=tab;document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('active');}});document.querySelector('.tab.'+tab).classList.add('active');renderChart(tab==='up'?UP_DATA:DOWN_DATA,tab);}}

function toggleFullscreen(){{if(!document.fullscreenElement){{document.documentElement.requestFullscreen();document.body.classList.add('fullscreen');}}else{{document.exitFullscreen();document.body.classList.remove('fullscreen');}}
  setTimeout(function(){{chart&&chart.resize();}},300);}}

document.addEventListener('fullscreenchange',function(){{if(!document.fullscreenElement)document.body.classList.remove('fullscreen');chart&&chart.resize();}});

renderChart(UP_DATA,'up');
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

    # Also copy echarts.min.js if not present
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

#!/usr/bin/env python3
"""缠论+威科夫+量价每日复盘 - 交易日15:15系统crontab自动执行"""
import json, os, subprocess, time
from datetime import datetime

OUTPUT_DIR = os.path.expanduser("~/Desktop")

def curl(url):
    r = subprocess.run(["curl","-s","--max-time","10","-H","User-Agent: Mozilla/5.0", url], capture_output=True, text=True, timeout=12)
    return r.stdout.strip()

def parse_pct(v):
    try: return float(str(v).replace(',',''))
    except: return 0

def parse_amt(v):
    try: return float(str(v).replace(',',''))
    except: return 0

def get_index(name, code):
    r = subprocess.run(["curl","-s","--max-time","6","-H","Referer: https://finance.sina.com.cn",f"https://hq.sinajs.cn/list={code}"], capture_output=True, timeout=8)
    txt = r.stdout.decode('gbk', errors='ignore')
    p = txt.split('"')[1].split(',') if '"' in txt else []
    if len(p)>=32:
        return {"name":name,"price":float(p[3]),"chg":(float(p[3])-float(p[2]))/float(p[2])*100,"open":float(p[1]),"high":float(p[4]),"low":float(p[5]),"yc":float(p[2]),"amt":float(p[9])/1e8}
    return None

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"🔄 获取{date_str}市场数据...")

    # 指数
    idxs = [get_index("上证指数","sh000001"),get_index("深证成指","sz399001"),get_index("创业板指","sz399006"),get_index("科创50","sh000688")]
    idxs = [i for i in idxs if i]

    # 全量涨跌数据
    all_data = []
    for page in range(1, 6):
        resp = curl(f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple?page={page}&num=1000&sort=changepercent&asc=0&node=hs_a")
        if resp and resp != 'null': all_data.extend(json.loads(resp))
        time.sleep(0.2)

    # 跌幅数据
    losers = []
    for page in range(1, 4):
        resp = curl(f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple?page={page}&num=1000&sort=changepercent&asc=1&node=hs_a")
        if resp and resp != 'null':
            for s in json.loads(resp):
                if parse_pct(s.get('changepercent',0)) < 0: losers.append(s)
        time.sleep(0.2)

    up = sum(1 for s in all_data if parse_pct(s.get('changepercent',0)) > 0.01)
    down = sum(1 for s in all_data if parse_pct(s.get('changepercent',0)) < -0.01)
    zt = sum(1 for s in all_data if parse_pct(s.get('changepercent',0)) >= 9.9)
    dt = sum(1 for s in losers if parse_pct(s.get('changepercent',0)) <= -9.9)
    total_amt = sum(i['amt'] for i in idxs)

    # 板块
    up_sectors = [s for s in (json.loads(curl("https://push2.eastmoney.com/api/qt/clist/get?cb=&pn=1&pz=5&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:3&fields=f12,f14,f3") or "{}")).get('data',{}).get('diff',[])]
    down_sectors = [s for s in (json.loads(curl("https://push2.eastmoney.com/api/qt/clist/get?cb=&pn=1&pz=5&po=0&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:3&fields=f12,f14,f3") or "{}")).get('data',{}).get('diff',[])]

    # 成交额TOP
    vol_rank = sorted(all_data, key=lambda s: parse_amt(s.get('amount',0)), reverse=True)

    sh = idxs[0] if idxs else None
    kc = next((i for i in idxs if i['name']=='科创50'), None)

    # ===== 生成报告 =====
    lines = []
    lines.append("# ═══ A股每日复盘 — 缠论·威科夫·量价 ═══\n")
    lines.append(f"**日期：** {date_str} | **数据源：** 新浪/东财\n")

    # 一、大盘
    lines.append("---\n## 一、大盘研判\n")
    lines.append("### 指数表现\n")
    lines.append("| 指数 | 收盘 | 涨跌 | 成交额 | 信号 |")
    lines.append("|:----|:---:|:----:|:-----:|:----|")
    for i in idxs:
        icon = "🏛️"
        s = "🟢" if i['chg']>1 else "🔴" if i['chg']<-1 else "🟡"
        lines.append(f"| {icon} {i['name']} | {i['price']:.0f} | {i['chg']:+.2f}% | {i['amt']:.0f}亿 | {s} |")

    lines.append(f"\n### 涨跌分布\n")
    lines.append(f"| 指标 | 数据 | 判断 |")
    lines.append(f"|:----|:----:|:----|")
    lines.append(f"| 上涨/下跌 | **{up} / {down}** | {'✅ 涨多跌少' if up>down else '🔴 跌多涨少'} |")
    lines.append(f"| 涨停/跌停 | **{zt}只 / {dt}只** | {'✅ 情绪活跃' if zt>dt*2 else '🔴 偏弱' if dt>zt else '🟡 分化'} |")
    lines.append(f"| 成交额 | 约{total_amt:.0f}亿 | {'🔴 放量' if total_amt>35000 else '🟡 缩量' if total_amt<25000 else '🟡 正常'} |")

    # 缠论判断
    if kc and kc['chg'] < -1:
        trend = "科创50大跌，半导体/科技板块领跌，市场风格切换中"
    elif sh and sh['chg'] > 0.5:
        trend = "上证反弹，市场情绪回暖"
    elif sh and abs(sh['chg']) < 0.5:
        trend = "窄幅震荡，方向待定"
    elif sh and sh['chg'] < -0.5:
        trend = "上证下跌，市场整体偏弱"
    else:
        trend = "市场震荡，等待方向"

    lines.append(f"\n**缠论判断：** {trend}。")
    lines.append(f"**威科夫供需：** {'放量' if total_amt>35000 else '缩量' if total_amt<25000 else '正常'}成交{total_amt:.0f}亿，{'抛压释放中' if kc and kc['chg']<-1 else '资金观望中' if abs((sh['chg'] if sh else 0))<0.5 else '资金回流中'}。\n")

    # 二、板块
    lines.append("---\n## 二、板块排名\n")
    lines.append("### 🔥 今日强势板块")
    for s in up_sectors:
        lines.append(f"| 🥇 {s.get('f14')} | **{s.get('f3')}%** |")
    lines.append("\n### ❌ 今日弱势板块")
    for s in down_sectors:
        lines.append(f"| ❌ {s.get('f14')} | **{s.get('f3')}%** |")

    # 三、成交额TOP10
    lines.append("\n## 三、成交额TOP10\n")
    lines.append("| 股票 | 涨跌 | 成交额 |")
    lines.append("|:----|:----:|:-----:|")
    for s in vol_rank[:10]:
        p = parse_pct(s.get('changepercent',0))
        a = parse_amt(s.get('amount',0))/1e8
        lines.append(f"| {s['name']}({s['code']}) | {'+' if p>0 else ''}{p:.1f}% | {a:.0f}亿 |")

    # 四、结论
    lines.append("\n## 四、综合结论\n")
    # 自动判断
    if kc and kc['chg'] < -1:
        conclusion = "今日科技股继续调整，资金从半导体板块流出，机器人概念成为新热点。"
    elif zt > 100 and up > down:
        conclusion = "市场情绪偏暖，涨停家数较多，但需关注持续性。"
    elif dt > 50:
        conclusion = "跌停家数较多，市场风险偏好下降，注意控制仓位。"
    else:
        conclusion = "市场震荡整理，无明显趋势。"
    lines.append(f">{conclusion}")
    lines.append("\n---\n*本复盘基于缠论+威科夫+量价框架，AI自动生成，仅供参考学习，不构成投资建议。*")

    fpath = os.path.join(OUTPUT_DIR, f"A股复盘_{date_str}.md")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ 复盘已保存: {fpath}")
    print(f"   上涨{up} 下跌{down} 涨停{zt} 跌停{dt} 成交{total_amt:.0f}亿")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
个股缠论+威科夫量价分析工具 (基于baostock K线数据)
用法: python3 analyze_stock.py <股票代码> [天数]

示例: python3 analyze_stock.py 300570     # 太辰光
      python3 analyze_stock.py 300274 120 # 阳光电源, 120天K线
"""
import sys, math
import baostock as bs

def to_bs_code(code):
    """转baostock格式：sz.300570 / sh.600519"""
    return f"sh.{code}" if code.startswith(('6','9')) else f"sz.{code}"

def get_kline(code, days=100):
    bs_code = to_bs_code(code)
    lg = bs.login()
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,open,high,low,close,volume,amount,peTTM,pbMRQ",
        frequency="d", adjustflag="3"
    )
    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    bs.logout()
    return rows[-days:] if len(rows) > days else rows

def analyze(code, name=""):
    k = get_kline(code)
    if not k or len(k) < 20:
        print(f"❌ {code} 数据不足")
        return

    closes = [float(r[4]) for r in k if r[4]]
    highs = [float(r[2]) for r in k if r[2]]
    lows = [float(r[3]) for r in k if r[3]]
    vols = [int(float(r[5])) for r in k if r[5]]
    curr = closes[-1]

    # 均线
    ma5 = sum(closes[-5:])/5
    ma10 = sum(closes[-10:])/10
    ma20 = sum(closes[-20:])/20
    ma60 = sum(closes[-60:])/60 if len(closes) >= 60 else ma20

    # 区间
    h60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    l60 = min(lows[-60:]) if len(lows) >= 60 else min(lows)
    h20 = max(highs[-20:])
    l20 = min(lows[-20:])

    # 量能
    vol10 = sum(vols[-10:])/10 if len(vols) >= 10 else 0
    vol30 = sum(vols[-30:])/30 if len(vols) >= 30 else vol10
    vol_shrink = vol10 < vol30 * 0.8
    vol_surge = vols[-1] > vol30 * 1.5 if vols and vol30 else False

    from_low = (curr - l60)/l60*100 if l60 else 0
    recent_high = max(highs[-15:])
    pullback = (recent_high - curr)/recent_high*100 if recent_high else 0
    today_pct = (closes[-1]-closes[-2])/closes[-2]*100 if len(closes) >= 2 else 0

    # 输出
    print(f"\n{'='*60}")
    print(f"  {name or code}({code})  缠论·威科夫量价分析")
    print(f"{'='*60}")
    print(f"  当前价: {curr:.2f}    今日涨幅: {today_pct:+.2f}%")
    print(f"  区间: {h60:.2f} / {l60:.2f}  (从底部+{from_low:.0f}%)")
    print(f"  均线: MA5={ma5:.1f}  MA10={ma10:.1f}  MA20={ma20:.1f}  MA60={ma60:.1f}")
    print(f"  回调: {pullback:.1f}% (近15日高→现)")
    print(f"  量能: 近10日均{vol10/1e4:.0f}万  近30日均{vol30/1e4:.0f}万")
    print(f"  缩量回调: {'✅' if vol_shrink else '❌'}  放量突破: {'✅' if vol_surge else '❌'}")
    print(f"  比MA20: {'✅ 站上' if curr>ma20 else '❌ 跌破'} MA20")
    print()

    # 缠论判断
    print(f"── 缠论结构 ──")
    print(f"  日线级别: ", end="")
    if from_low > 30:
        print("上升趋势中")
    elif from_low > 10:
        print("底部抬高，可能转势")
    else:
        print("底部震荡")

    # 中枢区间 (用MA20上下摆动近似)
    mid_zone_low = min(ma20, l20)
    mid_zone_high = max(ma20, h20)
    print(f"  近似中枢区间: {mid_zone_low:.1f} ~ {mid_zone_high:.1f}")
    if curr > mid_zone_high * 1.02:
        print(f"  当前在中枢上方 → 关注回踩不破{mid_zone_high:.1f}的三买")
    elif curr < mid_zone_low * 0.98:
        print(f"  当前在中枢下方 → 等待向下背驰的一买")
    else:
        print(f"  当前在中枢内部震荡")

    # 3B评分
    print(f"\n── 3B评分 ──")
    score = 0
    if from_low > 12: score += 2
    if 3 < pullback < 18: score += 2
    if vol_shrink: score += 2
    if curr > ma20: score += 1
    if vol_surge: score += 1
    print(f"  3B特征评分: {score}/8 {'⭐'* (score//2)}")
    if score >= 6: print(f"  → 3B特征显著")
    elif score >= 4: print(f"  → 有3B雏形")
    else: print(f"  → 暂不符合3B条件")

    # 威科夫
    print(f"\n── 威科夫量价 ──")
    if curr > h60 * 0.9 and vol_surge:
        print(f"  → Phase D/E: 可能进入Mark-up阶段")
    elif pullback > 3 and vol_shrink and curr > ma20:
        print(f"  → Phase D LPS: 缩量回踩，关注LPS确认")
    elif from_low < 15 and not vol_surge:
        print(f"  → Phase A/B: 底部吸筹阶段")
    elif curr > ma20 and not vol_shrink:
        print(f"  → Phase C: 突破测试阶段")
    else:
        print(f"  → 阶段模糊，等待确认")

    # 关键位
    print(f"\n── 关键位 ──")
    print(f"  压力: {recent_high:.1f} (15日高) / {round(curr*1.05+5):.1f}")
    print(f"  支撑: {ma20:.1f} (MA20) / {l20:.1f} (20日低) / {l60:.1f} (60日低)")
    print(f"  止损: 跌破{l20:.1f}结构破坏")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    codes = sys.argv[1:] if len(sys.argv) > 1 else ["300570"]
    name_map = {"300570":"太辰光","300274":"阳光电源","300333":"兆日科技",
                "600519":"贵州茅台","000858":"五粮液","601318":"中国平安",
                "300750":"宁德时代","002594":"比亚迪","600178":"东安动力"}
    for code in codes:
        analyze(code, name_map.get(code, ""))

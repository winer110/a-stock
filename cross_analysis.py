#!/usr/bin/env python3
"""多日股票数据交叉分析

从本地 sina_stocks_1_YYYY-MM-DD.json 文件中读取股票行情数据，
按 code 分组聚合，筛选至少出现 (文件数-3) 次的高频股票，输出涨跌幅明细表。

用法:
    python3 cross_analysis.py           # 生成 HTML 报告并自动打开
"""

import json
import os
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PREFIX = "sina_stocks_1_"
# THRESHOLD 改为动态计算：文件数 - 3，在 main() 中赋值
OUTPUT_HTML = os.path.join(DATA_DIR, "cross_report.html")


def load_data():
    files = sorted(
        [f for f in os.listdir(DATA_DIR) if f.startswith(FILE_PREFIX) and f.endswith("_1501.json")],
        reverse=True,
    )
    if not files:
        print("未找到数据文件", file=sys.stderr)
        sys.exit(1)

    all_data = {}
    for f in files:
        date_str = f.replace(FILE_PREFIX, "").replace(".json", "")
        fp = os.path.join(DATA_DIR, f)
        with open(fp) as fh:
            rows = json.load(fh)
        all_data[date_str] = {
            r["code"]: {"name": r["name"], "changepercent": r["changepercent"]}
            for r in rows
        }
    return all_data


def analyze(all_data, threshold):
    dates = sorted(all_data.keys())
    N = len(dates)

    code_set = set()
    for d in dates:
        code_set |= set(all_data[d].keys())

    results = []
    for code in code_set:
        present = [d for d in dates if code in all_data[d]]
        name = all_data[present[0]][code]["name"]
        ch = {d: all_data[d][code]["changepercent"] for d in present}
        vals = list(ch.values())
        results.append({
            "code": code,
            "name": name,
            "count": len(present),
            "changes": ch,
            "volatility": round(max(vals) - min(vals), 2),
            "cumulative": round(sum(vals), 2),
            "missing": [d for d in dates if d not in present],
        })

    results.sort(key=lambda x: x["count"], reverse=True)
    return dates, results


def filter_by_threshold(results, threshold):
    return [r for r in results if r["count"] >= threshold]


def output_terminal(dates, results, threshold):
    N = len(dates)
    print(f"文件数: {N}, 日期范围: {dates[0]} ~ {dates[-1]}")
    print(f"筛选条件: 至少在 {threshold} 个日期出现\n")

    header = "| 代码 | 名称 | 出现 | " + " | ".join(dates) + " | 累计% | 波幅% |"
    sep = "|---" * (4 + N) + "|"
    print(header)
    print(sep)

    for r in results:
        vals = []
        for d in dates:
            if d in r["changes"]:
                v = r["changes"][d]
                vals.append(f"▲{v:.1f}" if v > 0 else f"▼{v:.1f}" if v < 0 else "0.0")
            else:
                vals.append("-")
        sign = "▲" if r["cumulative"] > 0 else "▼" if r["cumulative"] < 0 else ""
        print(
            f"| {r['code']} | {r['name']} | {r['count']}/{N} | "
            + " | ".join(vals)
            + f" | {sign}{r['cumulative']:.1f} | {r['volatility']:.1f} |"
        )

    print(f"\n符合条件: {len(results)} 只")

    missed = [r for r in results if r["count"] == threshold]
    if missed:
        print(f"\n仅出现 {threshold} 天的股票:")
        for r in missed:
            print(f"  {r['code']} {r['name']}: 缺 {r['missing']}")


def output_html(dates, all_results, threshold):
    import json
    N = len(dates)

    def color_class(v): return "up" if v > 0 else ("down" if v < 0 else "zero")
    def sign(v): return "▲" if v > 0 else ("▼" if v < 0 else "")

    filtered = filter_by_threshold(all_results, threshold)
    max_count = max(r["count"] for r in all_results) if all_results else N

    # 构建初始表格
    rows_html = ""
    for r in filtered:
        vals_html = ""
        for d in dates:
            if d in r["changes"]:
                v = r["changes"][d]
                vals_html += f'<td class="{color_class(v)}">{sign(v)}{v:.1f}</td>'
            else:
                vals_html += '<td class="na">-</td>'
        c = r["cumulative"]
        rows_html += f"""<tr>
<td class="code">{r['code']}</td>
<td><a href="https://stockpage.10jqka.com.cn/{r['code']}/" target="_blank" style="color:#333;text-decoration:none;font-weight:bold;">{r['name']}</a></td>
<td class="center">{r['count']}/{N}</td>
{vals_html}
<td class="{color_class(c)}">{sign(c)}{c:.1f}</td>
<td>{r['volatility']:.1f}</td>
</tr>
"""

    # 序列化全量数据
    all_json = json.dumps(all_results, ensure_ascii=False)
    dates_json = json.dumps(dates, ensure_ascii=False)

    # 构建下拉框选项
    select_options = "\n".join(
        f'<option value="{i}" {"selected" if i == threshold else ""}>{i}</option>'
        for i in range(1, max_count + 1)
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>股票交叉分析报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f7fa; color: #333; padding: 24px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
.header {{ background: #fff; border-radius: 12px; padding: 20px 28px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
.header h1 {{ font-size: 20px; margin-bottom: 8px; }}
.header .meta {{ color: #888; font-size: 13px; line-height: 1.8; }}
.slider-wrap {{ display:flex; align-items:center; gap:12px; margin-top:10px; }}
.slider-wrap .slider-label {{ color:#666; font-size:13px; white-space:nowrap; }}
.toggle-label {{ display:inline-flex; align-items:center; gap:4px; color:#666; font-size:13px; cursor:pointer; user-select:none; margin-left:16px; }}
.table-wrap {{ background: #fff; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.06); max-height: 100vh; overflow: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }}
th {{ background: #f8f9fb; color: #555; font-weight: 600; padding: 10px 8px; border-bottom: 2px solid #e8e8e8; text-align: left; position: sticky; top: 0; z-index: 1; }}
th.center {{ text-align: center; }}
td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; }}
td.center {{ text-align: center; }}
td.code {{ font-family: "SF Mono", "Menlo", "Consolas", monospace; }}
tr:hover {{ background: #f8faff; }}
.up {{ color: #e03131; font-weight: 600; }}
.down {{ color: #2f9e44; font-weight: 600; }}
.zero {{ color: #999; }}
.na {{ color: #ccc; text-align: center; }}
.footer {{ margin-top: 20px; color: #888; font-size: 13px; }}
.missing-section {{ background: #fff; border-radius: 12px; padding: 20px 28px; margin-top: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
.missing-section h2 {{ font-size: 16px; margin-bottom: 12px; color: #555; }}
.missing-item {{ font-size: 13px; line-height: 2; color: #666; }}

thead th {{
    position: sticky;
    top: 0;
    z-index: 3;
    background-color: #e9ecef;
    border-bottom: 2px solid #999;
}}
/* 固定第一列 */
th:first-child,
td:first-child {{
    position: sticky;
    left: 0;
    z-index: 2;
    background-color: #f9f9f9;  /* 与背景区分，避免透明 */
    min-width: 120px;
}}

/* 固定第二列 */
th:nth-child(2),
td:nth-child(2) {{
    position: sticky;
    left: 120px;               /* 等于第一列的宽度（min-width） */
    z-index: 2;
    background-color: #f9f9f9;
    min-width: 150px;
}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>股票多日交叉分析报告</h1>
<div class="meta" id="metaInfo">
日期范围: {dates[0]} ~ {dates[-1]} | 数据文件: {N} 个 | 筛选条件: 至少出现 <span id="threshVal">{threshold}</span> 天 | 符合条件: <span id="matchCount">{len(filtered)}</span> 只
</div>
<div class="slider-wrap">
  <span class="slider-label">筛选阈值（出现次数）:</span>
  <select id="threshSelect" onchange="onThreshChange()" style="padding:4px 8px;border:1px solid #ddd;border-radius:6px;font-size:14px;color:#4d96ff;font-weight:700;cursor:pointer;">
{select_options}
  </select>
  <span class="slider-label">/ {max_count} 天</span>
  <label class="toggle-label"><input type="checkbox" id="toggleMissing" onchange="onThreshChange()"> 缺勤明细</label>
</div>
</div>
<div class="table-wrap" id="tableWrap">
<table>
<thead>
<tr>
<th>代码</th>
<th>名称</th>
<th class="center">出现</th>
{"".join(f'<th class="center">{d}</th>' for d in dates)}
<th>累计%</th>
<th>波幅%</th>
</tr>
</thead>
<tbody id="tableBody">
{rows_html}
</tbody>
</table>
</div>
<div class="missing-section" id="missingSection"></div>
<div class="footer" id="footerInfo">生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")} | 共 {len(filtered)} 只股票</div>
</div>
<script>
var ALL_DATA = {all_json};
var DATES = {dates_json};
var N = {N};

function colorClass(v) {{ return v > 0 ? 'up' : (v < 0 ? 'down' : 'zero'); }}
function signStr(v) {{ return v > 0 ? '▲' : (v < 0 ? '▼' : ''); }}

function onThreshChange() {{
  var t = parseInt(document.getElementById('threshSelect').value);
  document.getElementById('threshVal').textContent = t;
  var filtered = ALL_DATA.filter(function(r) {{ return r.count >= t; }});
  document.getElementById('matchCount').textContent = filtered.length;
  document.getElementById('footerInfo').textContent = '生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")} | 共 ' + filtered.length + ' 只股票';

  var html = '';
  filtered.forEach(function(r) {{
    var valsHtml = '';
    DATES.forEach(function(d) {{
      if (d in r.changes) {{
        var v = r.changes[d];
        valsHtml += '<td class="' + colorClass(v) + '">' + signStr(v) + v.toFixed(1) + '</td>';
      }} else {{
        valsHtml += '<td class="na">-</td>';
      }}
    }});
    var c = r.cumulative;
    html += '<tr>' +
      '<td class="code">' + r.code + '</td>' +
      '<td><a href="https://stockpage.10jqka.com.cn/' + r.code + '/" target="_blank" style="color:#333;text-decoration:none;font-weight:bold;">' + r.name + '</a></td>' +
      '<td class="center">' + r.count + '/' + N + '</td>' +
      valsHtml +
      '<td class="' + colorClass(c) + '">' + signStr(c) + c.toFixed(1) + '</td>' +
      '<td>' + r.volatility.toFixed(1) + '</td>' +
      '</tr>';
  }});
  document.getElementById('tableBody').innerHTML = html;

  var showMissing = document.getElementById('toggleMissing').checked;
  if (showMissing) {{
    var missed = filtered.filter(function(r) {{ return r.count === t; }});
    var missHtml = '';
    if (missed.length > 0) {{
      missHtml = '<h2>仅出现 ' + t + ' 天的股票 (缺勤明细)</h2>';
      missed.forEach(function(r) {{
        missHtml += '<div class="missing-item"><span class="code">' + r.code + '</span> ' + r.name + ': 缺 ' + r.missing.join(', ') + '</div>';
      }});
    }}
    document.getElementById('missingSection').innerHTML = missHtml;
    document.getElementById('missingSection').style.display = '';
  }} else {{
    document.getElementById('missingSection').innerHTML = '';
    document.getElementById('missingSection').style.display = 'none';
  }}
}}
</script>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    filtered_count = len(filtered)
    print(f"已生成: {OUTPUT_HTML} (共 {filtered_count} 只股票)")
    # webbrowser.open(f"file://{OUTPUT_HTML}")


def main():
    all_data = load_data()
    # print(all_data.keys())
    recent_dates = sorted(all_data.keys(), reverse=True)[:7]
    print(recent_dates)
    all_data = {d: all_data[d] for d in recent_dates}
    threshold = max(1, len(all_data) - 3)
    dates, all_results = analyze(all_data, threshold)
    output_html(dates, all_results, threshold)


if __name__ == "__main__":
    main()

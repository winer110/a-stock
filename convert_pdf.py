#!/usr/bin/env python3
"""使用 pdf-inspector 把 PDF 转为 Markdown。

用法:
    python3 convert_pdf.py <pdf路径> [-o <输出.md>] [--pages 1,3,5]

依赖: pip install pdf-inspector
"""
import argparse
import sys

try:
    import pdf_inspector
except ImportError:
    sys.exit("缺少依赖，请先安装: pip install pdf-inspector")


def main():
    parser = argparse.ArgumentParser(
        description="用 pdf-inspector 将 PDF 转 Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例: python3 convert_pdf.py 文档.pdf -o 文档.md\n"
               "      python3 convert_pdf.py 文档.pdf --pages 0,2  # 仅转第1、3页(0起始)",
    )
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("-o", "--output", help="输出 .md 路径（默认与 PDF 同名同目录）")
    parser.add_argument("--pages", help="仅转换指定页，逗号分隔，从0开始计")
    args = parser.parse_args()

    pages = [int(p.strip()) for p in args.pages.split(",")] if args.pages else None

    print(f"解析中: {args.pdf}" + (f"  仅页 {pages}" if pages else ""))
    result = pdf_inspector.process_pdf(args.pdf, pages=pages)

    print(f"PDF类型: {result.pdf_type}  置信度: {result.confidence:.2f}  页数: {result.page_count}")

    if not result.markdown:
        sys.exit(f"未能提取 Markdown（类型={result.pdf_type}）。若为扫描件/图片型 PDF，pdf-inspector 不做 OCR，需另用 OCR 方案。")

    out = args.output or args.pdf.rsplit(".", 1)[0] + ".md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(result.markdown)
    print(f"✅ 已生成: {out}  ({len(result.markdown)} 字符, {result.markdown.count(chr(10)) + 1} 行)")


if __name__ == "__main__":
    main()

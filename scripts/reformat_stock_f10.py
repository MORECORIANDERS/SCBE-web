"""将现有 603220_f10.json 重新格式化为结构化 JSON（lines 数组 + _meta 元数据）"""
import json
import re
from datetime import datetime
from pathlib import Path


def parse_sections(text: str) -> list:
    """从原始文本中提取小节名称（去重、排除免责条款）"""
    sections = re.findall(r'【(.+?)】', text)
    seen = set()
    unique = []
    for s in sections:
        if s != '免责条款' and s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def parse_updated_date(text: str) -> str:
    """从原始文本中提取更新日期"""
    m = re.search(r'更新日期：(\d{4}-\d{2}-\d{2})', text)
    return m.group(1) if m else ""


def main():
    src = Path(__file__).resolve().parent.parent / "underlying_stock" / "603220_f10.json"
    if not src.exists():
        print(f"错误: 未找到 {src}", flush=True)
        return

    with open(src, "r", encoding="utf-8") as f:
        raw = json.load(f)

    result = {
        "_meta": {
            "code": "603220",
            "name": "中贝通信",
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "categories_count": len(raw),
        }
    }

    for key, value in raw.items():
        lines = value.strip().split('\r\n')
        result[key] = {
            "_meta": {
                "updated": parse_updated_date(value),
                "sections": parse_sections(value),
                "line_count": len(lines),
            },
            "lines": lines,
        }

    # 写回原文件
    with open(src, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    size_kb = src.stat().st_size / 1024
    print(f"重新格式化完成！文件: {src}", flush=True)
    print(f"文件大小: {size_kb:.1f} KB", flush=True)
    print(f"分类数: {len(raw)}", flush=True)
    for k, v in result.items():
        if k == '_meta':
            continue
        sections = v['_meta']['sections']
        print(f"  {k}: {v['_meta']['line_count']} 行, 包含 {len(sections)} 个小节 {sections}", flush=True)


if __name__ == "__main__":
    main()

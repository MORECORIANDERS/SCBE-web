"""获取 F10 原始数据，保存为结构化的 JSON 格式"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from mootdx.quotes import Quotes

print("正在连接服务器...", flush=True)
client = Quotes.factory(market='std', server=('110.41.147.114', 7709), timeout=10)
print(f"连接成功, 服务器: {client.server}", flush=True)

print("正在获取 F10 数据...", flush=True)
f10 = client.F10('113678')

if not f10:
    print("F10 获取失败: 返回空", flush=True)
    sys.exit(1)

print(f"获取到 {len(f10)} 个分类: {list(f10.keys())}", flush=True)

# 构建结构化数据
result = {
    "_meta": {
        "code": "113678",
        "name": "中贝转债",
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "categories_count": len(f10),
    }
}

def parse_sections(text: str) -> list:
    """从原始文本中提取小节名称（去重、排除免责条款）"""
    sections = re.findall(r'【(.+?)】', text)
    # 去重并保留顺序，同时排除【免责条款】
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

for key, value in f10.items():
    # 按行拆分
    lines = value.strip().split('\r\n')

    result[key] = {
        "_meta": {
            "updated": parse_updated_date(value),
            "sections": parse_sections(value),
            "line_count": len(lines),
        },
        "lines": lines,
    }

# 保存到文件
output_file = Path(__file__).parent / "convertible_bond" / "113678_f10.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n数据已保存到: {output_file}", flush=True)
print(f"文件大小: {output_file.stat().st_size / 1024:.1f} KB", flush=True)
print(f"分类数: {len(f10)}", flush=True)
for k, v in result.items():
    if k == '_meta':
        continue
    sections = v['_meta']['sections']
    print(f"  {k}: {v['_meta']['line_count']} 行, 包含 {len(sections)} 个小节 {sections}", flush=True)

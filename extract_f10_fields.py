"""
从 F10 JSON 数据中提取关键字段，输出干净的 JSON
"""
import json
import re
from pathlib import Path


def load_f10(path: str | Path) -> dict:
    """加载已缓存的 F10 JSON 数据"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_section(lines: list[str], section_title: str) -> int:
    """在 lines 中查找指定小节（如【1.债券资料】）的起始行号
    要求该行以【section_title】开头（允许左侧空白），
    避免误匹配菜单行 "★本栏包括【...】" 等。
    """
    pattern = re.compile(rf"^\s*【{re.escape(section_title)}】")
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i
    return -1


def extract_value_by_key(lines: list[str], key: str) -> str:
    """从键-值配对的表格行中，根据 key 提取对应的 value

    支持格式: │key1    │value1    │key2    │value2    │
              │key1    │value1    │
    """
    for line in lines:
        if key in line and line.startswith("│"):
            parts = [p.strip() for p in line.split("│")]
            for i, p in enumerate(parts):
                if key in p and i + 1 < len(parts):
                    return parts[i + 1]
    return ""


def get_table_rows(lines: list[str], section_title: str) -> list[list[str]]:
    """提取某个小节中的所有表格数据行（按 │ 拆分为单元格列表）"""
    start = find_section(lines, section_title)
    if start == -1:
        return []

    rows = []
    for line in lines[start:]:
        line = line.strip()
        if not line.startswith("│"):
            continue
        # 跳过框线行（含 ┌┐├┤└┘┴┬┼）
        if re.search(r"[┌┐├┤└┘┴┬┼]", line):
            continue
        cells = [c.strip() for c in line.strip("│").split("│")]
        if cells:
            rows.append(cells)
    return rows


def parse_number(val: str) -> float | None:
    """从字符串中解析数字"""
    if not val:
        return None
    m = re.search(r"[\d.]+", val)
    return float(m.group()) if m else None


def extract_basic_info(lines: list[str]) -> dict:
    """提取债券基本资料（双列键值表）"""
    info = {}
    for key in ["债券代码", "债券简称", "交易市场", "发行规模(亿元)",
                 "最新规模(亿元)", "到期日期", "兑付日期"]:
        info[key] = extract_value_by_key(lines, key)
    return info


def extract_issuer_info(lines: list[str]) -> dict:
    """提取发行人基本资料"""
    return {"公司网址": extract_value_by_key(lines, "公司网址")}


def extract_stock_info(lines: list[str]) -> dict:
    """提取正股信息"""
    return {
        "正股代码": extract_value_by_key(lines, "标的股票"),
        "正股名称": extract_value_by_key(lines, "正股名称"),
    }


def extract_latest_convert_price(lines: list[str]) -> float | None:
    """从【转股价格调整】表中提取最新转股价"""
    rows = get_table_rows(lines, "3.转股价格调整")
    if len(rows) < 2:
        return None
    # 第一行是表头，第二行开始是数据（最新的一条在最前面）
    headers = rows[0]
    data = rows[1]
    # 找到"调整后转股价格(元)"所在的列
    for i, h in enumerate(headers):
        if "调整后转股价格" in h and i < len(data):
            return parse_number(data[i])
    return None


def extract_latest_rating(lines: list[str]) -> dict | None:
    """从【信用评级】表中提取最新评级"""
    rows = get_table_rows(lines, "1.信用评级")
    if len(rows) < 2:
        return None
    headers = rows[0]
    data = rows[1]  # 最新的一条
    record = {}
    for i, h in enumerate(headers):
        if i < len(data):
            record[h] = data[i]
    return record


def extract_announcements(lines: list[str]) -> list[dict]:
    """解析最新公告列表"""
    start = find_section(lines, "2.最新公告")
    if start == -1:
        return []

    announcements = []
    i = start + 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("〖"):
            break

        # 公告行: "      2026-04-30│公告标题"
        m = re.match(r"\s*(\d{4}-\d{2}-\d{1,2})│(.+)", line)
        if m:
            date = m.group(1)
            title = m.group(2).strip()
            link = ""
            # 向下查找 PDF 链接
            for j in range(i + 1, min(i + 4, len(lines))):
                url = lines[j].strip()
                if url.startswith("http"):
                    link = url.strip()
                    i = j
                    break
            announcements.append({
                "date": date,
                "title": title,
                "link": link,
            })
        i += 1

    return announcements


def extract_fields(data: dict) -> dict:
    """从 F10 数据中提取所需字段"""
    result = {}

    # ── 1. 债券概况 ──
    bond = data.get("债券概况", {}).get("lines", [])

    s1 = find_section(bond, "1.债券资料")
    basic = extract_basic_info(bond[s1:]) if s1 >= 0 else {}

    result["债券代码"] = basic.get("债券代码", "")
    result["债券简称"] = basic.get("债券简称", "")
    result["交易场所"] = basic.get("交易市场", "")
    result["发行规模(亿元)"] = parse_number(basic.get("发行规模(亿元)", ""))
    result["最新规模(亿元)"] = parse_number(basic.get("最新规模(亿元)", ""))
    result["到期日期"] = basic.get("到期日期") or basic.get("兑付日期", "")

    s2 = find_section(bond, "2.发行人基本资料")
    issuer = extract_issuer_info(bond[s2:]) if s2 >= 0 else {}
    result["公司网址"] = issuer.get("公司网址", "")

    # ── 2. 转股情况 ──
    convert = data.get("转股情况", {}).get("lines", [])

    sc = find_section(convert, "1.转股基本情况")
    stock = extract_stock_info(convert[sc:]) if sc >= 0 else {}
    result["正股代码"] = stock.get("正股代码", "")
    result["正股名称"] = stock.get("正股名称", "")
    result["最新转股价(元)"] = extract_latest_convert_price(convert)

    # ── 3. 债券条款（条件赎回触发比例）──
    terms = data.get("债券条款", {}).get("lines", [])
    result["条件赎回触发比例(%)"] = parse_number(extract_value_by_key(terms, "条件赎回触发比例"))

    # ── 4. 债券评级 ──
    rating = data.get("债券评级", {}).get("lines", [])
    latest_rating = extract_latest_rating(rating)
    if latest_rating:
        result["最新评级"] = {
            "等级": latest_rating.get("信用等级", ""),
            "机构": latest_rating.get("评级机构", ""),
            "日期": latest_rating.get("评级日期", ""),
        }

    # ── 5. 债券公告（前 10 条）──
    notices = data.get("债券公告", {}).get("lines", [])
    result["最新公告"] = extract_announcements(notices)[:10]

    return result


def main():
    f10_path = Path(__file__).parent / "convertible_bond" / "113678_f10.json"
    if not f10_path.exists():
        print(f"错误: 未找到 {f10_path}，请先运行 get_f10.py 获取数据", flush=True)
        return

    print("正在解析 F10 数据...", flush=True)
    data = load_f10(f10_path)
    fields = extract_fields(data)

    output_path = Path(__file__).parent / "convertible_bond" / "113678_f10_summary.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fields, f, ensure_ascii=False, indent=2)

    print(f"已完成！输出到: {output_path}", flush=True)
    print(json.dumps(fields, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

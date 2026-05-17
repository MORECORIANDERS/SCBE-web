"""从正股 F10 JSON 数据中提取关键字段，输出干净的 JSON"""
import json
import re
from pathlib import Path


def load_f10(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_section(lines: list[str], section_title: str) -> int:
    """在 lines 中查找指定小节（如【1.基本资料】）的起始行号
    排除菜单行中的相邻标题（如 【5.最新异动】【6.大宗交易】）
    """
    pattern = re.compile(rf"^\s*【{re.escape(section_title)}】")
    for i, line in enumerate(lines):
        if pattern.search(line):
            # 确认不是菜单行（后面紧跟着另一个 【）
            after = line[line.index(f"【{section_title}】") + len(section_title) + 2:]
            if not after.startswith("【"):
                return i
    return -1


def extract_value_by_key(lines: list[str], key: str) -> str:
    """从键-值配对的表格行中，根据 key 提取对应的 value"""
    for line in lines:
        if key in line and line.startswith("│"):
            parts = [p.strip() for p in line.split("│")]
            for i, p in enumerate(parts):
                if key in p and i + 1 < len(parts):
                    return parts[i + 1]
    return ""


def get_table_rows(lines, section_title):
    """提取某个小节中的所有表格数据行（按 │ 拆分为单元格列表）
    遇到下一个小节标题时停止
    """
    start = find_section(lines, section_title)
    if start == -1:
        return []
    rows = []
    for line in lines[start + 1:]:
        line_stripped = line.strip()
        # 遇到下一个小节标题时停止
        if re.match(r"^【\d+\.", line_stripped):
            break
        if not line_stripped.startswith("│"):
            continue
        if re.search(r"[┌┐├┤└┘┴┬┼]", line_stripped):
            continue
        cells = [c.strip() for c in line_stripped.strip("│").split("│")]
        if cells:
            rows.append(cells)
    return rows


def parse_concept(lines: list[str]) -> list[str]:
    """解析概念列表（所属板块中的 概念:xxx）"""
    start = find_section(lines, "1.所属板块")
    if start == -1:
        return []
    # 收集从 "概念:" 到 "风格:" 之间的所有行
    text_parts = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("概念:"):
            text_parts.append(stripped[3:])
        elif text_parts:
            # 已经进入概念区域
            if stripped.startswith("风格:") or stripped.startswith("指数:") or stripped.startswith("【"):
                break
            if stripped:
                # 如果续行以 "、" 开头，是标准换行，保留分隔符
                # 否则（如 "算力"→续行"租赁"），是文本截断，直接拼接
                if stripped.startswith("、"):
                    text_parts.append("、" + stripped.lstrip("、"))
                else:
                    text_parts.append(stripped)
    # 合并后去掉所有空白，再按 "、" 分割
    text = "".join(text_parts).replace(" ", "").replace("，", "、")
    concepts = [c.strip() for c in text.split("、") if c.strip()]
    return concepts


def parse_theme_events(lines: list[str], section_title: str) -> list[dict]:
    """解析主题投资/事件驱动列表"""
    start = find_section(lines, section_title)
    if start == -1:
        return []

    items = []
    i = start + 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("【") and "." not in line:
            break
        # 格式: "  2026-02-02│卫星导航    │关联度：☆☆☆"
        m = re.match(r"\s*(\d{4}-\d{2}-\d{2})│(.+)", line)
        if m:
            date = m.group(1)
            title = m.group(2).strip()
            # 清理标题（去掉关联度标记）
            title = re.sub(r"\s*│关联度[：:].*", "", title).strip()
            # 跳过框线行，找到描述起始行
            desc_start = i + 1
            for j in range(i + 1, len(lines)):
                nl = lines[j].strip()
                if nl.startswith("─") or nl.startswith("│"):
                    desc_start = j + 1
                else:
                    break
            # 收集描述（直到遇到下一条框线或标题）
            desc_lines = []
            for k in range(desc_start, len(lines)):
                nl = lines[k].strip()
                if not nl or nl.startswith("─") or nl.startswith("│") or nl.startswith("【"):
                    break
                desc_lines.append(nl.replace("│", "").strip())
            desc = "".join(desc_lines)
            items.append({"日期": date, "标题": title, "描述": desc})
        i += 1
    return items


def parse_biz_composition(lines: list[str]) -> dict | None:
    """解析主营构成分析（最新一期）"""
    start = find_section(lines, "2.主营构成分析")
    if start == -1:
        return None

    result = {}
    i = start + 1
    # 找到截止日期
    period = ""
    products = []
    regions = []
    current_section = None  # 'product' or 'region'

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("截止日期:"):
            if period:  # 已经解析完一期
                break
            period = line.replace("截止日期:", "").strip()
            result["截止日期"] = period
            i += 1
            # 跳过标题行和分隔线
            while i < len(lines):
                l = lines[i].strip()
                if l.startswith("─") or "项目名" in l:
                    i += 1
                    continue
                break
            continue

        if not line or line.startswith("─") or "项目名" in line:
            i += 1
            continue

        # 数据行格式: "5G新基建(产品)     17.76亿   54.73   3.48亿   54.51   19.61"
        # 按 2+ 空格分割
        parts = re.split(r"\s{2,}", line)
        if len(parts) >= 2:
            name = parts[0].strip()
            # 判断是产品还是地区
            is_product = "(产品)" in name or "(行业)" in name
            is_region = "(地区)" in name or "地区)" in name
            is_other = "(其他)" in name or "其他业务" in name

            if is_product or (not is_region and not "其他业务" in name):
                current_section = "product"
            elif is_region:
                current_section = "region"
            elif "其他业务" in name:
                # 从上下文判断
                pass

            # 提取数据
            data_parts = re.split(r"\s{2,}", line)
            item = {"名称": data_parts[0].strip()}
            if len(data_parts) > 1:
                item["营业收入"] = data_parts[1].strip()
            if len(data_parts) > 2:
                item["收入比例(%)"] = parse_number(data_parts[2])
            if len(data_parts) > 3:
                item["营业利润"] = data_parts[3].strip()
            if len(data_parts) > 4:
                item["利润比例(%)"] = parse_number(data_parts[4])
            if len(data_parts) > 5:
                item["毛利率(%)"] = parse_number(data_parts[5])

            target = products if current_section == "product" else regions
            target.append(item)

        i += 1

    if products:
        result["产品"] = products
    if regions:
        result["地区"] = regions
    return result if result else None


def parse_top5_customers(lines: list[str]) -> dict | None:
    """解析前5名客户营业收入表"""
    rows = get_table_rows(lines, "3.前5名客户营业收入表")
    if len(rows) < 2:
        return None
    # 第一行是表头，后续是数据
    headers = rows[0]
    customers = []
    total = None
    for row in rows[1:]:
        cells = [c.strip() for c in row]
        if len(cells) < 2:
            continue
        name = cells[0].replace(" ", "")
        if name == "合计":
            total = {
                "合计销售额(万元)": parse_number(cells[1]) if len(cells) > 1 else None,
                "占总营收比(%)": parse_number(cells[2]) if len(cells) > 2 else None,
            }
        else:
            customer = {"客户名称": name}
            if len(cells) > 1:
                customer["销售额(万元)"] = parse_number(cells[1])
            if len(cells) > 2:
                customer["占比(%)"] = parse_number(cells[2])
            customers.append(customer)
    return {"客户明细": customers, "合计": total}


def parse_number(val: str) -> float | None:
    if not val:
        return None
    m = re.search(r"[\d.]+", val)
    return float(m.group()) if m else None


def parse_revenue_info(lines: list[str]) -> dict | None:
    """从财务分析→主要财务指标 提取营业总收及同比增长率"""
    idx = find_section(lines, "1.主要财务指标")
    if idx == -1:
        return None
    section_lines = lines[idx:]

    result = {}

    # 提取营业总收（最新一期 2026-03-31 对应第一个数据列）
    for line in section_lines:
        stripped = line.strip()
        if stripped.startswith("│") and "营业总收(未调整:万)" in stripped:
            parts = [p.strip() for p in stripped.split("│")]
            # parts[0]="", parts[1]="营业总收(未调整:万)", parts[2]=最新一期
            if len(parts) > 2:
                val_str = parts[2].replace(",", "").strip()
                if val_str and val_str != "---":
                    val_wan = float(val_str)
                    if val_wan >= 10000:
                        result["营业总收入"] = f"{val_wan / 10000:.2f}亿"
                    else:
                        result["营业总收入"] = f"{val_wan:.2f}万"
                    result["营业总收入(万)"] = val_wan
            break

    # 提取总营收同比增长率
    for line in section_lines:
        stripped = line.strip()
        if stripped.startswith("│") and "总营收同比增长率" in stripped:
            parts = [p.strip() for p in stripped.split("│")]
            if len(parts) > 2:
                val_str = parts[2].strip()
                if val_str and val_str != "---":
                    result["总营收同比增长率(%)"] = float(val_str)
            break

    return result if result else None


def extract_fields(data: dict) -> dict:
    result = {}

    # ── 元数据 ──
    meta = data.get("_meta", {})
    result["fetch_time"] = meta.get("fetch_time", "")

    # ── 1. 公司概况 → 基本资料 ──
    profile = data.get("公司概况", {}).get("lines", [])
    s1 = find_section(profile, "1.基本资料")
    basic_lines = profile[s1:] if s1 >= 0 else []

    result["证券简称"] = extract_value_by_key(basic_lines, "证券简称")
    result["证券代码"] = extract_value_by_key(basic_lines, "证券代码")
    result["通达信研究行业"] = extract_value_by_key(basic_lines, "通达信研究行业")
    result["办公地址"] = extract_value_by_key(basic_lines, "办公地址")
    result["主营业务"] = extract_value_by_key(basic_lines, "主营业务")

    # ── 2. 最新异动 ──
    notice = data.get("最新提示", {}).get("lines", [])
    ns = find_section(notice, "5.最新异动")
    if ns >= 0:
        # 行内容如 "【5.最新异动】 暂无数据"
        result["最新异动"] = notice[ns].replace("【5.最新异动】", "").strip() or "暂无数据"
    else:
        result["最新异动"] = "暂无数据"

    # ── 3. 财务分析 → 营业收入 ──
    fin = data.get("财务分析", {}).get("lines", [])
    result["营业收入及占比"] = parse_revenue_info(fin)

    # ── 4. 热点题材 ──
    topics = data.get("热点题材", {}).get("lines", [])

    # 概念
    result["概念"] = parse_concept(topics)

    # 主题投资
    result["主题投资"] = parse_theme_events(topics, "2.主题投资")

    # 事件驱动
    result["事件驱动"] = parse_theme_events(topics, "3.事件驱动")

    # ── 5. 经营分析 ──
    biz = data.get("经营分析", {}).get("lines", [])

    # 主营构成分析（最新一期）
    result["主营构成分析"] = parse_biz_composition(biz)

    # 前5名客户
    result["前五名客户"] = parse_top5_customers(biz)

    return result


def main():
    src = Path(__file__).parent / "underlying_stock" / "603220_f10.json"
    if not src.exists():
        print(f"错误: 未找到 {src}", flush=True)
        return

    data = load_f10(src)
    fields = extract_fields(data)

    output_path = Path(__file__).parent / "underlying_stock" / "603220_summary.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fields, f, ensure_ascii=False, indent=2)

    print(f"已完成！输出到: {output_path}", flush=True)
    print(json.dumps(fields, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

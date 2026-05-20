"""
可转债 F10 数据采集 + 入库 CloudBase MySQL
=========================================
流程:
  1. 读取可转债列表（支持两种模式）:
     - CSV 模式: 从本地 CSV 读取（首次全量采集）
     - DB 模式:   从 bond_list 表读取（增量更新）
  2. 遍历每只转债，通过 mootdx 获取 F10（转债详情 + 正股详情）
  3. 提取关键字段（参考 f10_summary.json + stock_summary.json）
  4. 写入 CloudBase MySQL（bond_static: 转债基本信息）

使用说明:
  - 首次全量采集: DATA_SOURCE = 'csv'，读取本地 CSV 文件
  - 增量更新:     DATA_SOURCE = 'db'，从数据库 bond_list 表读取

预计耗时: 343 只转债 × 2 次 F10 ≈ 686 次请求，约 15~30 分钟
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# ============================================================
# 阶段开关（可独立运行）
# ============================================================
DO_COLLECT = True    # Phase 1: 从 mootdx 采集 F10 数据
DO_IMPORT = True     # Phase 2: 写入 CloudBase MySQL

# 数据源模式：'csv' 或 'db'
# csv: 从本地 CSV 读取（首次全量采集）
# db:  从 bond_list 表读取（增量更新）
DATA_SOURCE = 'db'

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = str(BASE_DIR / "convertible_bond" / "all_convertible_bonds_sina_20260518.csv")
OUTPUT_DIR = BASE_DIR / "convertible_bond" / "f10_cache"
BATCH_SIZE = 20          # 每批间隔数（避免 mootdx 请求过快）
REQUEST_DELAY = 0.5      # 每批间隔秒数
MOOTDX_SERVER = ('110.41.147.114', 7709)

DB_CONFIG = {
    "host": "sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com",
    "port": 27120,
    "user": "cbreport",
    "password": "huo22QQQ",
    "database": "python12-9guk780v324f024d",
    "charset": "utf8mb4",
}


# ============================================================
# 工具函数
# ============================================================

def setup_db():
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    return conn


def find_section(lines, section_title):
    pattern = re.compile(rf"^\s*【{re.escape(section_title)}】")
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i
    return -1


def extract_value_by_key(lines, key):
    for line in lines:
        if key in line and line.startswith("│"):
            parts = [p.strip() for p in line.split("│")]
            for i, p in enumerate(parts):
                if key in p and i + 1 < len(parts):
                    return parts[i + 1]
    return ""


def get_table_rows(lines, section_title):
    start = find_section(lines, section_title)
    if start == -1:
        return []
    rows = []
    for line in lines[start:]:
        line = line.strip()
        if not line.startswith("│"):
            continue
        if re.search(r"[┌┐├┤└┘┴┬┼]", line):
            continue
        cells = [c.strip() for c in line.strip("│").split("│")]
        if cells:
            rows.append(cells)
    return rows


def parse_number(val):
    if not val:
        return None
    m = re.search(r"[\d.]+", str(val))
    return float(m.group()) if m else None


def extract_announcements(lines):
    start = find_section(lines, "2.最新公告")
    if start == -1:
        return []
    announcements = []
    i = start + 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("〖"):
            break
        m = re.match(r"\s*(\d{4}-\d{2}-\d{1,2})│(.+)", line)
        if m:
            date = m.group(1)
            title = m.group(2).strip()
            link = ""
            for j in range(i + 1, min(i + 4, len(lines))):
                url = lines[j].strip()
                if url.startswith("http"):
                    link = url.strip()
                    i = j
                    break
            announcements.append({"date": date, "title": title, "link": link})
        i += 1
    return announcements


def parse_concept(lines):
    start = find_section(lines, "1.所属板块")
    if start == -1:
        return []
    text_parts = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("概念:"):
            text_parts.append(stripped[3:])
        elif text_parts:
            if stripped.startswith("风格:") or stripped.startswith("指数:") or stripped.startswith("【"):
                break
            if stripped:
                if stripped.startswith("、"):
                    text_parts.append("、" + stripped.lstrip("、"))
                else:
                    text_parts.append(stripped)
    text = "".join(text_parts).replace(" ", "").replace("，", "、")
    return [c.strip() for c in text.split("、") if c.strip()]


def parse_theme_events(lines, section_title):
    start = find_section(lines, section_title)
    if start == -1:
        return []
    items = []
    i = start + 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("【") and "." not in line:
            break
        m = re.match(r"\s*(\d{4}-\d{2}-\d{2})│(.+)", line)
        if m:
            date = m.group(1)
            title = m.group(2).strip()
            title = re.sub(r"\s*│关联度[：:].*", "", title).strip()
            desc_start = i + 1
            for j in range(i + 1, len(lines)):
                nl = lines[j].strip()
                if nl.startswith("─") or nl.startswith("│"):
                    desc_start = j + 1
                else:
                    break
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


def get_lines(data, key):
    """从 mootdx F10 数据中获取某个分类的行列表。F10 返回的是 {"类别名": "原始文本字符串"}"""
    val = data.get(key, "")
    if isinstance(val, str):
        return val.split("\n")
    if isinstance(val, dict) and "lines" in val:
        return val["lines"]
    return []


def extract_bond_f10_fields(f10_data):
    """从 mootdx F10 原始数据提取转债关键字段"""
    result = {}

    bond = get_lines(f10_data, "债券概况")
    s1 = find_section(bond, "1.债券资料")
    basic_start = bond[s1:] if s1 >= 0 else []
    result["债券简称"] = extract_value_by_key(basic_start, "债券简称")
    result["交易市场"] = extract_value_by_key(basic_start, "交易市场")
    result["发行规模(亿元)"] = parse_number(extract_value_by_key(basic_start, "发行规模(亿元)"))
    result["最新规模(亿元)"] = parse_number(extract_value_by_key(basic_start, "最新规模(亿元)"))
    result["到期日期"] = extract_value_by_key(basic_start, "到期日期") or extract_value_by_key(basic_start, "兑付日期")

    s2 = find_section(bond, "2.发行人基本资料")
    issuer = bond[s2:] if s2 >= 0 else []
    result["公司网址"] = extract_value_by_key(issuer, "公司网址")

    convert = get_lines(f10_data, "转股情况")
    sc = find_section(convert, "1.转股基本情况")
    convert_start = convert[sc:] if sc >= 0 else []
    result["正股代码"] = extract_value_by_key(convert_start, "标的股票")
    result["正股名称"] = extract_value_by_key(convert_start, "正股名称")

    cp_rows = get_table_rows(convert, "3.转股价格调整")
    if len(cp_rows) >= 2:
        headers = cp_rows[0]
        data = cp_rows[1]
        for i, h in enumerate(headers):
            if "调整后转股价格" in h and i < len(data):
                result["最新转股价(元)"] = parse_number(data[i])
                break

    terms = get_lines(f10_data, "债券条款")
    result["条件赎回触发比例(%)"] = parse_number(extract_value_by_key(terms, "条件赎回触发比例"))

    rating = get_lines(f10_data, "债券评级")
    rating_rows = get_table_rows(rating, "1.信用评级")
    if len(rating_rows) >= 2:
        headers = rating_rows[0]
        data = rating_rows[1]
        rating_info = {}
        for i, h in enumerate(headers):
            if i < len(data):
                rating_info[h] = data[i]
        if rating_info:
            result["评级等级"] = rating_info.get("信用等级", "")
            result["评级机构"] = rating_info.get("评级机构", "")
            result["评级日期"] = rating_info.get("评级日期", "")

    notices = get_lines(f10_data, "债券公告")
    result["最新公告"] = extract_announcements(notices)[:10]

    return result


def extract_stock_f10_fields(f10_data):
    """从 mootdx F10 原始数据提取正股关键字段"""
    result = {}

    profile = get_lines(f10_data, "公司概况")
    s1 = find_section(profile, "1.基本资料")
    basic = profile[s1:] if s1 >= 0 else []
    result["证券简称"] = extract_value_by_key(basic, "证券简称")
    result["证券代码"] = extract_value_by_key(basic, "证券代码")
    result["通达信研究行业"] = extract_value_by_key(basic, "通达信研究行业")
    result["办公地址"] = extract_value_by_key(basic, "办公地址")
    result["主营业务"] = extract_value_by_key(basic, "主营业务")

    notice = get_lines(f10_data, "最新提示")
    ns = find_section(notice, "5.最新异动")
    result["最新异动"] = notice[ns].replace("【5.最新异动】", "").strip() if ns >= 0 else "暂无数据"

    topics = get_lines(f10_data, "热点题材")
    result["概念"] = parse_concept(topics)
    result["主题投资"] = parse_theme_events(topics, "2.主题投资")

    return result


# ============================================================
# Phase 1: 采集
# ============================================================

def load_bond_list_from_db():
    """从数据库 bond_list 表读取可转债代码列表"""
    conn = setup_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT bond_code, bond_name, market
        FROM bond_list
        WHERE is_active = 1
        ORDER BY bond_code
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return pd.DataFrame(rows, columns=["转债代码", "转债名称", "市场"])


def collect_all():
    """遍历所有转债，通过 mootdx 采集 F10 数据"""
    from mootdx.quotes import Quotes

    # 根据数据源模式选择读取方式
    if DATA_SOURCE == 'csv':
        print(f"从 CSV 读取: {CSV_PATH}")
        df = pd.read_csv(CSV_PATH)
    else:
        print("从数据库 bond_list 表读取...")
        df = load_bond_list_from_db()

    total = len(df)
    print(f"可转债总数: {total}")
    print(f"预计采集: {total * 2} 次 F10 调用（债券 + 正股）")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"连接 mootdx 服务器 {MOOTDX_SERVER}...")
    client = Quotes.factory(market='std', server=MOOTDX_SERVER, timeout=15, multithread=True)
    print("连接成功\n")

    results = []
    success_count = 0
    fail_count = 0

    for idx, row in df.iterrows():
        bond_code = str(row["转债代码"]).zfill(6)
        bond_name = row["转债名称"]
        market = row["市场"]

        print(f"[{idx+1}/{total}] {bond_code} {bond_name} ({market})", end="", flush=True)

        bond_f10 = None
        stock_f10 = None
        stock_code = None

        # 获取转债 F10
        try:
            bond_f10_raw = client.F10(bond_code)
            if bond_f10_raw:
                bond_f10 = extract_bond_f10_fields(bond_f10_raw)
                stock_code = bond_f10.get("正股代码", "")
                print(f" ✓ 转债", end="", flush=True)
            else:
                print(f" ✗ 转债F10空", end="", flush=True)
        except Exception as e:
            print(f" ✗ 转债F10({e})", end="", flush=True)

        # 获取正股 F10（如果有正股代码）
        if stock_code and len(stock_code) >= 6:
            try:
                stock_f10_raw = client.F10(stock_code)
                if stock_f10_raw:
                    stock_f10 = extract_stock_f10_fields(stock_f10_raw)
                    print(f" ✓ 正股", end="", flush=True)
                else:
                    print(f" ✗ 正股F10空", end="", flush=True)
            except Exception as e:
                print(f" ✗ 正股F10({e})", end="", flush=True)
        else:
            print(f" ⚠ 无正股代码", end="", flush=True)

        record = {
            "bond_code": bond_code,
            "bond_name": bond_name,
            "market": market,
            "stock_code": stock_code,
        }
        if bond_f10:
            record["bond_f10"] = bond_f10
        if stock_f10:
            record["stock_f10"] = stock_f10

        results.append(record)

        if bond_f10 or stock_f10:
            success_count += 1
        else:
            fail_count += 1

        print()

        if (idx + 1) % BATCH_SIZE == 0 and idx + 1 < total:
            print(f"  → 休息 {REQUEST_DELAY}s...")
            time.sleep(REQUEST_DELAY)

    # 保存中间结果
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cache_file = OUTPUT_DIR / f"all_bonds_f10_{ts}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*50}")
    print(f"采集完成!")
    print(f"  成功: {success_count}, 失败: {fail_count}")
    print(f"  缓存文件: {cache_file}")
    return cache_file


# ============================================================
# Phase 2: 入库
# ============================================================

def safe_str(val, default=""):
    return str(val).strip() if val and str(val).strip() not in ("", "nan", "--", "None") else default


def import_to_db(cache_file):
    """将采集的数据写入 CloudBase MySQL"""
    print(f"读取缓存: {cache_file}")
    with open(cache_file, "r", encoding="utf-8") as f:
        records = json.load(f)
    print(f"共 {len(records)} 条记录")

    conn = setup_db()
    cur = conn.cursor()
    today = datetime.now().date()

    updated = 0
    inserted = 0
    errors = 0

    for idx, rec in enumerate(records):
        bond_code = rec["bond_code"]
        bond_name = safe_str(rec.get("bond_name"))
        market = safe_str(rec.get("market"))
        bf10 = rec.get("bond_f10", {}) or {}
        sf10 = rec.get("stock_f10", {}) or {}

        exchange_map = {"沪市": "上交所", "深市": "深交所"}
        exchange = exchange_map.get(market, "")

        stock_code_no_suffix = safe_str(bf10.get("正股代码", sf10.get("证券代码", "")))

        industry_raw = safe_str(sf10.get("通达信研究行业"))
        industry_levels = industry_raw.split("-") if industry_raw else ["", "", ""]
        industry_all = industry_raw

        stock_short_name = safe_str(bf10.get("正股名称", sf10.get("证券简称", "")))

        concepts_json = json.dumps(sf10.get("概念", []), ensure_ascii=False) if sf10.get("概念") else "[]"
        themes_json = json.dumps(sf10.get("主题投资", []), ensure_ascii=False) if sf10.get("主题投资") else "[]"
        announcements_json = json.dumps(bf10.get("最新公告", []), ensure_ascii=False) if bf10.get("最新公告") else "[]"

        sql = """
            INSERT INTO bond_static (
                stock_code, stock_name, bond_code, bond_name,
                market, exchange,
                industry_level1, industry_level2, industry_level3, industry_all,
                stock_code_full, stock_code_no_suffix, stock_short_name,
                issue_amount, latest_amount, maturity_date,
                convert_price, call_trigger_pct,
                rating_level, rating_agency, rating_date,
                website, business_main, office_address,
                concepts_json, themes_json, announcements_json,
                sector
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s
            ) ON DUPLICATE KEY UPDATE
                stock_name = VALUES(stock_name),
                bond_name = VALUES(bond_name),
                market = VALUES(market),
                exchange = VALUES(exchange),
                industry_level1 = VALUES(industry_level1),
                industry_level2 = VALUES(industry_level2),
                industry_level3 = VALUES(industry_level3),
                industry_all = VALUES(industry_all),
                stock_short_name = VALUES(stock_short_name),
                issue_amount = VALUES(issue_amount),
                latest_amount = VALUES(latest_amount),
                maturity_date = VALUES(maturity_date),
                convert_price = VALUES(convert_price),
                call_trigger_pct = VALUES(call_trigger_pct),
                rating_level = VALUES(rating_level),
                rating_agency = VALUES(rating_agency),
                rating_date = VALUES(rating_date),
                website = VALUES(website),
                business_main = VALUES(business_main),
                office_address = VALUES(office_address),
                concepts_json = VALUES(concepts_json),
                themes_json = VALUES(themes_json),
                announcements_json = VALUES(announcements_json),
                sector = VALUES(sector)
        """

        stock_code_full = f"{stock_code_no_suffix}.SH" if market == "沪市" else f"{stock_code_no_suffix}.SZ"
        sector_map = {"沪市": "上交所主板", "深市": "深交所主板"}
        sector = sector_map.get(market, market)

        def to_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        def to_date(val):
            """日期字段：空字符串转 None，避免 MySQL strict mode 报错"""
            s = safe_str(val)
            return s if s else None

        vals = (
            f"{bond_code}.{'SH' if market == '沪市' else 'SZ'}",
            bond_name,
            bond_code,
            bond_name,
            market,
            exchange,
            safe_str(industry_levels[0] if len(industry_levels) > 0 else ""),
            safe_str(industry_levels[1] if len(industry_levels) > 1 else ""),
            safe_str(industry_levels[2] if len(industry_levels) > 2 else ""),
            industry_all,
            stock_code_full,
            stock_code_no_suffix,
            stock_short_name,
            to_float(bf10.get("发行规模(亿元)")),
            to_float(bf10.get("最新规模(亿元)")),
            to_date(bf10.get("到期日期")),
            to_float(bf10.get("最新转股价(元)")),
            to_float(bf10.get("条件赎回触发比例(%)")),
            safe_str(bf10.get("评级等级")),
            safe_str(bf10.get("评级机构")),
            to_date(bf10.get("评级日期")),
            safe_str(bf10.get("公司网址")),
            safe_str(sf10.get("主营业务")),
            safe_str(sf10.get("办公地址")),
            concepts_json,
            themes_json,
            announcements_json,
            sector,
        )

        try:
            cur.execute(sql, vals)
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1
            if (idx + 1) % 20 == 0:
                conn.commit()
                print(f"  [批提交] 已处理 {idx+1}/{len(records)} 条")
        except Exception as e:
            errors += 1
            print(f"  ✗ [{idx+1}] {bond_code} {bond_name}: {e}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n{'='*50}")
    print(f"bond_static 入库完成!")
    print(f"  新增: {inserted}, 更新: {updated}, 错误: {errors}")


def import_csv_to_snapshot():
    """将 CSV 日行情数据导入 bond_snapshot"""
    df = pd.read_csv(CSV_PATH)
    print(f"CSV 共 {len(df)} 条行情记录")

    conn = setup_db()
    cur = conn.cursor()
    today = datetime.now().date()
    inserted = 0
    skipped = 0

    sql = """
        INSERT INTO bond_snapshot (
            trade_date, bond_code, bond_name,
            price, price_change, change_pct,
            volume, amount, settlement,
            open_price, high_price, low_price,
            buy_price, sell_price, trade_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            bond_name = VALUES(bond_name),
            price = VALUES(price),
            price_change = VALUES(price_change),
            change_pct = VALUES(change_pct),
            volume = VALUES(volume),
            amount = VALUES(amount),
            settlement = VALUES(settlement),
            open_price = VALUES(open_price),
            high_price = VALUES(high_price),
            low_price = VALUES(low_price),
            buy_price = VALUES(buy_price),
            sell_price = VALUES(sell_price),
            trade_time = VALUES(trade_time)
    """

    for idx, row in df.iterrows():
        vals = (
            today,
            str(row["转债代码"]).zfill(6),
            safe_str(row.get("转债名称")),
            float(row["最新价"]) if pd.notna(row.get("最新价")) else None,
            float(row["涨跌额"]) if pd.notna(row.get("涨跌额")) else None,
            float(row["涨跌幅"]) if pd.notna(row.get("涨跌幅")) else None,
            int(row["成交量(股)"]) if pd.notna(row.get("成交量(股)")) else 0,
            float(row["成交额(元)"]) if pd.notna(row.get("成交额(元)")) else 0,
            float(row["昨收价"]) if pd.notna(row.get("昨收价")) else None,
            float(row["开盘价"]) if pd.notna(row.get("开盘价")) else None,
            float(row["最高价"]) if pd.notna(row.get("最高价")) else None,
            float(row["最低价"]) if pd.notna(row.get("最低价")) else None,
            float(row["买入价"]) if pd.notna(row.get("买入价")) else None,
            float(row["卖出价"]) if pd.notna(row.get("卖出价")) else None,
            safe_str(row.get("成交时间")),
        )

        try:
            cur.execute(sql, vals)
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ✗ [{idx+1}] {row['转债代码']}: {e}")

        if (idx + 1) % 50 == 0:
            conn.commit()

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n{'='*50}")
    print(f"bond_snapshot 行情入库完成!")
    print(f"  新增: {inserted}, 已存在(跳过): {skipped}")


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 50)
    print(f"可转债全量数据采集 + 入库")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print()

    cache_file = None

    if DO_COLLECT:
        print(">>> Phase 1: 从 mootdx 采集 F10 数据 <<<")
        cache_file = collect_all()
        print()

    if DO_IMPORT:
        print(">>> Phase 2: 写入 CloudBase MySQL <<<")

        if not cache_file:
            cache_files = sorted(OUTPUT_DIR.glob("all_bonds_f10_*.json"))
            if cache_files:
                cache_file = str(cache_files[-1])
                print(f"使用最新缓存: {cache_file}")
            else:
                print("错误: 未找到缓存文件，请先运行采集阶段")
                return

        import_to_db(cache_file)
        print()
        import_csv_to_snapshot()

    print("\n全部完成!")


if __name__ == "__main__":
    main()

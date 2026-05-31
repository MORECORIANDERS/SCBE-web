# -*- coding: utf-8 -*-
"""
增量同步脚本（本地版，数据存JSON）
===================================
  1. 从 CloudBase MySQL 读取 all_kzz_hdq_20260530 与 bond_list 差集
  2. 从 CloudBase MySQL 读取 bond_list 与 sina_bonds_info 差集，调用新浪接口采集
  3. 从 CloudBase MySQL 读取 sina_bonds_info 与 sina_stock_info 差集，调用新浪接口采集

输出:
  scripts/sync_output/bond_list_increment.json    — Step1 增量记录
  scripts/sync_output/sina_bonds_info_increment.json — Step2 增量记录
  scripts/sync_output/sina_stock_info_increment.json — Step3 增量记录
"""
import os
import sys
import datetime
import json
import time
import random
import re
from typing import Optional, List, Dict

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pymysql
except ImportError:
    print("[ERROR] pymysql 未安装，请执行: pip install pymysql")
    sys.exit(1)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com"),
    "port": int(os.environ.get("DB_PORT", "27120")),
    "user": os.environ.get("DB_USER", "cbreport"),
    "password": os.environ.get("DB_PASSWORD", "huo22QQQ"),
    "database": os.environ.get("DB_NAME", "python12-9guk780v324f024d"),
    "charset": "utf8mb4",
}

HDQ_TABLE = "all_kzz_hdq_20260530"

REQUEST_INTERVAL = (0.2, 2.0)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_output")

HEADERS_BOND = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://gu.sina.cn/",
}

HEADERS_STOCK = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://quotes.sina.cn/",
}


def get_db_conn():
    return pymysql.connect(**DB_CONFIG)


def _parse_jsonp(text: str) -> dict:
    text = re.sub(r"^/\*.*?\*/", "", text).strip()
    text = re.sub(r"^[a-zA-Z_]\w*\(", "", text)
    text = re.sub(r"\);?\s*$", "", text)
    return json.loads(text)


def _try_num(s):
    if s in (None, "", "--"):
        return None
    s = str(s).replace(",", "")
    try:
        return float(s) if "." in s else int(s)
    except (ValueError, TypeError):
        return None


def safe_str(val, default=""):
    return str(val).strip() if val and str(val).strip() not in ("", "nan", "--", "None") else default


def save_json(data, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  [JSON] Saved: {filepath}")
    return filepath


def get_market_from_code(bond_code: str) -> str:
    if bond_code.startswith(("110", "111", "113", "118")):
        return "沪市"
    elif bond_code.startswith(("123", "127", "128")):
        return "深市"
    return ""


# ============================================================
# Step 1: all_kzz_hdq_20260530 → bond_list 增量
# ============================================================

def step1_sync_bond_list():
    print("\n" + "=" * 60)
    print("Step 1: all_kzz_hdq_20260530 → bond_list 增量")
    print("=" * 60)

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) FROM {HDQ_TABLE}")
    hdq_count = cur.fetchone()[0]
    print(f"  {HDQ_TABLE} 记录数: {hdq_count}")

    cur.execute("SELECT COUNT(*) FROM bond_list")
    bl_count = cur.fetchone()[0]
    print(f"  bond_list 记录数: {bl_count}")

    cur.execute(f"""
        SELECT h.bond_code, h.bond_name, h.stock_code, h.stock_name,
               h.listing_date, h.maturity_date
        FROM {HDQ_TABLE} h
        LEFT JOIN bond_list b ON h.bond_code = b.bond_code
        WHERE b.bond_code IS NULL
        ORDER BY h.bond_code
    """)
    missing = cur.fetchall()
    print(f"  bond_list 中缺失的记录: {len(missing)} 条")

    cur.close()
    conn.close()

    if not missing:
        print("  ✓ bond_list 已是最新，无需增量")
        return []

    today = datetime.date.today().strftime("%Y-%m-%d")
    records = []
    for bond_code, bond_name, stock_code, stock_name, listing_date, maturity_date in missing:
        bond_code = str(bond_code).zfill(6)
        market = get_market_from_code(bond_code)
        is_active = 0 if bond_name and ("定转" in bond_name or "定01" in bond_name) else 1
        records.append({
            "bond_code": bond_code,
            "bond_name": safe_str(bond_name),
            "market": market,
            "is_active": is_active,
            "created_at": today,
            "updated_at": today,
            "stock_code": safe_str(stock_code),
            "stock_name": safe_str(stock_name),
            "listing_date": str(listing_date) if listing_date else None,
            "maturity_date": str(maturity_date) if maturity_date else None,
        })

    active = [r for r in records if r["is_active"] == 1]
    inactive = [r for r in records if r["is_active"] == 0]
    print(f"  其中活跃: {len(active)}, 非活跃(定转等): {len(inactive)}")

    save_json({
        "update_date": today,
        "total": len(records),
        "active_count": len(active),
        "inactive_count": len(inactive),
        "records": records,
    }, "bond_list_increment.json")

    return [r["bond_code"] for r in records if r["is_active"] == 1]


# ============================================================
# Step 2: bond_list → sina_bonds_info 增量采集
# ============================================================

def fetch_bond_info(bond_code: str, session: requests.Session) -> Optional[Dict]:
    url = "https://quotes.sina.com.cn/bd/api/openapi.php/BondService2021.getBondInfo"
    params = {"symbol": f"sh{bond_code}", "callback": "hqccall_bondinfo"}

    try:
        time.sleep(random.uniform(*REQUEST_INTERVAL))
        response = session.get(url, params=params, headers=HEADERS_BOND, timeout=30)
        response.encoding = "utf-8"

        if response.status_code != 200:
            return None

        data = _parse_jsonp(response.text)
        result_data = data.get("result", {}).get("data", {})

        if not result_data:
            return None

        conver = result_data.get("converInfo", {})
        bond = result_data.get("baseInfo", {})

        raw = {
            "bond_code": bond_code,
            "name": bond.get("BondSName", ""),
            "stock_name": conver.get("SKSENAME", ""),
            "stock_code": conver.get("SKCODE", ""),
            "stock_symbol": conver.get("SYMBOL", ""),
            "转股起始日": conver.get("ZGQSR", ""),
            "转股截止日": conver.get("ZGJZR", ""),
            "强赎触发价": _try_num(conver.get("QSCFPrice", "")),
            "赎回锁定期": conver.get("QSQSR", ""),
            "最新赎回价": _try_num(conver.get("ZXSHPrice", "")),
            "回售触发价": _try_num(conver.get("HSCFPrice", "")),
            "回售锁定期": conver.get("HSQSR", ""),
            "最新回售价": _try_num(conver.get("ZXHSPrice", "")),
            "最新回售日期": conver.get("ZXHSR", ""),
            "修正触发价": _try_num(conver.get("XZCFPrice", "")),
            "当前转股价": _try_num(conver.get("DQZGPrice", "")),
            "发行价格": _try_num(bond.get("Value", "")),
            "发行规模(万元)": _try_num(bond.get("FXGM", "")),
            "剩余规模": bond.get("SYGM", ""),
            "起息日期": bond.get("BeginDate", ""),
            "到期日期": bond.get("PayDate", ""),
            "付息方式": bond.get("PayFreq", ""),
            "到期赎回价格": _try_num(bond.get("DQSHPrice", "")) or _try_num(conver.get("DQSHPrice", "")),
            "债券评级": bond.get("XYPJ", ""),
            "债券全称": bond.get("BondName", ""),
            "债券简称": bond.get("BondSName", ""),
            "债券期限(年)": _try_num(bond.get("BondLife", "")),
            "利息说明": bond.get("LLSM", ""),
        }

        info = {
            "bond_code": bond_code,
            "name": raw["name"],
            "stock_code": raw["stock_code"],
            "stock_name": raw["stock_name"],
            "stock_symbol": raw["stock_symbol"],
            "conversion_start_date": raw["转股起始日"],
            "conversion_end_date": raw["转股截止日"],
            "force_redeem_price": raw["强赎触发价"],
            "redeem_lock_period": raw["赎回锁定期"],
            "latest_redeem_price": str(raw["最新赎回价"]) if raw["最新赎回价"] is not None else None,
            "put_option_price": raw["回售触发价"],
            "put_option_lock": raw["回售锁定期"],
            "latest_put_price": raw["最新回售价"],
            "latest_put_date": raw["最新回售日期"],
            "revise_price": raw["修正触发价"],
            "conversion_price": raw["当前转股价"],
            "issue_price": raw["发行价格"],
            "issue_amount": raw["发行规模(万元)"],
            "remain_scale": raw["剩余规模"],
            "interest_start_date": raw["起息日期"],
            "maturity_date": raw["到期日期"],
            "interest_method": raw["付息方式"],
            "maturity_redeem_price": raw["到期赎回价格"],
            "rating": raw["债券评级"],
            "full_name": raw["债券全称"],
            "short_name": raw["债券简称"],
            "bond_life": raw["债券期限(年)"],
            "interest_note": raw["利息说明"],
            "raw_data": raw,
        }

        return info

    except Exception as e:
        print(f"    [WARN] Fetch {bond_code} failed: {e}")
        return None


def step2_sync_sina_bonds_info(new_bond_codes: List[str] = None):
    print("\n" + "=" * 60)
    print("Step 2: bond_list → sina_bonds_info 增量采集")
    print("=" * 60)

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT bond_code FROM sina_bonds_info")
    existing = {row[0] for row in cur.fetchall()}
    print(f"  sina_bonds_info 已有记录: {len(existing)} 条")

    if new_bond_codes:
        missing_codes = [c for c in new_bond_codes if c not in existing]
    else:
        cur.execute("SELECT bond_code FROM bond_list WHERE is_active = 1")
        all_active = {row[0] for row in cur.fetchall()}
        missing_codes = list(all_active - existing)

    cur.close()
    conn.close()

    print(f"  需要增量采集: {len(missing_codes)} 条")

    if not missing_codes:
        print("  ✓ sina_bonds_info 已是最新，无需采集")
        return []

    session = requests.Session()
    all_info = []
    fail_list = []

    for i, code in enumerate(missing_codes):
        print(f"  [{i+1}/{len(missing_codes)}] Fetch {code}...", end="", flush=True)
        info = fetch_bond_info(code, session)
        if info:
            all_info.append(info)
            print(f" OK ({info.get('name', '')})")
        else:
            fail_list.append(code)
            print(" FAIL")

    save_json({
        "update_date": datetime.date.today().strftime("%Y-%m-%d"),
        "total": len(missing_codes),
        "success_count": len(all_info),
        "fail_count": len(fail_list),
        "fail_list": fail_list,
        "records": all_info,
    }, "sina_bonds_info_increment.json")

    new_stock_codes = list(set(
        info["stock_code"] for info in all_info
        if info.get("stock_code") and info["stock_code"].strip()
    ))
    print(f"  ✓ 采集完成: 成功 {len(all_info)}, 失败 {len(fail_list)}")
    print(f"  新增正股代码: {len(new_stock_codes)} 个")
    return new_stock_codes


# ============================================================
# Step 3: sina_bonds_info → sina_stock_info 增量采集
# ============================================================

def fetch_company_info(symbol: str, session: requests.Session) -> Optional[Dict]:
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyF10Service.getCompanyInformation"
    params = {"symbol": symbol, "callback": "hqccall_company"}

    try:
        time.sleep(random.uniform(*REQUEST_INTERVAL))
        response = session.get(url, params=params, headers=HEADERS_STOCK, timeout=30)
        response.encoding = "utf-8"

        if response.status_code != 200:
            return None

        data = _parse_jsonp(response.text)
        result = data.get("result", {}).get("data", {})

        if not result:
            return None

        industries = []
        for ind in result.get("Industry", []):
            industries.append({
                "级别": ind.get("tagname", ""),
                "名称": ind.get("name", ""),
            })

        return {
            "company_name": result.get("CorpName", ""),
            "company_nature": result.get("orgType", ""),
            "industry": industries,
            "main_business": result.get("mainBusiness", ""),
            "max_income_source": result.get("maxIncome", ""),
            "max_profit_source": result.get("maxProfit", ""),
            "office_address": result.get("workAddress", ""),
            "company_website": result.get("companyAddress", ""),
            "highlight": result.get("highlight", ""),
        }

    except Exception as e:
        print(f"    [WARN] Fetch company info {symbol} failed: {e}")
        return None


def fetch_related_data(symbol: str, session: requests.Session) -> Optional[Dict]:
    url = "https://quotes.sina.cn/app/api/openapi.php/ClientCnHqService.getRelatedHq"
    params = {"market": "cn", "symbol": symbol, "callback": "hqccall_related"}

    try:
        time.sleep(random.uniform(*REQUEST_INTERVAL))
        response = session.get(url, params=params, headers=HEADERS_STOCK, timeout=30)
        response.encoding = "utf-8"

        if response.status_code != 200:
            return None

        data = _parse_jsonp(response.text)
        result = data.get("result", {}).get("data", {})

        if not result:
            return None

        concepts = []
        for gn in result.get("belong_gn", []):
            concepts.append({
                "概念名称": gn.get("name", ""),
                "相关性": gn.get("relevancy_cn", ""),
                "相关原因": gn.get("reason", ""),
            })

        return {"concepts": concepts}

    except Exception as e:
        print(f"    [WARN] Fetch related data {symbol} failed: {e}")
        return None


def step3_sync_sina_stock_info(new_stock_codes: List[str] = None):
    print("\n" + "=" * 60)
    print("Step 3: sina_bonds_info → sina_stock_info 增量采集")
    print("=" * 60)

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT stock_code FROM sina_stock_info")
    existing = {row[0] for row in cur.fetchall()}
    print(f"  sina_stock_info 已有记录: {len(existing)} 条")

    if new_stock_codes:
        missing_codes = list(set(new_stock_codes) - existing)
    else:
        cur.execute("SELECT stock_code FROM sina_bonds_info WHERE stock_code != '' AND stock_code IS NOT NULL")
        all_stock_codes = {row[0] for row in cur.fetchall()}
        missing_codes = list(all_stock_codes - existing)

    cur.close()
    conn.close()

    print(f"  需要增量采集: {len(missing_codes)} 条")

    if not missing_codes:
        print("  ✓ sina_stock_info 已是最新，无需采集")
        return

    session = requests.Session()
    all_info = []
    fail_list = []

    for i, stock_code in enumerate(missing_codes):
        if stock_code.startswith(("60", "68")):
            symbol = f"sh{stock_code}"
        else:
            symbol = f"sz{stock_code}"

        print(f"  [{i+1}/{len(missing_codes)}] Fetch {stock_code} ({symbol})...", end="", flush=True)

        company_info = fetch_company_info(symbol, session)
        related_data = fetch_related_data(symbol, session)

        if not company_info and not related_data:
            fail_list.append(stock_code)
            print(" FAIL")
            continue

        info = {"stock_code": stock_code}
        if company_info:
            info.update(company_info)
        if related_data:
            info["concepts"] = related_data.get("concepts", [])
        if "concepts" not in info:
            info["concepts"] = []

        raw_data = dict(info)
        info["raw_data"] = raw_data

        all_info.append(info)
        print(f" OK ({info.get('company_name', '')})")

    save_json({
        "update_date": datetime.date.today().strftime("%Y-%m-%d"),
        "total": len(missing_codes),
        "success_count": len(all_info),
        "fail_count": len(fail_list),
        "fail_list": fail_list,
        "records": all_info,
    }, "sina_stock_info_increment.json")

    print(f"  ✓ 采集完成: 成功 {len(all_info)}, 失败 {len(fail_list)}")


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("增量同步（本地版）: hdq → bond_list → sina_bonds_info → sina_stock_info")
    print(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    new_bond_codes = step1_sync_bond_list()

    new_stock_codes = step2_sync_sina_bonds_info(new_bond_codes if new_bond_codes else None)

    step3_sync_sina_stock_info(new_stock_codes if new_stock_codes else None)

    print("\n" + "=" * 60)
    print("全部同步完成!")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()

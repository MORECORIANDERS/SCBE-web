"""
新浪财经行情获取 → 直接入库 bond_snapshot
支持增量更新：只更新当日行情，已存在的记录会覆盖
"""
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
API_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://vip.stock.finance.sina.com.cn/mkt/",
    "Accept-Charset": "gbk",
}
PARAMS = {
    "page": 1,
    "num": 50,
    "sort": "symbol",
    "asc": 1,
    "node": "hskzz_z",
    "symbol": "",
    "_s_r_a": "page",
}

DB_CONFIG = {
    "host": "sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com",
    "port": 27120,
    "user": "cbreport",
    "password": "huo22QQQ",
    "database": "python12-9guk780v324f024d",
    "charset": "utf8mb4",
}


def fetch_page(page_num: int) -> list:
    params = PARAMS.copy()
    params["page"] = page_num
    r = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
    r.encoding = "gbk"
    import json
    return json.loads(r.text)


def setup_db():
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    return conn


def save_to_db(records: list) -> dict:
    """将行情数据直接写入 bond_snapshot 表"""
    if not records:
        return {"inserted": 0, "updated": 0, "errors": 0}

    conn = setup_db()
    cur = conn.cursor()
    today = datetime.now().date()

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

    inserted = 0
    updated = 0
    errors = 0

    for idx, row in records.iterrows():
        bond_code = str(row["转债代码"]).zfill(6)
        bond_name = str(row.get("转债名称", "")).strip() if row.get("转债名称") else ""

        def safe_float(val, default=0.0):
            try:
                return float(val) if val and str(val).strip() not in ("", "nan", "--", "None") else default
            except (ValueError, TypeError):
                return default

        def safe_int(val, default=0):
            try:
                return int(float(val)) if val and str(val).strip() not in ("", "nan", "--", "None") else default
            except (ValueError, TypeError):
                return default

        vals = (
            today,
            bond_code,
            bond_name,
            safe_float(row.get("最新价")),
            safe_float(row.get("涨跌额")),
            safe_float(row.get("涨跌幅")),
            safe_int(row.get("成交量(股)")),
            safe_float(row.get("成交额(元)")),
            safe_float(row.get("昨收价")),
            safe_float(row.get("开盘价")),
            safe_float(row.get("最高价")),
            safe_float(row.get("最低价")),
            safe_float(row.get("买入价")),
            safe_float(row.get("卖出价")),
            str(row.get("成交时间", "")) if row.get("成交时间") else "",
        )

        try:
            cur.execute(sql, vals)
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ✗ {bond_code} {bond_name}: {e}")

        if (idx + 1) % 50 == 0:
            conn.commit()

    conn.commit()
    cur.close()
    conn.close()

    return {"inserted": inserted, "updated": updated, "errors": errors}


def main():
    print("=" * 60)
    print("新浪财经行情获取 → 直接入库")
    print("=" * 60)

    print("\n正在从新浪财经获取可转债列表...")
    all_data = []
    page = 1

    while True:
        print(f"  第 {page} 页...", end="", flush=True)
        items = fetch_page(page)
        if not items:
            print(" 无数据")
            break
        print(f" {len(items)} 条")
        all_data.extend(items)
        page += 1
        time.sleep(0.3)

    print(f"\n共获取 {len(all_data)} 条原始记录")

    df = pd.DataFrame(all_data)

    df["市场"] = df["symbol"].str[:2].map({"sh": "沪市", "sz": "深市", "bj": "北交所"})
    df["转债代码"] = df["code"].astype(str).str.zfill(6)

    dingzhuan_mask = df["name"].str.contains("定转", na=False)
    if dingzhuan_mask.sum() > 0:
        print(f'剔除"定转"记录 {dingzhuan_mask.sum()} 条')
    df = df[~dingzhuan_mask].copy()

    rename = {
        "name": "转债名称",
        "trade": "最新价",
        "pricechange": "涨跌额",
        "changepercent": "涨跌幅",
        "buy": "买入价",
        "sell": "卖出价",
        "settlement": "昨收价",
        "open": "开盘价",
        "high": "最高价",
        "low": "最低价",
        "volume": "成交量(股)",
        "amount": "成交额(元)",
        "ticktime": "成交时间",
    }
    df = df.rename(columns=rename)

    result = df[[
        "转债代码", "转债名称", "最新价", "涨跌额", "涨跌幅",
        "买入价", "卖出价", "昨收价", "开盘价", "最高价", "最低价",
        "成交量(股)", "成交额(元)", "成交时间"
    ]].copy()

    print(f"有效可转债: {len(result)} 只")

    print("\n正在入库 bond_snapshot...")
    stats = save_to_db(result)

    print(f"\n{'='*60}")
    print(f"入库完成!")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  总记录: {len(result)}")
    print(f"  新增: {stats['inserted']}")
    print(f"  更新: {stats['updated']}")
    print(f"  错误: {stats['errors']}")


if __name__ == "__main__":
    main()

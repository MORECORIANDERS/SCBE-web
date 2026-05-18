"""从新浪财经获取沪深全量可转债当日行情，保存到本地 CSV/Excel"""
import os
import time
from datetime import datetime

import pandas as pd
import requests

# ── 配置 ──
OUTPUT_DIR = "convertible_bond"
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


def fetch_page(page_num: int) -> list:
    params = PARAMS.copy()
    params["page"] = page_num
    r = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
    r.encoding = "gbk"
    import json
    return json.loads(r.text)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("正在从新浪财经获取可转债列表...")
    all_data = []
    page = 1

    while True:
        print(f"  第 {page} 页...", flush=True)
        items = fetch_page(page)
        if not items:
            break
        all_data.extend(items)
        page += 1
        time.sleep(0.3)

    print(f"\n共获取 {len(all_data)} 条原始记录（含北交所定转）")

    df = pd.DataFrame(all_data)

    df["市场"] = df["symbol"].str[:2].map({"sh": "沪市", "sz": "深市", "bj": "北交所"})
    df["转债代码"] = df["code"].astype(str).str.zfill(6)

    # 剔除名称含"定转"的记录（北交所定向转债，非公开募集）
    dingzhuan_mask = df["name"].str.contains("定转", na=False)
    dingzhuan_count = dingzhuan_mask.sum()
    if dingzhuan_count > 0:
        print(f'剔除"定转"记录 {dingzhuan_count} 条: {df.loc[dingzhuan_mask, "name"].tolist()}')
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
        "转债代码", "市场", "转债名称",
        "最新价", "涨跌额", "涨跌幅",
        "买入价", "卖出价",
        "昨收价", "开盘价", "最高价", "最低价",
        "成交量(股)", "成交额(元)",
        "成交时间",
    ]].copy()

    result["涨跌幅"] = pd.to_numeric(result["涨跌幅"], errors="coerce").round(3)
    result["涨跌额"] = pd.to_numeric(result["涨跌额"], errors="coerce").round(3)
    result["最新价"] = pd.to_numeric(result["最新价"], errors="coerce").round(3)

    result = result.sort_values("成交额(元)", ascending=False).reset_index(drop=True)

    today = datetime.now().strftime("%Y%m%d")
    csv_path = os.path.join(OUTPUT_DIR, f"all_convertible_bonds_sina_{today}.csv")
    xlsx_path = os.path.join(OUTPUT_DIR, f"all_convertible_bonds_sina_{today}.xlsx")

    result.to_csv(csv_path, index=False, encoding="utf-8-sig")
    result.to_excel(xlsx_path, index=False)

    print(f"\n{'='*50}")
    print(f"数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总记录数: {len(result)}")
    print(f"  沪市: {len(result[result['市场']=='沪市'])} 只")
    print(f"  深市: {len(result[result['市场']=='深市'])} 只")
    print(f"  北交所: {len(result[result['市场']=='北交所'])} 只")
    print(f"\n✓ CSV: {os.path.abspath(csv_path)}")
    print(f"✓ Excel: {os.path.abspath(xlsx_path)}")
    print(f"\n前10条（按成交额排序）:")
    print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

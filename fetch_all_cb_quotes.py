"""获取全部可转债当日行情，保存到本地 CSV/Excel"""
import os
import sys
import time
from datetime import datetime

import pandas as pd
from mootdx.quotes import Quotes

# ── 配置 ──
OUTPUT_DIR = "convertible_bond"
BATCH_SIZE = 50       # 每批查询数量
REQUEST_DELAY = 0.5   # 每批间隔(秒)
SERVER = ('110.41.147.114', 7709)

# 可转债代码前缀
CB_PREFIXES = ('110', '111', '113', '118', '123', '127', '128')

# 需要排除的指数/基金名称关键词
EXCLUDE_KEYWORDS = ['上证转债', '深证转债', '国证转债', '转债ETF', 'CX转债', '可转债', '含可转债', '发可转债']


def get_convertible_bonds(client) -> pd.DataFrame:
    """获取全部可转债基础信息列表"""
    print("正在获取沪深全量证券列表...")
    stocks_sh = client.stocks(market=0)
    stocks_sz = client.stocks(market=1)
    all_stocks = pd.concat([stocks_sh, stocks_sz], ignore_index=True)

    # 筛选名称含"转债"的品种
    cb_mask = all_stocks['name'].str.contains('转债', na=False)
    cb_candidates = all_stocks[cb_mask].copy()

    # 按代码前缀过滤真正的可转债
    prefix_mask = cb_candidates['code'].str.startswith(CB_PREFIXES)
    cb_list = cb_candidates[prefix_mask].copy()

    # 排除指数/基金类
    for keyword in EXCLUDE_KEYWORDS:
        cb_list = cb_list[~cb_list['name'].str.contains(keyword, na=False)]

    # 清理名称中的空字符
    cb_list['name'] = cb_list['name'].str.replace('\x00', '', regex=False).str.strip()

    cb_list = cb_list.reset_index(drop=True)
    return cb_list


def fetch_quotes_batch(client, codes):
    """批量获取实时行情"""
    try:
        df = client.quotes(symbol=codes)
        if df is not None and not df.empty:
            return df
    except Exception as e:
        print(f"  批量查询失败: {e}")
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"连接服务器 {SERVER}...")
    client = Quotes.factory(market='std', server=SERVER, timeout=15, multithread=True)
    print("连接成功")

    # ── 1. 获取可转债列表 ──
    cb_list = get_convertible_bonds(client)
    total = len(cb_list)
    print(f"\n共找到 {total} 只可转债")

    codes_list = cb_list['code'].tolist()
    print(f"代码范围: {codes_list[0]} ~ {codes_list[-1]}")

    # ── 2. 分批获取行情 ──
    all_quotes = []
    success_count = 0
    fail_count = 0

    for i in range(0, total, BATCH_SIZE):
        batch_codes = codes_list[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n[{batch_num}/{total_batches}] 正在查询第 {i+1}-{i+len(batch_codes)} 只...")

        df = fetch_quotes_batch(client, batch_codes)

        if df is not None and not df.empty:
            all_quotes.append(df)
            success_count += len(df)
            print(f"  ✓ 成功获取 {len(df)} 只")
        else:
            # 逐只重试失败的
            print(f"  ⚠ 批量失败，逐只查询...")
            for code in batch_codes:
                try:
                    q = client.quotes(symbol=code)
                    if q is not None and not q.empty:
                        all_quotes.append(q)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    fail_count += 1
                time.sleep(0.05)

        if batch_num < total_batches:
            time.sleep(REQUEST_DELAY)

    print(f"\n{'='*50}")
    print(f"查询完成: 成功 {success_count}, 失败 {fail_count}")

    if not all_quotes:
        print("未获取到任何行情数据！")
        sys.exit(1)

    # ── 3. 合并数据 ──
    quotes_df = pd.concat(all_quotes, ignore_index=True)

    # 合并基础信息（名称、昨收）
    merged = quotes_df.merge(
        cb_list[['code', 'name', 'pre_close']],
        on='code',
        how='left',
        suffixes=('', '_list')
    )

    # 选取关键字段并重命名
    result = merged[[
        'code', 'name',
        'open', 'high', 'low', 'price',
        'last_close', 'pre_close',
        'vol', 'amount', 'volume',
        'bid1', 'ask1',
        'servertime'
    ]].copy()

    result.columns = [
        '转债代码', '转债名称',
        '开盘价', '最高价', '最低价', '最新价',
        '昨收价', '昨收(列表)',
        '成交量(手)', '成交额(元)', '成交量(股)',
        '买一价', '卖一价',
        '服务器时间'
    ]

    # 计算涨跌幅
    base_price = result['昨收价'].fillna(result['昨收(列表)'])
    result['涨跌幅(%)'] = ((result['最新价'] - base_price) / base_price * 100).round(2)
    result['涨跌额'] = (result['最新价'] - base_price).round(3)

    result = result.sort_values('成交额(元)', ascending=False).reset_index(drop=True)

    # ── 4. 添加市场标记 ──
    def get_market(code):
        if code.startswith(('110', '111', '113', '118')):
            return '沪市'
        elif code.startswith(('123', '127', '128')):
            return '深市'
        return '未知'

    result.insert(1, '市场', result['转债代码'].apply(get_market))

    # ── 5. 保存文件 ──
    today = datetime.now().strftime('%Y%m%d')
    csv_path = os.path.join(OUTPUT_DIR, f'all_convertible_bonds_{today}.csv')
    xlsx_path = os.path.join(OUTPUT_DIR, f'all_convertible_bonds_{today}.xlsx')

    result.to_csv(csv_path, index=False, encoding='utf-8-sig')
    result.to_excel(xlsx_path, index=False)

    print(f"\n✓ CSV 文件: {os.path.abspath(csv_path)}")
    print(f"✓ Excel 文件: {os.path.abspath(xlsx_path)}")
    print(f"\n数据概要:")
    print(f"  可转债总数: {len(result)}")
    print(f"  沪市: {len(result[result['市场']=='沪市'])} 只")
    print(f"  深市: {len(result[result['市场']=='深市'])} 只")
    print(f"  成交额最高: {result.iloc[0]['转债名称']} ({result.iloc[0]['转债代码']})")
    print(f"  成交额最低: {result.iloc[-1]['转债名称']} ({result.iloc[-1]['转债代码']})")
    print(f"  数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()

"""
可转债周线数据采集脚本（mootdx 直连通达信）
========================================
功能：
  1. 通过 mootdx（通达信协议）直接获取周线数据
  2. 展示数据样本，验证数据正确性
  3. 若 mootdx 无数据，则从本地 CSV/数据库降级聚合

用法：
  python scripts/fetch_weekly_kline.py                    # 测试默认转债
  python scripts/fetch_weekly_kline.py --code 113667       # 指定转债
  python scripts/fetch_weekly_kline.py --test-all          # 全量测试
  python scripts/fetch_weekly_kline.py --mode init         # 初始化历史数据（offset=800）
"""

import argparse
import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_weekly(symbol: str, offset: int = 10) -> pd.DataFrame:
    """通过 mootdx 获取周线数据"""
    from mootdx.quotes import Quotes

    client = Quotes.factory(market='std')
    try:
        data = client.bars(symbol=symbol, frequency=5, offset=offset)
        if data is not None and len(data) > 0:
            # 确保 datetime 列为标准日期格式
            if 'datetime' in data.columns:
                data['trade_date'] = pd.to_datetime(data['datetime']).dt.strftime('%Y-%m-%d')
            return data
        return pd.DataFrame()
    except Exception as e:
        print(f"  [ERROR] mootdx query failed: {e}")
        return pd.DataFrame()
    finally:
        client.client.close()


def print_sample(data: pd.DataFrame, symbol: str):
    """打印周线数据样本"""
    if data.empty:
        print(f"\n  [{symbol}] 无数据")
        return

    cols = [c for c in ['trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount'] if c in data.columns]
    print(f"\n  [{symbol}] 共 {len(data)} 条周线记录，最近 5 条：")
    print(data[cols].tail(5).to_string(index=False))


def test_all_bonds(bond_codes: list[str]):
    """全量测试"""
    from mootdx.quotes import Quotes

    client = Quotes.factory(market='std')
    results = {'ok': 0, 'empty': 0, 'error': 0}
    details = []

    for i, code in enumerate(bond_codes, 1):
        print(f"  [{i}/{len(bond_codes)}] {code}...", end=' ')
        try:
            data = client.bars(symbol=code, frequency=5, offset=5)
            if data is not None and len(data) > 0:
                last = data.iloc[-1]
                print(f"OK (close={last.close:.2f}, date={last.datetime})")
                results['ok'] += 1
                details.append({
                    'bond_code': code,
                    'latest_close': float(last.close),
                    'latest_date': str(last.datetime),
                })
            else:
                print("EMPTY")
                results['empty'] += 1
        except Exception as e:
            print(f"ERROR: {e}")
            results['error'] += 1
        time.sleep(0.3)

    client.client.close()

    print(f"\n结果统计: OK={results['ok']}, EMPTY={results['empty']}, ERROR={results['error']}")
    print(f"mootdx 覆盖率: {results['ok'] / len(bond_codes) * 100:.1f}%")

    # 保存结果
    out = os.path.join(os.path.dirname(__file__), '..', 'convertible_bond', 'weekly_kline_test_result.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'total': len(bond_codes), **results, 'details': details}, f, ensure_ascii=False, indent=2)
    print(f"结果已保存到: {out}")

    return results


def main():
    parser = argparse.ArgumentParser(description='可转债周线数据采集（mootdx）')
    parser.add_argument('--code', default='113667', help='转债代码（默认 113667）')
    parser.add_argument('--offset', type=int, default=10, help='获取条数（默认 10，最大 800）')
    parser.add_argument('--test-all', action='store_true', help='全量测试所有转债')
    parser.add_argument('--mode', choices=['daily', 'init'], default='daily',
                        help='daily=增量(offset=10), init=全量历史(offset=800)')
    args = parser.parse_args()

    # 全量测试模式
    if args.test_all:
        # 从本地 mock 数据读取转债代码列表
        mock_file = os.path.join(os.path.dirname(__file__), '..', 'web', 'mock', 'data.json')
        if os.path.exists(mock_file):
            with open(mock_file, 'r', encoding='utf-8') as f:
                bonds = json.load(f)
            codes = sorted(set(b['bond_code'] for b in bonds if b.get('bond_code')))
            print(f"从 mock 数据加载了 {len(codes)} 只转债代码")
        else:
            print("未找到 mock 数据文件，使用预置测试列表")
            codes = ['113667', '113678', '113050', '110044', '127005', '128095']
        return test_all_bonds(codes)

    # 单只转债测试
    offset = 800 if args.mode == 'init' else args.offset
    data = fetch_weekly(args.code, offset=offset)
    print_sample(data, args.code)

    # 同时获取日线做对比
    from mootdx.quotes import Quotes
    client = Quotes.factory(market='std')
    daily = client.bars(symbol=args.code, frequency=9, offset=5)
    if daily is not None and len(daily) > 0:
        print(f"\n  同期日线样本（最近 5 条）：")
        daily['trade_date'] = pd.to_datetime(daily['datetime']).dt.strftime('%Y-%m-%d')
        print(daily[['trade_date', 'open', 'high', 'low', 'close', 'volume']].tail(5).to_string(index=False))
    client.client.close()


if __name__ == '__main__':
    main()

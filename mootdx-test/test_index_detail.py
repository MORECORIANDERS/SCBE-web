"""
可转债等权指数 881385 详细信息
"""
from mootdx.quotes import Quotes
import json
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_index_detail():
    print("=== 获取指数 881385 详细信息 ===\n")

    client = Quotes.factory(market='std', server=('123.125.108.14', 7709))

    try:
        # 1. 日线数据
        print("--- 日线数据 (最近60条) ---")
        daily = client.index(symbol='881385', frequency=9, offset=60)
        if daily is not None and not daily.empty:
            print(f"共 {len(daily)} 条，最新收盘: {daily.iloc[-1]['close']}")
            print(daily.tail(5).to_string())

        # 2. 财务数据 finance()
        print("\n--- 财务数据 finance() ---")
        try:
            fin = client.finance(symbol='881385')
            if fin is not None and not fin.empty:
                print(fin.to_string())
            else:
                print("finance() 无数据")
        except Exception as e:
            print(f"finance() 错误: {e}")

        # 3. 板块成分 sector()
        print("\n--- 板块成分 sector() ---")
        try:
            sec = client.sector(symbol='881385')
            if sec is not None and not sec.empty:
                print(f"共 {len(sec)} 条成分")
                print(sec.head(20).to_string())
            else:
                print("sector() 无数据")
        except Exception as e:
            print(f"sector() 错误: {e}")

        # 4. 指数日K extended()
        print("\n--- 指数日K extended() ---")
        try:
            ext = client.extended(symbol='881385')
            if ext is not None and not ext.empty:
                print(f"共 {len(ext)} 条")
                print(ext.tail(5).to_string())
            else:
                print("extended() 无数据")
        except Exception as e:
            print(f"extended() 错误: {e}")

        # 5. 获取分钟数据
        print("\n--- 分钟数据 minute() ---")
        try:
            minute = client.minute(symbol='881385')
            if minute is not None and not minute.empty:
                print(f"共 {len(minute)} 条")
                print(minute.tail(10).to_string())
            else:
                print("minute() 无数据")
        except Exception as e:
            print(f"minute() 错误: {e}")

        # 6. 保存完整日线数据到JSON
        print("\n--- 保存完整数据 ---")
        full_daily = client.index(symbol='881385', frequency=9)
        if full_daily is not None and not full_daily.empty:
            # 计算统计指标
            closes = full_daily['close']
            stats = {
                'symbol': '881385',
                'name': '可转债等权指数',
                'latest_date': str(full_daily.iloc[-1].name),
                'latest_close': float(full_daily.iloc[-1]['close']),
                'latest_open': float(full_daily.iloc[-1]['open']),
                'latest_high': float(full_daily.iloc[-1]['high']),
                'latest_low': float(full_daily.iloc[-1]['low']),
                'total_records': len(full_daily),
                'statistics': {
                    'close_max': float(closes.max()),
                    'close_min': float(closes.min()),
                    'close_mean': float(closes.mean()),
                    'close_std': float(closes.std()),
                },
                'recent_5': [],
                'recent_30_stats': {}
            }

            # 最近5条
            for _, row in full_daily.tail(5).iterrows():
                stats['recent_5'].append({
                    'date': str(row.name),
                    'open': float(row['open']),
                    'close': float(row['close']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'amount': float(row['amount']),
                    'up_count': int(row['up_count']),
                    'down_count': int(row['down_count']),
                })

            # 最近30日统计
            recent30 = full_daily.tail(30)
            recent30_closes = recent30['close']
            recent30_change = recent30_closes.pct_change() * 100
            stats['recent_30_stats'] = {
                'count': 30,
                'close_max': float(recent30_closes.max()),
                'close_min': float(recent30_closes.min()),
                'close_mean': float(recent30_closes.mean()),
                'change_max': float(recent30_change.max()),
                'change_min': float(recent30_change.min()),
                'change_mean': float(recent30_change.mean()),
            }

            # 近一年高低点
            one_year = full_daily.tail(240)  # 约1年
            one_year_high = float(one_year['high'].max())
            one_year_low = float(one_year['low'].min())
            one_year_high_date = one_year[one_year['high'] == one_year_high].index[0]
            one_year_low_date = one_year[one_year['low'] == one_year_low].index[0]
            stats['one_year'] = {
                'high': one_year_high,
                'high_date': str(one_year_high_date),
                'low': one_year_low,
                'low_date': str(one_year_low_date),
            }

            json_path = os.path.join(OUTPUT_DIR, '881385_detail.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"已保存: {json_path}")
            print(json.dumps(stats, ensure_ascii=False, indent=2))

    finally:
        client.close()


if __name__ == '__main__':
    get_index_detail()
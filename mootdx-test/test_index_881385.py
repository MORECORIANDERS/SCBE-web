"""
可转债等权指数 881385 行情测试
测试 mootdx 获取指数 K 线数据并保存结果
"""
from mootdx.quotes import Quotes
from datetime import date
import json
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def test_index_881385():
    today = date.today()
    print(f"=== 测试获取可转债等权指数 881385 行情 ===")
    print(f"测试日期: {today}")

    servers = [
        ('123.125.108.14', 7709),
        ('110.41.147.124', 7709),
        ('110.41.147.115', 7709),
    ]

    client = None
    for ip, port in servers:
        print(f"\n尝试连接服务器 {ip}:{port} ...")
        try:
            client = Quotes.factory(market='std', server=(ip, port))
            test = client.bars(symbol='000001', frequency=9, offset=1)
            if test is not None and not test.empty:
                print(f"  ✅ 连接成功！")
                break
            else:
                client.close()
                client = None
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            client = None

    if client is None:
        print("\n所有服务器连接失败，退出。")
        return

    try:
        # 使用 index() 方法获取日线数据
        print("\n--- 使用 index() 获取日线数据 ---")
        index_data = client.index(symbol='881385', frequency=9)
        if index_data is not None and not index_data.empty:
            print(f"✅ 获取到 {len(index_data)} 条数据")
            print("\n最新10条:")
            print(index_data.tail(10).to_string())

            # 保存为 CSV
            csv_path = os.path.join(OUTPUT_DIR, '881385_daily.csv')
            index_data.to_csv(csv_path, encoding='utf-8-sig')
            print(f"\n已保存 CSV: {csv_path}")

            # 保存为 JSON（最新30条）
            latest30 = index_data.tail(30).reset_index(drop=True)
            records = latest30.to_dict(orient='records')
            json_path = os.path.join(OUTPUT_DIR, '881385_latest30.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'symbol': '881385',
                    'name': '可转债等权指数',
                    'date': str(today),
                    'total_count': len(index_data),
                    'data': records
                }, f, ensure_ascii=False, indent=2)
            print(f"已保存 JSON: {json_path}")

            # 打印最新一条的详细信息
            latest = index_data.iloc[-1]
            print(f"\n=== 今日行情 ({latest.name}) ===")
            print(f"  开盘: {latest['open']}")
            print(f"  收盘: {latest['close']}")
            print(f"  最高: {latest['high']}")
            print(f"  最低: {latest['low']}")
            print(f"  上涨家数: {latest['up_count']}")
            print(f"  下跌家数: {latest['down_count']}")
            print(f"  成交量: {latest['vol']}")
            print(f"  成交额: {latest['amount']:.2f} 元")
        else:
            print("❌ index() 方法未返回数据")

    finally:
        client.close()


if __name__ == '__main__':
    test_index_881385()
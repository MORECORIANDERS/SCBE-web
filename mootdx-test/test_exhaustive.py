"""
穷举 mootdx Quotes 所有接口，获取 881385 相关信息
只输出接口实际返回的内容，不做任何编造
"""
from mootdx.quotes import Quotes
import pandas as pd

client = Quotes.factory(market='std', server=('123.125.108.14', 7709))

symbol = '881385'
print(f"========== 穷举测试 881385 ==========\n")

# 获取所有 public 方法
methods = [m for m in dir(client) if not m.startswith('_')]
print(f"可用方法 ({len(methods)}): {methods}\n")

for method_name in methods:
    method = getattr(client, method_name)
    if not callable(method):
        print(f"[{method_name}] (属性值) = {method}")
        continue

    print(f"--- 调用 {method_name}() ---")

    # 根据方法名尝试不同参数
    try:
        if method_name in ('index', 'bars', 'minute', 'fzline', 'extended', 'finance'):
            result = method(symbol=symbol, frequency=9)
        elif method_name == 'quotes':
            result = method(symbol=symbol)
        elif method_name in ('block', 'sector', 'concept', 'industry'):
            result = method()
        elif method_name == 'transactions':
            result = method(symbol=symbol, start=0, count=10)
        elif method_name in ('stock_count',):
            result = method(symbol=symbol)
        else:
            try:
                result = method(symbol=symbol)
            except TypeError:
                try:
                    result = method(code=symbol)
                except TypeError:
                    result = method()
    except Exception as e:
        print(f"  [错误] {type(e).__name__}: {e}\n")
        continue

    if result is None:
        print(f"  [结果] None\n")
        continue

    if isinstance(result, pd.DataFrame):
        if result.empty:
            print(f"  [结果] 空 DataFrame (columns: {list(result.columns)})\n")
        else:
            print(f"  [结果] {len(result)} 行 x {len(result.columns)} 列")
            print(f"  [列名] {list(result.columns)}")
            # 显示前3行
            for i in range(min(3, len(result))):
                print(f"  行{i}: {dict(result.iloc[i])}")
            print()
    elif isinstance(result, (list, tuple)):
        if len(result) == 0:
            print(f"  [结果] 空列表\n")
        else:
            print(f"  [结果] 共 {len(result)} 项")
            for i, item in enumerate(result[:5]):
                print(f"  [{i}]: {item}")
            print()
    elif isinstance(result, dict):
        if len(result) == 0:
            print(f"  [结果] 空字典\n")
        else:
            print(f"  [结果] {result}\n")
    else:
        print(f"  [结果] ({type(result).__name__}) {result}\n")

client.close()
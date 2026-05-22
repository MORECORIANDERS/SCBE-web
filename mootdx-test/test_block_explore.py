"""
探索 mootdx 板块相关接口和数据
"""
from mootdx.quotes import Quotes

client = Quotes.factory(market='std', server=('123.125.108.14', 7709))
blk = client.block()

print(f"block() 总行数: {len(blk)}")
print(f"列: {list(blk.columns)}")
print()

# === 搜索可转债相关 ===
print("=" * 50)
print("搜索可转债相关板块")
print("=" * 50)
for keyword in ['转债', '债券', '可转换', '等权', '8813']:
    m = blk[blk['blockname'].str.contains(keyword, na=False)]
    print(f'  "{keyword}": {len(m)} 条')
    if len(m) > 0:
        print(m.head(5))
    print()

# === block_type 含义 ===
print("=" * 50)
print("block_type 分布及含义推断")
print("=" * 50)
type_counts = blk['block_type'].value_counts()
for bt, cnt in type_counts.head(10).items():
    samples = blk[blk['block_type'] == bt]['blockname'].unique()[:8]
    print(f"  block_type={bt:>6} ({cnt:>6}行) 示例: {list(samples)}")

print()

# === 板块名称分类 ===
print("=" * 50)
print("板块名称分类")
print("=" * 50)
names = blk['blockname'].unique()
print(f"共 {len(names)} 个不同的板块名称")

digit_names = [n for n in names if n[0].isdigit()]
chinese_names = [n for n in names if not n[0].isdigit()]

print(f"  数字代码型板块: {len(digit_names)} 个")
if digit_names:
    print(f"    示例: {digit_names[:15]}")
    print(f"    末尾示例: {digit_names[-10:]}")
print()
print(f"  中文名称板块: {len(chinese_names)} 个")
print(f"    示例: {chinese_names[:30]}")

print()

# === 查看一个板块的成分股 ===
print("=" * 50)
print("部分板块成分展示")
print("=" * 50)
for show_name in ['沪深300', '上证50', '中证500', '创业板指']:
    m = blk[blk['blockname'] == show_name]
    print(f"  {show_name}: {len(m)} 只成分")
    if len(m) > 0:
        print(f"    成分示例: {list(m['code'].head(5))}")
    print()

# === 查看可转债在 block 中的情况 ===
print("=" * 50)
print("查看可转债代码范围 (sh11xxxx / sz12xxxx)")
print("=" * 50)
# 看是否有 11/12 开头的代码
cb_codes = blk[blk['code'].str.match(r'^1[12]\d{4}$', na=False)]
print(f"代码为11/12开头的(疑似可转债): {len(cb_codes)} 条")
if len(cb_codes) > 0:
    print(cb_codes.head(20))

print()
print("=" * 50)
print("所有可用接口方法列表")
print("=" * 50)
methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
for m in sorted(methods):
    print(f"  {m}")

client.close()

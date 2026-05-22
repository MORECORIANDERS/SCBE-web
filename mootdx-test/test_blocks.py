"""
探索 mootdx block() 中所有板块数据
"""
from mootdx.quotes import Quotes

client = Quotes.factory(market='std', server=('123.125.108.14', 7709))
blk = client.block()

# block_type=2 的板块名称
sub2 = blk[blk['block_type'] == 2]
print('=== block_type=2 所有板块名称 ===')
for n in sub2['blockname'].unique():
    print(f'  [{n}]')

print()

# 其他类型
for bt in [12336, 12851, 13104, 12600, 12592, 12593]:
    sub = blk[blk['block_type'] == bt]
    names = sub['blockname'].unique()
    codes_example = [n for n in names][:8]
    print(f'block_type={bt:>6} ({len(sub):>6}行) 名称数: {len(names):>2} 示例: {codes_example}')

print()

# 搜索中文行业
print('=== 搜索中文关键词 ===')
all_names = blk['blockname'].unique()
for kw in ['行业', '概念', '板块', '制造', '金融', '医药', '科技', '地产', '能源', '消费', '材料', '信息', '指数', '风格']:
    found = [n for n in all_names if kw in str(n)]
    if found:
        print(f'  "{kw}": {found}')

# 展示 block_type=2 所有名称
print()
print('=== block_type=2 完整列表 ===')
for n in sorted(sub2['blockname'].unique()):
    print(f'  {n}')

client.close()

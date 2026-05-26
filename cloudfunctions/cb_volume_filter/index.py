"""
可转债成交量异动筛选云函数
====================================
触发时间：每天 15:50（收盘前10分钟，定时触发器）
策略：
  - 筛选当天成交额 >= 前5日（含）平均成交额 * 2 的可转债
  - 按剩余规模（latest_amount）升序排序
  - 返回字段：行业、到期日期、剩余规模、最新价格、成交额（亿元）
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/opt/python')

DB_CONFIG = {
    'host': 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com',
    'port': 27120,
    'user': 'cbreport',
    'password': 'huo22QQQ',
    'database': 'python12-9guk780v324f024d',
    'charset': 'utf8mb4',
    'connect_timeout': 30,
}

FEISHU_WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5'

HISTORY_QUERY_SQL = """
SELECT 
    bond_code,
    AVG(amount) AS avg_amount_5d
FROM (
    SELECT bond_code, amount
    FROM bond_snapshot
    WHERE trade_date <= %s
      AND trade_date >= %s
      AND amount > 0
) t
GROUP BY bond_code
"""


def get_db_connection():
    import pymysql
    return pymysql.connect(**DB_CONFIG)


def get_trading_days(conn, n=6):
    """获取最近 n 个交易日（包含今天）"""
    cur = conn.cursor()
    sql = """
        SELECT DISTINCT trade_date
        FROM bond_snapshot
        WHERE trade_date <= %s
        ORDER BY trade_date DESC
        LIMIT %s
    """
    today = datetime.now().date()
    cur.execute(sql, (today, n))
    rows = cur.fetchall()
    cur.close()
    return [r[0] for r in rows]


def get_hist_avg_amounts(conn, trading_days):
    """获取前5日（不含今天）的平均成交额"""
    if len(trading_days) < 2:
        return {}
    today = trading_days[0]
    five_days_ago = trading_days[-1]

    cur = conn.cursor()
    cur.execute(HISTORY_QUERY_SQL, (today, five_days_ago))
    rows = cur.fetchall()
    cur.close()
    return {r[0]: float(r[1]) for r in rows}


def filter_bonds(conn, today, avg_amounts):
    """筛选成交额异动转债"""
    cur = conn.cursor()
    results = []

    for bond_code, avg_amount in avg_amounts.items():
        if avg_amount <= 0:
            continue
        threshold = avg_amount * 2
        cur.execute("""
            SELECT 
                s.bond_code,
                s.bond_name,
                st.industry_all,
                st.maturity_date,
                st.latest_amount,
                s.price,
                s.amount,
                s.amount / 100000000 AS amount_yi
            FROM bond_snapshot s
            LEFT JOIN bond_static st ON s.bond_code = st.bond_code
            WHERE s.trade_date = %s
              AND s.bond_code = %s
              AND s.amount >= %s
            ORDER BY st.latest_amount ASC
        """, (today, bond_code, threshold))
        row = cur.fetchone()
        if row:
            results.append({
                'bond_code': row[0],
                'bond_name': row[1],
                'industry': row[2] or '未知',
                'maturity_date': str(row[3]) if row[3] else '未知',
                'remaining_scale': float(row[4]) if row[4] else 0,
                'price': float(row[5]) if row[5] else 0,
                'amount_yi': round(float(row[7]), 4) if row[7] else 0
            })

    cur.close()
    results.sort(key=lambda x: x['remaining_scale'])
    return results


def format_feishu_card(results, today_str):
    """格式化飞书消息卡片"""
    if not results:
        content = "今日无成交额异动可转债（成交额未达到前5日均值的2倍）"
    else:
        content = f"**📅 筛选日期：** {today_str}\n"
        content += f"**📊 筛选条件：** 当日成交额 ≥ 前5日平均成交额 × 2\n"
        content += f"**🔢 符合条件：** {len(results)} 只\n\n"
        content += "---\n\n"

        for i, r in enumerate(results, 1):
            scale_str = f"{r['remaining_scale']:.2f}亿"
            price_str = f"{r['price']:.2f}"
            amount_str = f"{r['amount_yi']:.4f}亿"
            industry = r['industry'][:15] if r['industry'] else '未知'
            maturity = r['maturity_date'][:10] if r['maturity_date'] != '未知' else '未知'

            content += f"**{i}. {r['bond_name']}**（{r['bond_code']}）\n"
            content += f"   • 行业：{industry}\n"
            content += f"   • 到期日：{maturity} | 剩余规模：{scale_str}\n"
            content += f"   • 现价：{price_str} | 成交额：{amount_str}\n\n"

    return content


def send_feishu(title, content):
    """发送飞书卡片消息"""
    payload = json.dumps({
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': title},
                'template': 'purple',
            },
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}},
                {'tag': 'hr'},
                {'tag': 'note', 'elements': [
                    {'tag': 'plain_text', 'content': f'函数: cb_volume_filter | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'}
                ]},
            ],
        },
    }).encode('utf-8')
    req = urllib.request.Request(FEISHU_WEBHOOK, data=payload,
                                 headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode('utf-8'))
        if result.get('code') == 0 or result.get('StatusCode') == 0:
            print('[飞书] 通知成功')
            return True
        else:
            print(f'[飞书] 发送失败: {result}')
            return False
    except Exception as e:
        print(f'[飞书] 异常: {e}')
        return False


def main(event, context):
    """云函数入口"""
    print('[cb_volume_filter] 开始执行...')

    try:
        conn = get_db_connection()

        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')

        trading_days = get_trading_days(conn, n=6)
        if len(trading_days) < 2:
            print('[cb_volume_filter] 历史数据不足，跳过')
            return {'success': False, 'message': '历史数据不足'}

        avg_amounts = get_hist_avg_amounts(conn, trading_days)
        if not avg_amounts:
            print('[cb_volume_filter] 无法获取历史平均成交额')
            return {'success': False, 'message': '历史数据为空'}

        results = filter_bonds(conn, today, avg_amounts)

        conn.close()

        print(f'[cb_volume_filter] 筛选结果: {len(results)} 只转债')

        content = format_feishu_card(results, today_str)
        send_feishu('📈 可转债成交额异动提醒', content)

        return {
            'success': True,
            'date': today_str,
            'total': len(results),
            'results': results
        }

    except Exception as e:
        print(f'[cb_volume_filter] 执行异常: {e}')
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    result = main(None, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
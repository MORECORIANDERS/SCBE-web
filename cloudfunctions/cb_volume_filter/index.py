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
    'host': os.environ.get('DB_HOST', 'sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com'),
    'port': int(os.environ.get('DB_PORT', '27120')),
    'user': os.environ.get('DB_USER', 'cbreport'),
    'password': os.environ.get('DB_PASSWORD', 'huo22QQQ'),
    'database': os.environ.get('DB_NAME', 'python12-9guk780v324f024d'),
    'charset': 'utf8mb4',
    'connect_timeout': 30,
}

FEISHU_WEBHOOK = os.environ.get('FEISHU_WEBHOOK', 'https://open.feishu.cn/open-apis/bot/v2/hook/ecedf7fa-9000-42bb-805c-e09d7fce5bb5')

FILTER_SQL = """
SELECT
    s.bond_code,
    s.bond_name,
    COALESCE(JSON_UNQUOTE(JSON_EXTRACT(si.industry, '$[0]."名称"')), s.industry1, '') AS industry,
    COALESCE(JSON_UNQUOTE(JSON_EXTRACT(si.industry, '$[1]."名称"')), '') AS industry_level2,
    COALESCE(JSON_UNQUOTE(JSON_EXTRACT(si.industry, '$[2]."名称"')), '') AS industry_level3,
    COALESCE(st.maturity_date, '') AS maturity_date,
    COALESCE(st.latest_amount, 0) AS latest_amount,
    s.price,
    s.change_pct,
    s.amount,
    s.amount / 100000000 AS amount_yi
FROM bond_snapshot s
LEFT JOIN bond_static st ON s.bond_code = st.bond_code
LEFT JOIN sina_stock_info si ON CAST(st.stock_code_no_suffix AS CHAR) = CAST(si.stock_code AS CHAR)
JOIN (
    SELECT bond_code, AVG(amount) AS avg_amount_5d
    FROM bond_snapshot
    WHERE trade_date >= %s AND trade_date < %s
      AND amount > 0
    GROUP BY bond_code
) hist ON s.bond_code = hist.bond_code
WHERE s.trade_date = %s
  AND s.amount >= hist.avg_amount_5d * 2
  AND hist.avg_amount_5d > 0
ORDER BY st.latest_amount ASC
"""


def get_db_connection():
    import pymysql
    return pymysql.connect(**DB_CONFIG)


def filter_volume_anomalies(conn, today):
    """单条 SQL 筛选成交额异动转债（替代原 N+1 方式）"""
    cur = conn.cursor()
    # 取前5个交易日（不含今天）作为基准
    cur.execute("""
        SELECT DISTINCT trade_date FROM bond_snapshot
        WHERE trade_date < %s ORDER BY trade_date DESC LIMIT 5
    """, (today,))
    hist_days = cur.fetchall()
    if len(hist_days) < 3:
        return []

    five_days_ago = hist_days[-1][0]

    cur.execute(FILTER_SQL, (five_days_ago, today, today))
    rows = cur.fetchall()
    cur.close()

    results = []
    for row in rows:
        results.append({
            'bond_code': row[0],
            'bond_name': row[1],
            'industry': str(row[2] or ''),
            'industry_level2': str(row[3] or ''),
            'industry_level3': str(row[4] or ''),
            'maturity_date': str(row[5]) if row[5] else '',
            'remaining_scale': float(row[6]) if row[6] else 0,
            'price': float(row[7]) if row[7] else 0,
            'change_pct': float(row[8]) if row[8] else None,
            'amount_yi': round(float(row[10]), 4) if row[10] else 0
        })

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
            industry = r['industry'][:15] if r['industry'] else ''
            maturity = r['maturity_date'][:10] if r['maturity_date'] else ''

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


def save_to_strategy_table(conn, results, today_str):
    """将成交额异动结果保存到 daily_strategy 表"""
    if not results:
        return
    cur = conn.cursor()
    insert_sql = """
        INSERT INTO daily_strategy
            (trade_date, strategy_type, bond_code, bond_name, price, change_pct, industry, industry_level1, industry_level2, industry_level3, remain_scale, maturity_date, cci, wr, is_oversold, amount_yi, created_at, updated_at)
        VALUES (%s, 'volume', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, 0, %s, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
            bond_name = VALUES(bond_name),
            price = VALUES(price),
            change_pct = VALUES(change_pct),
            industry = VALUES(industry),
            industry_level1 = VALUES(industry_level1),
            industry_level2 = VALUES(industry_level2),
            industry_level3 = VALUES(industry_level3),
            remain_scale = VALUES(remain_scale),
            maturity_date = VALUES(maturity_date),
            amount_yi = VALUES(amount_yi),
            updated_at = NOW()
    """
    for r in results:
        try:
            cur.execute(insert_sql, (
                today_str,
                r['bond_code'],
                r['bond_name'],
                r['price'],
                r['change_pct'],
                r['industry'],
                r['industry'],
                r['industry_level2'],
                r['industry_level3'],
                r['remaining_scale'],
                r['maturity_date'],
                r['amount_yi']
            ))
        except Exception as e:
            print(f"[保存失败] {r['bond_code']}: {e}")
    conn.commit()
    cur.close()
    print(f"[cb_volume_filter] 已保存 {len(results)} 条记录到 daily_strategy(volume)")


def main(event, context):
    """云函数入口"""
    print('[cb_volume_filter] 开始执行...')

    try:
        conn = get_db_connection()

        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')

        results = filter_volume_anomalies(conn, today)

        print(f'[cb_volume_filter] 筛选结果: {len(results)} 只转债')

        save_to_strategy_table(conn, results, today_str)

        conn.close()

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

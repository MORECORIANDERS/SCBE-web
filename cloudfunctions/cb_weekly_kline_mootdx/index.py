"""
可转债周线数据采集云函数
====================
触发时间：每周五 16:00（收盘后，定时触发器）
策略：
  init   模式 — 通过 mootdx 获取全量历史周线（仅初始化时手动触发一次）
  weekly 模式 — 通过 mootdx 拉最近30交易日日线，upsert 当周数据（定时触发）
  daily  模式 — 从 bond_kline + bond_snapshot 聚合周线（保留备用）
"""

import json
import os
import pathlib
import sys
import time
from datetime import datetime, timedelta

# 云函数只读文件系统补丁（必须在导入 mootdx 之前）
pathlib.Path.home = classmethod(lambda cls: pathlib.Path('/tmp'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mootdx.quotes import Quotes

# ============ 配置 ============

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

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bond_weekly_kline (
  bond_code  VARCHAR(20)    NOT NULL COMMENT '转债代码',
  trade_week DATE           NOT NULL COMMENT '该周周一日期',
  open       DECIMAL(10,3)  NOT NULL COMMENT '周开盘价',
  high       DECIMAL(10,3)  NOT NULL COMMENT '周最高价',
  low        DECIMAL(10,3)  NOT NULL COMMENT '周最低价',
  close      DECIMAL(10,3)  NOT NULL COMMENT '周收盘价',
  volume     BIGINT         DEFAULT 0 COMMENT '周成交量（股）',
  amount     DECIMAL(20,4)  DEFAULT 0 COMMENT '周成交额（元）',
  source     VARCHAR(10)    DEFAULT 'mootdx' COMMENT '数据来源: mootdx/bond_kline',
  updated_at DATETIME       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (bond_code, trade_week)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='可转债周K线数据';
"""

UPSERT_SQL = """
INSERT INTO bond_weekly_kline (bond_code, trade_week, open, high, low, close, volume, amount, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  open     = VALUES(open),
  high     = VALUES(high),
  low      = VALUES(low),
  close    = VALUES(close),
  volume   = VALUES(volume),
  amount   = VALUES(amount),
  source   = VALUES(source),
  updated_at = NOW()
"""

# 检查 bond_kline 是否有 volume/amount/open 列
CHECK_COLUMNS_SQL = """
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'bond_kline'
  AND COLUMN_NAME IN ('open', 'volume', 'amount')
"""


# ============ 工具函数 ============

def get_db_connection():
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor'))
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    conn.autocommit(True)
    return conn


def send_feishu(title: str, content: str, template: str = 'blue'):
    """发送飞书卡片消息"""
    import urllib.request
    payload = json.dumps({
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': title},
                'template': template,
            },
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}},
                {'tag': 'hr'},
                {'tag': 'note', 'elements': [
                    {'tag': 'plain_text', 'content': f'函数: cb_weekly_kline_mootdx | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'}
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
        else:
            print(f'[飞书] 发送失败: {result}')
    except Exception as e:
        print(f'[飞书] 异常: {e}')


# ============ Init 模式：mootdx 全量获取 ============

def fetch_weekly_mootdx(client: Quotes, symbol: str, offset: int = 800) -> list | None:
    """通过 mootdx 获取周线数据（默认800条日线≈3年）"""
    try:
        data = client.bars(symbol=symbol, frequency=5, offset=offset)
        if data is None or len(data) == 0:
            return None
        records = []
        for _, row in data.iterrows():
            if float(row['close']) <= 0:
                continue
            dt = row.get('datetime')
            if dt is None:
                continue
            date_str = str(dt)[:10]
            d = datetime.strptime(date_str[:10], '%Y-%m-%d')
            trade_week = (d - timedelta(days=d.weekday())).strftime('%Y-%m-%d')
            records.append({
                'bond_code': symbol,
                'trade_week': trade_week,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(float(row.get('volume', 0) or 0)),
                'amount': float(row.get('amount', 0) or 0),
                'source': 'mootdx',
            })
        return records if records else None
    except Exception as e:
        print(f'    [mootdx] {symbol} 查询失败: {e}')
        return None


def run_init_mode(conn):
    """init 模式：通过 mootdx 获取全部历史周线"""
    import random
    import time as _time

    cursor = conn.cursor()
    cursor.execute(
        "SELECT bond_code, bond_name FROM bond_list WHERE is_active = 1 ORDER BY bond_code"
    )
    bonds = cursor.fetchall()
    cursor.close()
    print(f'[Init] 获取到 {len(bonds)} 只活跃转债')

    client = Quotes.factory(market='std')
    stats = {'ok': 0, 'failed': 0, 'total_records': 0}
    missing_bonds = []

    try:
        for i, (bond_code, bond_name) in enumerate(bonds, 1):
            print(f'[{i}/{len(bonds)}] {bond_code} {bond_name}...', end=' ')
            records = fetch_weekly_mootdx(client, bond_code)

            if not records:
                print('无数据')
                stats['failed'] += 1
                missing_bonds.append(f'{bond_code}({bond_name})')
                continue

            params_list = [
                (rec['bond_code'], rec['trade_week'],
                 rec['open'], rec['high'], rec['low'], rec['close'],
                 rec['volume'], rec['amount'], rec['source'])
                for rec in records
            ]

            w_cursor = conn.cursor()
            try:
                w_cursor.executemany(UPSERT_SQL, params_list)
                written = len(params_list)
            except Exception as e:
                print(f'批量写入失败: {e}，改用单条写入')
                written = 0
                for rec in records:
                    try:
                        w_cursor.execute(UPSERT_SQL, (
                            rec['bond_code'], rec['trade_week'],
                            rec['open'], rec['high'], rec['low'], rec['close'],
                            rec['volume'], rec['amount'], rec['source'],
                        ))
                        written += 1
                    except Exception as ex:
                        print(f'    [DB] {rec["trade_week"]} 失败: {ex}')
            finally:
                w_cursor.close()

            stats['ok'] += 1
            stats['total_records'] += written
            print(f'OK ({written} 条)')

            _time.sleep(random.uniform(0.3, 0.8))

            if i % 50 == 0:
                print(f'  [进度] {i}/{len(bonds)}, OK={stats["ok"]}, 失败={stats["failed"]}, 写入={stats["total_records"]}')

    finally:
        client.client.close()

    return stats, missing_bonds


# ============ Daily 模式：从日线聚合 ============

def get_weekly_boundaries() -> tuple[str, str]:
    """获取需要聚合的周范围：本周一和前周一"""
    today = datetime.now()
    this_monday = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    last_monday = (today - timedelta(days=today.weekday() + 7)).strftime('%Y-%m-%d')
    return last_monday, this_monday


def build_kline_agg_sql(has_open: bool, has_volume: bool, has_amount: bool) -> str:
    """动态构建 bond_kline 聚合 SQL（适配不同表结构）"""
    open_field = 'MIN(open) AS open' if has_open else '0 AS open'
    volume_field = 'SUM(volume) AS volume' if has_volume else '0 AS volume'
    amount_field = 'SUM(amount) AS amount' if has_amount else '0 AS amount'

    return f"""
    SELECT
        bond_code,
        trade_week,
        {open_field},
        MAX(high) AS high,
        MIN(low) AS low,
        close_last AS `close`,
        {volume_field},
        {amount_field}
    FROM (
        SELECT
            SUBSTRING(symbol, 3) AS bond_code,
            DATE_SUB(trade_date, INTERVAL WEEKDAY(trade_date) DAY) AS trade_week,
            open, high, low,
            FIRST_VALUE(`close`) OVER (
                PARTITION BY SUBSTRING(symbol, 3), DATE_SUB(trade_date, INTERVAL WEEKDAY(trade_date) DAY)
                ORDER BY trade_date DESC
            ) AS close_last,
            volume, amount
        FROM bond_kline
        WHERE trade_date >= %s AND trade_date <= %s
    ) t
    GROUP BY bond_code, trade_week, close_last
    """


def build_snapshot_agg_sql() -> str:
    """从 bond_snapshot 聚合（补最近日线）"""
    return """
    SELECT
        bond_code,
        DATE_SUB(trade_date, INTERVAL WEEKDAY(trade_date) DAY) AS trade_week,
        SUBSTRING_INDEX(GROUP_CONCAT(CAST(open_price AS CHAR) ORDER BY trade_date), ',', 1) AS open,
        MAX(high_price) AS high,
        MIN(low_price) AS low,
        SUBSTRING_INDEX(GROUP_CONCAT(CAST(price AS CHAR) ORDER BY trade_date DESC), ',', 1) AS `close`,
        SUM(COALESCE(volume, 0)) AS volume,
        SUM(COALESCE(amount, 0)) AS amount
    FROM bond_snapshot
    WHERE trade_date >= %s AND trade_date <= %s
      AND price > 0 AND open_price IS NOT NULL
    GROUP BY bond_code, trade_week
    """


def check_table_columns(conn) -> set:
    """检查 bond_kline 表有哪些可用字段"""
    cursor = conn.cursor()
    try:
        cursor.execute(CHECK_COLUMNS_SQL, (DB_CONFIG['database'],))
        cols = {row[0] for row in cursor.fetchall()}
        return cols
    except Exception:
        return set()
    finally:
        cursor.close()


def run_daily_mode(conn):
    """daily 模式：从 bond_kline + bond_snapshot 聚合周线"""
    last_monday, this_monday = get_weekly_boundaries()
    # 拉取从上周一到今天的数据
    today = datetime.now().strftime('%Y-%m-%d')
    print(f'[Daily] 聚合范围: {last_monday} ~ {today}')

    # 检查 bond_kline 有哪些字段
    cols = check_table_columns(conn)
    has_open = 'open' in cols
    has_volume = 'volume' in cols
    has_amount = 'amount' in cols
    print(f'[Daily] bond_kline 可用字段: open={has_open}, volume={has_volume}, amount={has_amount}')

    # 1. 从 bond_kline 聚合
    kline_sql = build_kline_agg_sql(has_open, has_volume, has_amount)
    cursor = conn.cursor()
    cursor.execute(kline_sql, (last_monday, today))
    kline_rows = cursor.fetchall()
    cursor.close()
    print(f'[Daily] bond_kline: {len(kline_rows)} 条周线记录')
    for r in kline_rows[:3]:
        print(f'  sample: {r}')

    # 2. 从 bond_snapshot 补最新数据
    cursor = conn.cursor()
    cursor.execute(build_snapshot_agg_sql(), (last_monday, today))
    snap_rows = cursor.fetchall()
    cursor.close()
    print(f'[Daily] bond_snapshot: {len(snap_rows)} 条周线记录')

    # 3. 合并（bond_kline 优先，snapshot 补充缺失的）
    merged = {}
    for row in kline_rows:
        code = row[0]
        week = str(row[1])[:10]
        key = f'{code}_{week}'
        merged[key] = {
            'bond_code': code,
            'trade_week': week,
            'open': float(row[2] or 0),
            'high': float(row[3] or 0),
            'low': float(row[4] or 0),
            'close': float(row[5] or 0),
            'volume': int(row[6] or 0),
            'amount': float(row[7] or 0),
            'source': 'bond_kline',
        }

    for row in snap_rows:
        code = row[0]
        week = str(row[1])[:10]
        key = f'{code}_{week}'
        if key not in merged:
            merged[key] = {
                'bond_code': code,
                'trade_week': week,
                'open': float(row[2] or 0),
                'high': float(row[3] or 0),
                'low': float(row[4] or 0),
                'close': float(row[5] or 0),
                'volume': int(row[6] or 0),
                'amount': float(row[7] or 0),
                'source': 'bond_kline',
            }

    print(f'[Daily] 合并后: {len(merged)} 条周线')

    # 4. 写入数据库
    written = 0
    w_cursor = conn.cursor()
    for rec in merged.values():
        try:
            w_cursor.execute(UPSERT_SQL, (
                rec['bond_code'], rec['trade_week'],
                rec['open'], rec['high'], rec['low'], rec['close'],
                rec['volume'], rec['amount'], rec['source'],
            ))
            written += 1
        except Exception as e:
            print(f'    [DB] {rec["bond_code"]} {rec["trade_week"]} 写入失败: {e}')
    w_cursor.close()
    conn.commit()

    return written, len(merged), len(kline_rows), len(snap_rows)


# ============ Weekly 模式：mootdx 直拉当周 ============

def run_weekly_mode(conn):
    """weekly 模式：每周五16点触发，只更新当周数据

    通过 mootdx 拉取最近30个交易日日线（约6周），
    聚合出当周（本周一~今天）数据，upsert 到数据库。
    """
    import time as _time

    today = datetime.now()
    this_monday = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')

    cursor = conn.cursor()
    cursor.execute(
        "SELECT bond_code, bond_name FROM bond_list WHERE is_active = 1 ORDER BY bond_code"
    )
    bonds = cursor.fetchall()
    cursor.close()
    print(f'[Weekly] 活跃转债: {len(bonds)} 只，目标周: {this_monday}')

    client = Quotes.factory(market='std')
    written = 0
    failed = 0

    try:
        for i, (bond_code, bond_name) in enumerate(bonds, 1):
            records = fetch_weekly_mootdx(client, bond_code, offset=30)
            if not records:
                failed += 1
                continue

            this_week_records = [r for r in records if r['trade_week'] == this_monday]
            if not this_week_records:
                print(f'[{i}/{len(bonds)}] {bond_code} 无当周数据（可能今日非交易日）')
                continue

            params_list = [
                (rec['bond_code'], rec['trade_week'],
                 rec['open'], rec['high'], rec['low'], rec['close'],
                 rec['volume'], rec['amount'], rec['source'])
                for rec in this_week_records
            ]

            w_cursor = conn.cursor()
            w_cursor.executemany(UPSERT_SQL, params_list)
            w_cursor.close()
            written += len(params_list)

            print(f'[{i}/{len(bonds)}] {bond_code} 当周 {this_monday} OK ({len(params_list)} 条)')
            _time.sleep(0.2)

    finally:
        client.client.close()

    return written, len(bonds), failed


# ============ 主入口 ============

def main(event, context):
    mode = event.get('mode', 'weekly') if isinstance(event, dict) else 'weekly'
    if mode not in ('daily', 'init', 'weekly'):
        mode = 'weekly'

    print(f'[入口] cb_weekly_kline_mootdx, mode={mode}')
    start_time = time.time()

    conn = get_db_connection()
    try:
        # 确保表存在，补齐旧表可能缺少的列
        cursor = conn.cursor()
        try:
            cursor.execute("""
                ALTER TABLE bond_weekly_kline
                ADD COLUMN IF NOT EXISTS open  DECIMAL(10,3)  NOT NULL DEFAULT 0 COMMENT '周开盘价' AFTER trade_week,
                ADD COLUMN IF NOT EXISTS high  DECIMAL(10,3)  NOT NULL DEFAULT 0 COMMENT '周最高价' AFTER open,
                ADD COLUMN IF NOT EXISTS low   DECIMAL(10,3)  NOT NULL DEFAULT 0 COMMENT '周最低价'  AFTER high,
                ADD COLUMN IF NOT EXISTS source VARCHAR(10)    DEFAULT 'mootdx' COMMENT '数据来源' AFTER amount
            """)
        except Exception:
            pass
        for stmt in CREATE_TABLE_SQL.split(';'):
            s = stmt.strip()
            if s:
                try:
                    cursor.execute(s + ';')
                except Exception:
                    pass
        cursor.close()

        if mode == 'init':
            stats, missing_bonds = run_init_mode(conn)
            elapsed = time.time() - start_time
            coverage = stats['ok'] / (stats['ok'] + stats['failed']) * 100 if (stats['ok'] + stats['failed']) > 0 else 0

            missing_text = ''
            if missing_bonds:
                missing_text = f'\n**无周线数据的转债**: {", ".join(missing_bonds[:15])}'
                if len(missing_bonds) > 15:
                    missing_text += f'\n共 {len(missing_bonds)} 只'

            send_feishu(
                '可转债周线初始化完成',
                f'**方式**: mootdx 全量获取\n'
                f'**成功**: {stats["ok"]} 只\n'
                f'**失败**: {stats["failed"]} 只\n'
                f'**写入**: {stats["total_records"]} 条\n'
                f'**通达信覆盖率**: {coverage:.1f}%{missing_text}\n'
                f'**耗时**: {elapsed:.0f}s',
                template='green' if stats['ok'] > 0 else 'red'
            )
            return {
                'code': 0,
                'data': {
                    'mode': 'init',
                    'ok': stats['ok'],
                    'failed': stats['failed'],
                    'total_records': stats['total_records'],
                    'coverage_pct': round(coverage, 1),
                    'missing_bonds': missing_bonds,
                    'elapsed_s': round(elapsed),
                }
            }

        elif mode == 'weekly':
            written, total_bonds, failed = run_weekly_mode(conn)
            elapsed = time.time() - start_time

            send_feishu(
                '可转债周线更新完成',
                f'**方式**: mootdx 直拉日线聚合\n'
                f'**目标周**: 本周\n'
                f'**处理**: {total_bonds} 只\n'
                f'**无数据**: {failed} 只\n'
                f'**写入**: {written} 条\n'
                f'**耗时**: {elapsed:.0f}s',
                template='blue'
            )
            return {
                'code': 0,
                'data': {
                    'mode': 'weekly',
                    'written': written,
                    'total_bonds': total_bonds,
                    'failed': failed,
                    'elapsed_s': round(elapsed),
                }
            }

        else:
            written, total, kline_count, snap_count = run_daily_mode(conn)
            elapsed = time.time() - start_time

            send_feishu(
                '可转债周线更新完成',
                f'**方式**: bond_kline + snapshot 聚合\n'
                f'**聚合范围**: 最近 2 周\n'
                f'**bond_kline来源**: {kline_count} 条\n'
                f'**snapshot补充**: {snap_count} 条\n'
                f'**合并后写入**: {written} 条\n'
                f'**耗时**: {elapsed:.0f}s',
                template='blue'
            )
            return {
                'code': 0,
                'data': {
                    'mode': 'daily',
                    'written': written,
                    'total_records': total,
                    'kline_count': kline_count,
                    'snapshot_count': snap_count,
                    'elapsed_s': round(elapsed),
                }
            }

    except Exception as e:
        print(f'[错误] {e}')
        send_feishu('可转债周线采集异常', f'**错误**: {e}', template='red')
        return {'code': -1, 'message': str(e)}
    finally:
        conn.close()


if __name__ == '__main__':
    test_event = {'mode': 'init'}
    result = main(test_event, {})
    print('\n结果:', json.dumps(result, ensure_ascii=False, indent=2))

"""
初始化 bond_list 表（可转债代码基础信息表）
从 CSV 文件导入初始数据，后续由 fetch_and_save_snapshot.py 增量更新
"""
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "convertible_bond" / "all_convertible_bonds_sina_20260518.csv"

DB_CONFIG = {
    "host": "sh-cynosdbmysql-grp-3bg1w6t8.sql.tencentcdb.com",
    "port": 27120,
    "user": "cbreport",
    "password": "huo22QQQ",
    "database": "python12-9guk780v324f024d",
    "charset": "utf8mb4",
}


def setup_db():
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    return conn


def create_table(conn):
    """创建 bond_list 表"""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bond_list (
            bond_code VARCHAR(20) NOT NULL PRIMARY KEY COMMENT '转债代码',
            bond_name VARCHAR(50) DEFAULT '' COMMENT '转债名称',
            market VARCHAR(10) DEFAULT '' COMMENT '市场（沪市/深市）',
            is_active TINYINT(1) DEFAULT 1 COMMENT '是否在交易（1=是，0=否）',
            created_at DATE COMMENT '首次入库日期',
            updated_at DATE COMMENT '最后更新日期',
            INDEX idx_market (market)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='可转债代码基础信息表'
    """)

    conn.commit()
    cur.close()
    print("✓ bond_list 表创建成功")


def import_from_csv(conn, csv_path: str):
    """从 CSV 导入初始数据"""
    if not os.path.exists(csv_path):
        print(f"✗ CSV 文件不存在: {csv_path}")
        return

    cur = conn.cursor()
    df = pd.read_csv(csv_path)

    today = datetime.now().strftime('%Y-%m-%d')

    sql = """
        INSERT INTO bond_list (bond_code, bond_name, market, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, 1, %s, %s)
        ON DUPLICATE KEY UPDATE
            bond_name = VALUES(bond_name),
            market = VALUES(market),
            updated_at = VALUES(updated_at)
    """

    inserted = 0
    updated = 0

    for idx, row in df.iterrows():
        bond_code = str(row["转债代码"]).zfill(6)
        bond_name = str(row.get("转债名称", "")).strip() if row.get("转债名称") else ""
        market = str(row.get("市场", "")).strip() if row.get("市场") else ""

        try:
            cur.execute(sql, (bond_code, bond_name, market, today, today))
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1
        except Exception as e:
            print(f"  ✗ {bond_code}: {e}")

    conn.commit()
    cur.close()

    print(f"✓ 数据导入完成: 新增 {inserted}, 更新 {updated}")


def main():
    print("=" * 60)
    print("初始化 bond_list 表")
    print("=" * 60)

    conn = setup_db()
    print("\n1. 创建表结构...")
    create_table(conn)

    print("\n2. 从 CSV 导入初始数据...")
    if os.path.exists(CSV_PATH):
        import_from_csv(conn, str(CSV_PATH))
    else:
        print(f"  ⚠ CSV 文件不存在，跳过导入: {CSV_PATH}")
        print(f"  请先运行 fetch_sina_cb_quotes.py 获取最新数据")

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM bond_list")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"初始化完成!")
    print(f"  bond_list 表记录数: {count}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

import json
import os
import sys

sys.path.insert(0, '/opt')
sys.path.insert(0, '/opt/python')

import pymysql


def main(event, context):
    results = {}

    try:
        results['pymysql_version'] = pymysql.__version__
    except Exception as e:
        results['pymysql_import_error'] = str(e)

    try:
        conn = pymysql.connect(
            host=os.environ.get('DB_HOST', ''),
            port=int(os.environ.get('DB_PORT', '3306')),
            user=os.environ.get('DB_USER', ''),
            password=os.environ.get('DB_PASSWORD', ''),
            database=os.environ.get('DB_NAME', ''),
            charset='utf8mb4',
            connect_timeout=10,
        )
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 AS result')
            row = cursor.fetchone()
            results['db_query'] = f'SELECT 1 = {row[0]}'

        with conn.cursor() as cursor:
            cursor.execute('SELECT DATABASE() AS db, VERSION() AS ver, NOW() AS now')
            row = cursor.fetchone()
            results['db_info'] = {
                'database': row[0],
                'version': row[1],
                'server_time': str(row[2]),
            }

        conn.close()
        results['db_connect'] = 'success'
    except Exception as e:
        results['db_connect'] = f'failed: {str(e)}'

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(results, ensure_ascii=False, default=str),
    }

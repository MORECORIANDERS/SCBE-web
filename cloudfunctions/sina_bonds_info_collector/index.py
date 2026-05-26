# -*- coding: utf-8 -*-
import os
import sys
import datetime
import json
import time
import random
import re
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pymysql
    from db_config import DB_CONFIG
    HAS_DB = True
except ImportError:
    HAS_DB = False

BOND_DAILY_JSON = os.path.join(os.path.dirname(__file__), 'test_output', 'sina_bonds_daily_20260513.json')
REQUEST_INTERVAL = (2, 4)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    'Referer': 'https://gu.sina.cn/'
}

TEST_MODE = False
TEST_BOND_CODES = ['113050', '127005']


def _parse_jsonp(text: str) -> dict:
    text = re.sub(r'^/\*.*?\*/', '', text).strip()
    text = re.sub(r'^[a-zA-Z_]\w*\(', '', text)
    text = re.sub(r'\);?\s*$', '', text)
    return json.loads(text)


def _try_num(s):
    if s in (None, '', '--'):
        return None
    s = str(s).replace(',', '')
    try:
        return float(s) if '.' in s else int(s)
    except (ValueError, TypeError):
        return None


class SinaBondInfoCollector:
    def __init__(self, test_mode: bool = TEST_MODE):
        self.test_mode = test_mode
        self.session = requests.Session()
        self.results = []

    def get_bond_codes(self) -> list:
        if self.test_mode:
            return TEST_BOND_CODES
        return self._get_codes_from_json()

    def _get_codes_from_json(self) -> list:
        try:
            with open(BOND_DAILY_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            codes = [
                b['bond_code'] for b in data.get('bonds', [])
                if b.get('price', 0) > 0
            ]
            return codes
        except FileNotFoundError:
            print(f"[ERROR] File not found: {BOND_DAILY_JSON}")
            return []
        except Exception as e:
            print(f"[ERROR] Read file failed: {e}")
            return []

    def get_bond_info(self, bond_code: str):
        url = 'https://quotes.sina.com.cn/bd/api/openapi.php/BondService2021.getBondInfo'
        params = {'symbol': f'sh{bond_code}', 'callback': 'hqccall_bondinfo'}

        try:
            time.sleep(random.uniform(*REQUEST_INTERVAL))
            response = self.session.get(url, params=params, headers=HEADERS, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                return None

            return self._parse_bond_info_response(response.text, bond_code)

        except requests.RequestException as e:
            print(f"  [WARN] Fetch {bond_code} failed: {e}")
            return None

    def _parse_bond_info_response(self, text: str, bond_code: str):
        try:
            data = _parse_jsonp(text)
            result_data = data.get('result', {}).get('data', {})

            if not result_data:
                return None

            conver = result_data.get('converInfo', {})
            bond = result_data.get('baseInfo', {})

            info = {
                'bond_code': bond_code,
                'name': bond.get('BondSName', ''),
                'stock_name': conver.get('SKSENAME', ''),
                'stock_code': conver.get('SKCODE', ''),
                'stock_symbol': conver.get('SYMBOL', ''),
                '转股起始日': conver.get('ZGQSR', ''),
                '转股截止日': conver.get('ZGJZR', ''),
                '强赎触发价': _try_num(conver.get('QSCFPrice', '')),
                '赎回锁定期': conver.get('QSQSR', ''),
                '最新赎回价': _try_num(conver.get('ZXSHPrice', '')) or '--',
                '回售触发价': _try_num(conver.get('HSCFPrice', '')),
                '回售锁定期': conver.get('HSQSR', ''),
                '最新回售价': _try_num(conver.get('ZXHSPrice', '')),
                '最新回售日期': conver.get('ZXHSR', ''),
                '修正触发价': _try_num(conver.get('XZCFPrice', '')),
                '当前转股价': _try_num(conver.get('DQZGPrice', '')),
                '发行价格': _try_num(bond.get('Value', '')),
                '发行规模(万元)': _try_num(bond.get('FXGM', '')),
                '剩余规模': bond.get('SYGM', ''),
                '起息日期': bond.get('BeginDate', ''),
                '到期日期': bond.get('PayDate', ''),
                '付息方式': bond.get('PayFreq', ''),
                '到期赎回价格': _try_num(bond.get('DQSHPrice', '')) or _try_num(conver.get('DQSHPrice', '')),
                '债券评级': bond.get('XYPJ', ''),
                '债券全称': bond.get('BondName', ''),
                '债券简称': bond.get('BondSName', ''),
                '债券期限(年)': _try_num(bond.get('BondLife', '')),
                '利息说明': bond.get('LLSM', ''),
            }

            return info

        except (json.JSONDecodeError, AttributeError) as e:
            print(f"  [WARN] Parse {bond_code} failed: {e}")
            return None

    def save_to_json(self, bonds_info: list) -> str:
        if not bonds_info:
            return None

        output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
        os.makedirs(output_dir, exist_ok=True)

        filename = f"sina_bonds_info_{datetime.date.today().strftime('%Y%m%d')}.json"
        filepath = os.path.join(output_dir, filename)

        data = {
            'update_date': datetime.date.today().strftime('%Y-%m-%d'),
            'count': len(bonds_info),
            'bonds': bonds_info
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[JSON] Saved: {filepath}")
        return filepath

    def run(self):
        print("=" * 60)
        print("Bond Info Collector (Cloud Function)")
        print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        bond_codes = self.get_bond_codes()

        if not bond_codes:
            print("WARNING: No bond codes")
            return {'success': False, 'count': 0, 'saved': 0, 'message': 'No bond codes'}

        print(f"Total: {len(bond_codes)} bonds to fetch")

        all_info = []
        for i, code in enumerate(bond_codes):
            print(f"  [{i+1}/{len(bond_codes)}] Fetch {code}...", end='')
            info = self.get_bond_info(code)
            if info:
                print(" OK")
                all_info.append(info)
            else:
                print(" FAIL")

        print(f"\nTotal fetched: {len(all_info)} bonds")

        self.save_to_json(all_info)
        self.results = all_info

        return {
            'success': True,
            'count': len(all_info),
            'saved': 0,
            'message': f'Fetched {len(all_info)} bonds'
        }


def main(event, context):
    collector = SinaBondInfoCollector(test_mode=False)
    result = collector.run()
    return {
        'code': 0 if result['success'] else -1,
        'data': result
    }
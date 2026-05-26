# -*- coding: utf-8 -*-
import os
import sys
import datetime
import json
import time
import random
import re
from typing import Optional, List, Dict
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_MODE = False
TEST_STOCK_CODES = ['603890']

BOND_INFO_JSON = os.path.join(os.path.dirname(__file__), 'test_output', 'sina_bonds_info_20260513.json')
REQUEST_INTERVAL = (2, 4)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://quotes.sina.cn/",
}


def _parse_jsonp(text: str) -> dict:
    text = re.sub(r"^/\*.*?\*/", "", text).strip()
    text = re.sub(r"^[a-zA-Z_]\w*\(", "", text)
    text = re.sub(r"\);?\s*$", "", text)
    return json.loads(text)


def _try_num(s):
    if s in (None, "", "--"):
        return None
    s = str(s).replace(",", "")
    try:
        return float(s) if "." in s else int(s)
    except (ValueError, TypeError):
        return s


class SinaStockInfoCollector:
    def __init__(self, test_mode: bool = TEST_MODE):
        self.test_mode = test_mode
        self.session = requests.Session()
        self.results = []
        self._processed_stocks = set()

    def get_stock_codes(self) -> List[str]:
        if self.test_mode:
            return TEST_STOCK_CODES
        return self._get_codes_from_json()

    def _get_codes_from_json(self) -> List[str]:
        try:
            with open(BOND_INFO_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            codes = list(set(b.get('stock_code', '') for b in data.get('bonds', []) if b.get('stock_code')))
            print(f"[JSON] Loaded {len(codes)} unique stock codes from bond info")
            return codes
        except FileNotFoundError:
            print(f"[ERROR] File not found: {BOND_INFO_JSON}")
            return []
        except Exception as e:
            print(f"[ERROR] Read file failed: {e}")
            return []

    def fetch_company_info(self, symbol: str) -> Optional[Dict]:
        url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyF10Service.getCompanyInformation"
        params = {"symbol": symbol, "callback": "hqccall_company"}

        try:
            time.sleep(random.uniform(*REQUEST_INTERVAL))
            response = self.session.get(url, params=params, headers=HEADERS, timeout=30)
            response.encoding = "utf-8"

            if response.status_code != 200:
                return None

            data = _parse_jsonp(response.text)
            result = data.get("result", {}).get("data", {})

            if not result:
                return None

            industry_list = result.get("Industry", [])
            industries = []
            for ind in industry_list:
                industries.append({
                    "级别": ind.get("tagname", ""),
                    "名称": ind.get("name", ""),
                })

            return {
                "公司名称": result.get("CorpName", ""),
                "公司性质": result.get("orgType", ""),
                "所属行业": industries,
                "董事长": result.get("chairman", ""),
                "总经理": result.get("manager", ""),
                "成立日期": result.get("establishDate", ""),
                "上市日期": result.get("ipoDate", ""),
                "发行价": f"{result.get('price', '')}元" if result.get("price") else "",
                "主营业务": result.get("mainBusiness", ""),
                "最大收入来源": result.get("maxIncome", ""),
                "最大利润来源": result.get("maxProfit", ""),
                "办公地址": result.get("workAddress", ""),
                "公司网址": result.get("companyAddress", ""),
                "公司亮点": result.get("highlight", ""),
            }

        except Exception as e:
            print(f"  [WARN] Fetch company info {symbol} failed: {e}")
            return None

    def fetch_related_data(self, symbol: str) -> Optional[Dict]:
        url = "https://quotes.sina.cn/app/api/openapi.php/ClientCnHqService.getRelatedHq"
        params = {"market": "cn", "symbol": symbol, "callback": "hqccall_related"}

        try:
            time.sleep(random.uniform(*REQUEST_INTERVAL))
            response = self.session.get(url, params=params, headers=HEADERS, timeout=30)
            response.encoding = "utf-8"

            if response.status_code != 200:
                return None

            data = _parse_jsonp(response.text)
            result = data.get("result", {}).get("data", {})

            if not result:
                return None

            gn_list = result.get("belong_gn", [])
            concepts = []
            for gn in gn_list:
                concepts.append({
                    "概念名称": gn.get("name", ""),
                    "相关性": gn.get("relevancy_cn", ""),
                    "相关原因": gn.get("reason", ""),
                })

            return {
                "概念": concepts,
            }

        except Exception as e:
            print(f"  [WARN] Fetch related data {symbol} failed: {e}")
            return None

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        if stock_code.startswith(('60', '68')):
            symbol = f"sh{stock_code}"
        else:
            symbol = f"sz{stock_code}"

        company_info = self.fetch_company_info(symbol)
        related_data = self.fetch_related_data(symbol)

        if not company_info and not related_data:
            return None

        info = {
            "stock_code": stock_code,
        }

        if company_info:
            info.update({
                "公司名称": company_info.get("公司名称", ""),
                "公司性质": company_info.get("公司性质", ""),
                "所属行业": company_info.get("所属行业", []),
                "主营业务": company_info.get("主营业务", ""),
                "最大收入来源": company_info.get("最大收入来源", ""),
                "最大利润来源": company_info.get("最大利润来源", ""),
                "办公地址": company_info.get("办公地址", ""),
                "公司网址": company_info.get("公司网址", ""),
                "公司亮点": company_info.get("公司亮点", ""),
            })

        if related_data:
            info["概念"] = related_data.get("概念", [])

        return info

    def save_to_json(self, stocks_info: List[Dict]) -> str:
        if not stocks_info:
            return None

        output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
        os.makedirs(output_dir, exist_ok=True)

        filename = f"sina_stock_info_{datetime.date.today().strftime('%Y%m%d')}.json"
        filepath = os.path.join(output_dir, filename)

        data = {
            "update_date": datetime.date.today().strftime("%Y-%m-%d"),
            "count": len(stocks_info),
            "stocks": stocks_info
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[JSON] Saved: {filepath}")
        return filepath

    def run(self):
        stock_codes = self.get_stock_codes()

        print("=" * 60)
        print("[STOCK] Stock Info Collector (Cloud Function)")
        print(f"[TIME] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print(f"[INFO] Total {len(stock_codes)} stocks to fetch\n")

        for i, stock_code in enumerate(stock_codes, 1):
            print(f"  [{i}/{len(stock_codes)}] Fetch {stock_code}...", end=" ")
            info = self.get_stock_info(stock_code)
            if info:
                self.results.append(info)
                print("OK")
            else:
                print("FAIL")

            self._processed_stocks.add(stock_code)

        print(f"\n[RESULT] Fetched {len(self.results)} stocks info")

        if self.results:
            self.save_to_json(self.results)

        print("=" * 60)
        status = "SUCCESS" if self.results else "WARNING: No data"
        print(f"{status}! Got {len(self.results)} records")
        print("=" * 60)

        return len(self.results)


def main(event, context):
    collector = SinaStockInfoCollector(test_mode=False)
    count = collector.run()
    return {
        'code': 0 if count > 0 else -1,
        'data': {
            'success': count > 0,
            'count': count,
            'message': f'Fetched {count} stocks info'
        }
    }
import json
import traceback
import sys
import os
import urllib.request


def safe_to_dict(df, n=2):
    """Convert DataFrame to JSON-safe dict records."""
    if df is None or len(df) == 0:
        return None
    try:
        return json.loads(df.head(n).to_json(orient="records", force_ascii=False))
    except Exception:
        try:
            return json.loads(df.head(n).to_json(orient="records"))
        except Exception:
            return None


def main(event, context):
    result = {"steps": []}

    # Add /opt/python to sys.path
    opt_python = "/opt/python"
    if opt_python in sys.path:
        sys.path.remove(opt_python)
    sys.path.insert(0, opt_python)

    # Step 1: Import akshare
    try:
        result["steps"].append("importing akshare...")
        import akshare as ak
        result["steps"].append(f"akshare v{ak.__version__} imported successfully")
    except Exception as e:
        result["steps"].append(f"import failed: {e}")
        result["steps"].append(traceback.format_exc())
        return {"code": 1, "error": str(e), "detail": result}

    # Step 2: Test index_realtime_sw with corrected symbol "一级行业"
    try:
        result["steps"].append("calling ak.index_realtime_sw(symbol='一级行业')...")
        df = ak.index_realtime_sw(symbol="一级行业")
        result["steps"].append(f"success, shape={df.shape}")
        result["sw_rows"] = len(df)
        if len(df) > 0:
            result["sw_columns"] = list(df.columns)
            result["sw_sample"] = safe_to_dict(df, 3)
        else:
            result["sw_note"] = "返回空数据，可能非交易时间"
    except Exception as e:
        result["steps"].append(f"failed: {type(e).__name__}: {str(e)[:200]}")

    # Step 3: Test Sina connectivity
    try:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=3&sort=symbol&asc=1&node=hskzz_z&symbol=&_s_r_a=page"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://vip.stock.finance.sina.com.cn/mkt/"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("gbk")
            result["sina_ok"] = f"got {len(data)} chars"
            result["sina_preview"] = data[:200]
    except Exception as e:
        result["sina_fail"] = str(e)[:100]

    return {"code": 0, "message": "test completed", "detail": result}

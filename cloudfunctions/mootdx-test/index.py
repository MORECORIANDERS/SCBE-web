import json
import pathlib

pathlib.Path.home = classmethod(lambda cls: pathlib.Path('/tmp'))

from mootdx import quotes


def main(event, context):
    try:
        if isinstance(event, str):
            try:
                event = json.loads(event)
            except json.JSONDecodeError:
                pass

        http_method = event.get('httpMethod', event.get('method', 'GET'))

        if http_method == 'GET':
            return handle_verification(event)
        else:
            return handle_callback(event)
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)}, ensure_ascii=False)
        }


def handle_verification(event):
    query_string = event.get('queryString', event.get('queryStringParameters', ''))
    if isinstance(query_string, str):
        params = {}
        for pair in query_string.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                params[key] = value
    else:
        params = query_string or {}

    challenge = params.get('challenge')
    if challenge:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/plain'},
            'body': challenge
        }
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'status': 'ok'}, ensure_ascii=False)
    }


def handle_callback(event):
    body = event.get('body', '{}')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass

    if isinstance(body, str):
        body = {}

    if body.get('type') == 'url_verification':
        challenge = body.get('challenge', '')
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'challenge': challenge}, ensure_ascii=False)
        }

    header = body.get('header', {})
    event_type = header.get('event_type', '')
    event_data = body.get('event', {})

    if event_type == 'application.bot.menu_v6':
        return handle_bot_menu(event_data)
    else:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'ok',
                'event_type': event_type
            }, ensure_ascii=False)
        }


def handle_bot_menu(event_data):
    event_key = event_data.get('event_key', '')
    operator = event_data.get('operator', {})
    open_id = operator.get('open_id', 'unknown')

    result_msg = f"收到菜单点击事件! event_key={event_key}, open_id={open_id}"

    if event_key == 'test':
        result_msg += "\n\n正在获取113678行情数据..."

        client = None
        try:
            client = quotes.Quotes.factory(market='std')
            data = client.quotes(symbol=['113678'])

            if data is not None and not data.empty:
                record = data.iloc[0].to_dict()
                result_msg += f"\n股票代码: {record.get('code', 'N/A')}"
                result_msg += f"\n最新价: {record.get('price', record.get('close', 'N/A'))}"
                result_msg += f"\n涨跌: {record.get('change', 'N/A')}"
                result_msg += f"\n涨幅: {record.get('pct_change', record.get('change_pct', 'N/A'))}%"
                result_msg += f"\n成交量: {record.get('volume', 'N/A')}"
                result_msg += f"\n成交额: {record.get('amount', 'N/A')}"
            else:
                result_msg += "\n未获取到数据"
        except Exception as e:
            result_msg += f"\n获取数据失败: {str(e)}"
        finally:
            if client:
                client.client.close()
    else:
        result_msg += f"\n\n未处理的菜单: {event_key}"

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'status': 'ok',
            'message': result_msg
        }, ensure_ascii=False)
    }


if __name__ == '__main__':
    test_event = {
        'httpMethod': 'GET',
        'queryString': 'challenge=test_challenge'
    }
    print("GET测试:", main(test_event, {}))

    test_callback = {
        'httpMethod': 'POST',
        'body': json.dumps({
            'header': {
                'event_type': 'application.bot.menu_v6'
            },
            'event': {
                'event_key': 'test',
                'operator': {
                    'open_id': 'ou_xxx'
                }
            }
        })
    }
    print("\nPOST测试:", main(test_callback, {}))
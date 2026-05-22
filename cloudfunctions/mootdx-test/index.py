import json
import pathlib

pathlib.Path.home = classmethod(lambda cls: pathlib.Path('/tmp'))

from mootdx import quotes


def main_handler(event, context):
    client = None
    try:
        stock_code = '113678'
        if event and isinstance(event, dict):
            if event.get('queryStringParameters') and event['queryStringParameters'].get('code'):
                stock_code = event['queryStringParameters']['code']

        client = quotes.Quotes.factory(market='std')
        data = client.quotes(symbol=[stock_code])

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'code': stock_code,
                'data': data.to_dict('records') if data is not None and not data.empty else None
            }, ensure_ascii=False, default=str)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            }, ensure_ascii=False, default=str)
        }
    finally:
        if client:
            client.client.close()


if __name__ == '__main__':
    test_event = {'queryStringParameters': {'code': '000001'}}
    result = main_handler(test_event, {})
    print(result)
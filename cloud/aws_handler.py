"""API Gateway WebSocket Lambda adapter. No AWS calls on import."""
import json
import os
from decimal import Decimal
from cloud.service import Service, Conflict, Gone


def _dynamo(value):
    return json.loads(json.dumps(value), parse_float=Decimal)


def _native(value):
    # boto3 returns DynamoDB numbers as Decimal, including nested maze cells.
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_native(item) for item in value]
    if isinstance(value, dict):
        return {key: _native(item) for key, item in value.items()}
    return value


class DynamoStore:
    def __init__(self):
        import boto3
        db = boto3.resource('dynamodb')
        self.rooms = db.Table(os.environ['ROOMS_TABLE'])
        self.connections = db.Table(os.environ['CONNECTIONS_TABLE'])
        from botocore.exceptions import ClientError
        self.ClientError = ClientError

    def get_room(self, code):
        item = self.rooms.get_item(Key={'roomCode': code}, ConsistentRead=True).get('Item')
        return _native(item)

    def create_room(self, item):
        try:
            self.rooms.put_item(Item=_dynamo(item), ConditionExpression='attribute_not_exists(roomCode)')
        except self.ClientError as exc:
            if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise Conflict() from exc
            raise

    def save_room(self, item, previous_version):
        try:
            self.rooms.put_item(Item=_dynamo(item), ConditionExpression='#v = :prior',
                                ExpressionAttributeNames={'#v': 'version'},
                                ExpressionAttributeValues={':prior': previous_version})
        except self.ClientError as exc:
            if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise Conflict() from exc
            raise

    def bind_connection(self, connection, code, index, expires_at):
        self.connections.put_item(Item={'connectionId': connection, 'roomCode': code,
                                        'playerIndex': index, 'expiresAt': expires_at})

    def get_connection(self, connection):
        item = self.connections.get_item(Key={'connectionId': connection}, ConsistentRead=True).get('Item')
        if item and item['expiresAt'] > __import__('time').time():
            return item
        return None

    def remove_connection(self, connection):
        self.connections.delete_item(Key={'connectionId': connection})


def handler(event, context):
    import boto3
    from botocore.exceptions import ClientError
    route = event['requestContext']['routeKey']
    connection = event['requestContext']['connectionId']
    if route == '$connect':
        # Browsers send Origin. This is an abuse guard, not player authentication.
        allowed = set(os.environ.get('ALLOWED_ORIGINS', '').split(','))
        headers = event.get('headers') or {}
        origin = headers.get('origin') or headers.get('Origin', '')
        if origin not in allowed:
            return {'statusCode': 403}
        return {'statusCode': 200}

    endpoint = f"https://{event['requestContext']['domainName']}/{event['requestContext']['stage']}"
    api = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint)

    def send(target, message):
        try:
            api.post_to_connection(ConnectionId=target, Data=json.dumps(message).encode('utf-8'))
        except ClientError as exc:
            if exc.response['Error']['Code'] == 'GoneException':
                raise Gone() from exc
            raise

    service = Service(DynamoStore(), send)
    if route == '$disconnect':
        service.disconnect(connection)
        return {'statusCode': 200}
    try:
        data = json.loads(event.get('body') or '{}')
        if not isinstance(data, dict):
            raise ValueError('Invalid message.')
        action = data.get('action')
        if route not in ('$default', action):
            raise ValueError('Invalid route.')
        if action == 'create':
            service.create(connection, str(data.get('name', ''))[:80], data.get('gameType', 'maze'), data.get('mode', 'network'))
        elif action == 'join':
            service.join(connection, str(data.get('code', ''))[:12], str(data.get('name', ''))[:80])
        elif action == 'resume':
            service.resume(connection, str(data.get('code', ''))[:12], str(data.get('token', ''))[:128])
        elif action in ('start', 'command', 'replay', 'snapshot'):
            service.change(connection, action, data.get('command'), data.get('requestId'))
        elif action == 'ping':
            send(connection, {'type': 'pong'})
        else:
            raise ValueError('Unknown action.')
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        send(connection, {'type': 'error', 'error': str(exc), 'requestId': data.get('requestId') if isinstance(data, dict) else None})
    return {'statusCode': 200}

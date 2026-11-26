from unittest.mock import Mock

if __name__ == '__main__':
    transport = Mock(return_value=(200, {'ready': True}))
    status, body = transport('/health')
    transport.assert_called_once_with('/health')
    print(status, body['ready'])

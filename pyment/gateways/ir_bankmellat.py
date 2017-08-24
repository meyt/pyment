from datetime import datetime
from zeep import Client, exceptions as zeep_exceptions
from pyment import Gateway, Transaction
from pyment.exceptions import GatewayNetworkError, TransactionError
from pyment.rediraction import Redirection


class MellatGateway(Gateway):
    """
    BankMellat
    Home: https://www.behpardakht.com
    Documentation: https://www.behpardakht.com (Stupidly documentation is private!)
    """
    __gateway_name__ = 'mellat'
    __gateway_unit__ = 'IRR'
    __config_params__ = ['terminal_id', 'username', 'password', 'callback_url', 'proxies']
    _server_url = 'https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl'

    def request_transaction(self, transaction: Transaction) -> Transaction:
        client = Client(self._server_url)
        if 'proxies' in self.config:
            client.transport.session.proxies = self.config['proxies']

        try:
            params = {
                'terminalId': self.config['terminal_id'],
                'userName': self.config['username'],
                'userPassword': self.config['password'],
                'orderId': transaction.order_id,
                'amount': int(transaction.amount),
                'localDate': datetime.now().strftime('%Y%m%d'),
                'localTime': datetime.now().strftime('%H%M%S'),
                'additionalData': '',
                'callBackUrl': self.config['callback_url'],
                'payerId': 0,
            }
            result = client.service.bpPayRequest(**params)
            res = str(result).split(',')
            res_code = res[0]
            if int(res_code) == 0:
                transaction.id = res[1]
                transaction.redirection = Redirection(
                    url='https://bpm.shaparak.ir/pgwchannel/startpay.mellat',
                    body_params=dict(RefId=res[1]),
                    method='post'
                )
            else:
                raise TransactionError('Mellat: invalid information. %s' % res_code)

        except zeep_exceptions.Fault as e:
            raise TransactionError('Mellat: invalid information.')

        except zeep_exceptions.Error:
            raise GatewayNetworkError

        return transaction

    def validate_transaction(self, data: dict) -> Transaction:
        transaction = Transaction()
        transaction.id = data['RefId']
        transaction.meta = data
        if int(data['ResCode']) == 0:
            transaction.validate_status = True
        return transaction

    def verify_transaction(self, transaction: Transaction, data):
        try:
            params = {
                'terminalId': self.config['terminal_id'],
                'userName': self.config['username'],
                'userPassword': self.config['password'],
                'orderId': transaction.order_id,
                'saleOrderId': data['SaleOrderId'],
                'saleReferenceId': data['SaleReferenceId'],
            }
            client = Client(self._server_url)
            if 'proxies' in self.config:
                client.transport.session.proxies = self.config['proxies']

            result = client.service.bpVerifyRequest(**params)
            if int(result) != 0:
                client.service.bpReversalRequest(**params)
                raise TransactionError('Mellat: invalid transaction, code: %s ' % result)

            result = client.service.bpSettleRequest(**params)
            if int(result) != 0:
                client.service.bpReversalRequest(**params)
                raise TransactionError('Mellat: invalid transaction, code: %s ' % result)

        except zeep_exceptions.Error:
            raise GatewayNetworkError

        return transaction

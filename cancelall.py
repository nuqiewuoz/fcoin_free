from fcoin import Fcoin
from auth import api_key, api_secret
import os

fcoin = Fcoin(api_key, api_secret)
symbol_pairs = ['ethusdt', 'ftusdt', 'fteth']

cancelledbuys = {}
cancelledsells = {}

## order example
# {'amount': '0.010000000000000000',
#  'created_at': 1530599688471,
#  'executed_value': '0.000000000000000000',
#  'fill_fees': '0.000000000000000000',
#  'filled_amount': '0.000000000000000000',
#  'id': 'xKrbQiSknGT-RgfMCHyjLJ4cJxLa1VCtxdYGY47loos=',
#  'price': '480.000000000000000000',
#  'side': 'sell',
#  'source': 'api',
#  'state': 'submitted',
#  'symbol': 'ethusdt',
#  'type': 'limit'}


def cancel_all_orders(symbols):
    """取消所有在售的单子"""
    for symbol in symbols:
        orders_info = fcoin.list_orders(symbol=symbol, states="submitted")
        orders = orders_info['data']
        totalbuy = 0
        totalsell = 0
        for order in orders:
            if order['side'] == "buy":
                totalbuy += float(order['amount'])
            else:
                totalsell += float(order['amount'])
            fcoin.cancel_order(order['id'])
        cancelledbuys[symbol] = totalbuy
        cancelledsells[symbol] = totalsell
        print("取消{} 买单{} 卖单{}".format(symbol, totalbuy, totalsell))


def marketorders():
    all_symbols = fcoin.get_symbols()
    amount_decimals = {}
    for symbol in symbol_pairs:
        for info in all_symbols:
            if symbol == info['name']:
                amount_decimals[symbol] = int(info['amount_decimal'])
                break
    
    for symbol, value in cancelledsells:
        amount = round(value, amount_decimals[symbol])
        fcoin.sell(symbol, 0, amount, "market")
        print("市价卖出{} {}".format(symbol, amount))
    
    print("市价买入的标的和限价买入的标的不一致，请自行换算")
    # for symbol, value in cancelledbuys:
    #     amount = round(value, amount_decimals[symbol])
    #     fcoin.buy(symbol, 0, amount, "market")
    #     print("市价买入{} {}".format(symbol, amount))



if __name__ == '__main__':
    try:
        cancel_all_orders(symbol_pairs)
    except KeyboardInterrupt:
        os._exit(1)

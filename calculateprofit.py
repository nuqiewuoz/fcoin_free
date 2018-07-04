import re
import os
from fcoin import Fcoin
from auth import api_key, api_secret

fcoin = Fcoin(api_key, api_secret)
symbol_pairs = ['ethusdt', 'ftusdt', 'fteth']
filename1 = "arbitrage_strict1.log"
filename2 = "arbitragerobot.log"

onbuys = {}
onsells = {}


def lossonbook(symbols):
    """ 如果现在所有挂着的单子以市场价成交，会比以挂单价成交亏损的百分比"""
    totalloss = 0
    for symbol in symbols:
        orders_info = fcoin.list_orders(symbol=symbol, states="submitted")
        orders = orders_info['data']
        price = fcoin.get_market_price(symbol)
        totalbuy = 0
        totalsell = 0
        for order in orders:
            orderprice = float(order["price"])
            if order['side'] == "buy":
                loss = (price-orderprice)/orderprice
                totalbuy += float(order['amount'])
                print("buy:", loss)
            else:
                loss = (orderprice-price)/orderprice
                totalsell += float(order['amount'])
                print("sell:", loss)
            totalloss += loss
        onbuys[symbol] = totalbuy
        onsells[symbol] = totalsell
        print("{} 待买入{} 待卖出{}".format(symbol, totalbuy, totalsell))
    print("账面损失{:.2%}".format(totalloss))


def calculate(fn = filename1):
    profits1 = []
    profits2 = []
    bidnum = 0
    totalprofit = 0
    with open(fn) as f:
        lines = f.readlines()
        for line in lines:
            bidpattern = re.compile(r"^.*每单金额(.+)eth.*$")
            pattern1 = re.compile(r"^.*套利值为(.+)‰$")
            pattern2 = re.compile(r"^.*套利值比为(.+)‰$")
            m1 = pattern1.match(line)
            m2 = pattern2.match(line)
            bidm = bidpattern.match(line)
            if bidm:
                bidnum = float(bidm.group(1))
            if m1:
                profits1.append(float(m1.group(1)))
                totalprofit += bidnum * profits1[-1]
            if m2:
                profits2.append(float(m2.group(1)))
                totalprofit += bidnum * profits2[-1]
    total1 = sum(profits1)/1000
    total2 = sum(profits2)/1000
    totalprofit = totalprofit/1000
    print("总计获利{:.2%}".format(total1+total2))
    print("方式一交易次数{} 总获利{:.2%}".format(len(profits1), total1))
    print("方式二交易次数{} 总获利{:.2%}".format(len(profits2), total2))
    print("总计交易{}次 平均每次获利{:.2%}".format(len(profits1)+len(profits2),
                                        (total1+total2)/(len(profits1)+len(profits2))))
    print("预计总收益为{}eth".format(totalprofit))


if __name__ == '__main__':
    try:
        print("严格的套利方式：")
        calculate(filename1)
        # print("折中的套利方式：")
        # calculate(filename2)

        lossonbook(symbol_pairs)
    except KeyboardInterrupt:
        os._exit(1)

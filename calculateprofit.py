import re
import os
from fcoin import Fcoin
from auth import api_key, api_secret
import time
import pandas as pd
import balance


fcoin = Fcoin(api_key, api_secret)
symbol_pairs = ['ethusdt', 'zipusdt', 'zipeth']
filename1 = "arbitrage_strict.log"
filename2 = "arbitragerobot.log"


def lossonbook(symbols, status="submitted"):
    """ 如果现在所有挂着的单子以市场价成交，会比以挂单价成交亏损的百分比"""
    print("订单状态:{}".format(status))
    totalloss = 0
    buyorders = {}
    sellorders = {}
    onbuys = {}
    onsells = {}
    for symbol in symbols:
        orders_info = fcoin.list_orders(symbol=symbol, states=status)
        orders = orders_info['data']
        price = fcoin.get_market_price(symbol)
        totalbuy = 0
        totalsell = 0
        buyorder = []
        sellorder = []
        for order in orders:
            orderprice = float(order["price"])
            if order['side'] == "buy":
                loss = (price-orderprice)/orderprice
                buyorder.append(order)
                totalbuy += float(order['amount']) - float(order['filled_amount'])
                # print("buy:", loss)
            else:
                loss = (orderprice-price)/orderprice
                sellorder.append(order)
                totalsell += float(order['amount']) - float(order['filled_amount'])
                # print("sell:", loss)
            totalloss += loss
        onbuys[symbol] = totalbuy
        onsells[symbol] = totalsell
        buyorders[symbol] = buyorder
        sellorders[symbol] = sellorder
    for symbol in symbols:
        num = len(buyorders[symbol]) + len(sellorders[symbol])
        print("{} 未成交{}笔 待买入{} 待卖出{}".format(symbol, num, onbuys[symbol], onsells[symbol]))
    print("账面损失{:.2%}".format(totalloss))


def calculate(fn = filename1):
    profits1 = []
    profits2 = []
    bidnum = 0
    totalprofit = 0
    totalcost = 0
    totalslip = 0
    info = []
    with open(fn) as f:
        lines = f.readlines()
        for line in lines:
            bidpattern = re.compile(r"^.*每单金额(.+)eth.*$")
            slippattern = re.compile(r"^.*总滑点为(.+)‰ 依次为.*$")
            pattern1 = re.compile(r"^.*套利值为(.+)‰$")
            pattern2 = re.compile(r"^.*套利值比为(.+)‰$")
            m1 = pattern1.match(line)
            m2 = pattern2.match(line)
            bidm = bidpattern.match(line)
            slipm = slippattern.match(line)
            if bidm:
                bidnum = float(bidm.group(1))
            if m1:
                profits1.append(float(m1.group(1)))
                totalprofit += bidnum * profits1[-1]
                info.append(sum(profits1)+sum(profits2)-totalslip-sum(info))
                # if float(m1.group(1)) > 1.5:
                #     print("大于1.5的套利:", m1.group(0))
            if m2:
                profits2.append(float(m2.group(1)))
                totalprofit += bidnum * profits2[-1]
                info.append(sum(profits1)+sum(profits2)-totalslip-sum(info))
                # if float(m2.group(1)) > 1.5:
                #     print("大于1.5的套利:", m2.group(0))
            if slipm:
                totalcost += bidnum * float(slipm.group(1))
                totalslip += float(slipm.group(1))
                # if float(slipm.group(1)) > 2:
                #     print("大于5‰的滑点:", slipm.group(0))
                # print(slipm.group(1))

    total1 = sum(profits1)/1000
    total2 = sum(profits2)/1000
    totalprofit = totalprofit/1000
    totalcost = totalcost/1000
    totalslip = totalslip/1000
    totalnum = len(profits1)+len(profits2)
    infodf = pd.DataFrame(info)
    print("方式一交易次数{} 总获利{:.2%}".format(len(profits1), total1))
    print("方式二交易次数{} 总获利{:.2%}".format(len(profits2), total2))
    print("总计套利{:.2%} 平均套利{:.3%}".format(total1+total2, (total1+total2)/totalnum))
    print("总计滑点{:.2%} 平均滑点{:.3%}".format(totalslip, totalslip/totalnum))
    print("总计交易{}次 平均每次获利{:.3%}".format(totalnum, float(infodf.mean()/1000)))
    print("预计总收益为{}eth".format(totalprofit-totalcost))
    # print(infodf.describe())


def simple_calculate(fn=filename1):
    profits1 = []
    profits2 = []
    bidnums1 = []
    bidnums2 = []
    bidnum = 0
    with open(fn) as f:
        lines = f.readlines()
        for line in lines:
            pattern1 = re.compile(r"^.*套利值为(.+)‰$")
            pattern2 = re.compile(r"^.*套利值比为(.+)‰$")
            bidpattern = re.compile(r"^.*每单金额(.+)eth.*$")
            m1 = pattern1.match(line)
            m2 = pattern2.match(line)
            bidm = bidpattern.match(line)
            if bidm:
                bidnum = float(bidm.group(1))
            if m1:
                profits1.append(float(m1.group(1)))
                bidnums1.append(bidnum)
            if m2:
                profits2.append(float(m2.group(1)))
                bidnums2.append(bidnum)

    total1 = sum(profits1)/1000
    total2 = sum(profits2)/1000
    totalnum = len(profits1)+len(profits2)
    print("方式一交易次数{} 总获利{:.2%}".format(len(profits1), total1))
    print("方式二交易次数{} 总获利{:.2%}".format(len(profits2), total2))
    print("总计交易{}次 总计套利{:.2%} 平均套利{:.3%}".format(totalnum,
        total1+total2, (total1+total2)/totalnum))
    totalprofit = 0
    for i in range(len(profits1)):
        totalprofit += profits1[i]*bidnums1[i]
    for i in range(len(profits2)):
        totalprofit += profits2[i]*bidnums2[i]
    totalprofit /= 1000
    print("总计交易{}eth 预计获利{}eth".format(
        sum(bidnums1)+sum(bidnums2), float(totalprofit)))



def slippage(orderid, price):
    # 单位是千分之一
    result = fcoin.order_result(orderid)
    while result == None or len(result['data'])==0:
        time.sleep(0.1)
        result = fcoin.order_result(orderid)
    slip = 0
    amount = 0
    total = 0
    for order in result['data']:
        amount += float(order["filled_amount"])
        total += float(order["filled_amount"])*float(order["price"])
    realprice = total/amount
    if result['data'][0]['type'] == "buy_market":
        slip = (realprice-price)/price
    else:
        slip = (price-realprice)/price
    return slip*1000



def report():
    # print("严格的套利方式：")
    simple_calculate(filename1)
    # print("折中的套利方式：")
    # calculate(filename2)
    lossonbook(symbol_pairs)
    lossonbook(symbol_pairs, "partial_filled")

    balance.get_balance_action(['eth', 'usdt', 'zip'])


if __name__ == '__main__':
    try:
        report()
    except KeyboardInterrupt:
        os._exit(1)

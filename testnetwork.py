import threading
import requests
import logging
import os
import multiprocessing
import time
from fcoin import Fcoin
from auth import api_key, api_secret

def setlog():
    logging.basicConfig(filename="testnetwork.log", level=logging.DEBUG, format='%(asctime)s %(processName)s %(threadName)s %(levelname)s %(message)s')


def lprint(msg, level=logging.INFO):
    print(msg)
    logging.log(level, msg)


def test_network(repeat=20, api=None):
    base_url = 'https://api.fcoin.com/v2'
    api_url = '/public/server-time'
    if api:
        api_url = api

    url = base_url+api_url
    diffs = []

    with requests.Session() as s:
        # call url once to complete 3 hand shakes.
        s.get(url)
        beginat = time.time()
        lprint('begin network connect test:{}'.format(url), logging.DEBUG)
        for i in range(repeat):
            old = int(time.time()*1000)
            r = s.get(url)
            now = int(time.time()*1000)
            server = int(r.json()['data'])
            diff = (now + old)/2 - server
            lprint("before:{} after:{} server:{} delta:{}ms difference:{}".format(old, now, server, now-old, diff), logging.DEBUG)
            diffs.append(diff)

        endat = time.time()
        lprint('total time:{:.5}s avg time:{:.4}ms'.format(endat-beginat, (endat-beginat)/repeat*1000))
    # 返回本地和服务器的时间差, 单位毫秒
    return sum(diffs)/len(diffs)


def test_create_order(repeat=10):
    # 估算时间差
    system_delta = test_network()
    lprint('预计系统时间差:{:.4}ms'.format(system_delta))
        
    fcoin = Fcoin(api_key, api_secret)
    beginat = time.time()
    symbol = "fteth"
    # price = fcoin.get_market_price(symbol)
    price = 0.00001
    logging.info('begin create order test: buy {}'.format(symbol))
    orders_info = []
    for i in range(repeat):
        old = int(time.time()*1000)
        buy_result = fcoin.buy(symbol, price, 3)
        now = int(time.time()*1000)
        lprint("before:{} after:{} delta:{}ms".format(old, now, now-old), logging.DEBUG)
        logging.debug("buy order result:{}".format(buy_result))
        orders_info.append((buy_result['data'], old))
    endat = time.time()
    lprint('total time:{:.5}s avg time:{:.4}ms'.format(
        endat-beginat, (endat-beginat)/repeat*1000))
    # 计算从下单开始，到系统记录下单之间的时间
    delta_times = []
    for order_id, call_time in orders_info:
        order = fcoin.get_order(order_id)
        delta = int(order['data']['created_at']) - call_time
        # cancel the test order
        fcoin.cancel_order(order_id)
        delta_times.append(delta)
    avg = sum(delta_times)/len(delta_times)
    lprint('average time delta: {:.5}ms differece:{:.4}ms'.format(
        avg, system_delta))
    lprint('平均下单时间为:{:.4}ms'.format(avg+system_delta))


if __name__ == '__main__':
    try:
        setlog()
        test_create_order()
    except KeyboardInterrupt:
        os._exit(1)

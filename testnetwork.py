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

    with requests.Session() as s:
        # call url once to complete 3 hand shakes.
        s.get(url)
        beginat = time.time()
        logging.info('begin url connect test:{}'.format(url))
        for i in range(repeat):
            old = time.time()*1000
            r = s.get(url)
            now = time.time()*1000
            lprint("before:{} after:{} delta:{}ms".format(old, now, int(now-old)), logging.DEBUG)
            lprint("local:{} server:{} delta:{}ms".format(now, r.json()[
                   'data'], int(now)-int(r.json()['data'])), logging.DEBUG)
        endat = time.time()
        lprint('total time:{:.5}s avg time:{:.4}ms'.format(
            endat-beginat, (endat-beginat)/repeat*1000))


def test_create_order(repeat = 5):
    fcoin = Fcoin(api_key, api_secret)
    beginat = time.time()
    logging.info('begin buy test:')
    for i in range(repeat):
        old = time.time()*1000
        buy_result = fcoin.buy("ethusdt", 520.00, 0.001)
        now = time.time()*1000
        lprint("before:{} after:{} delta:{}ms".format(
            old, now, int(now-old)), logging.DEBUG)
        lprint("buy order result:{}".format(buy_result['data']))
    endat = time.time()
    lprint('total time:{:.5}s avg time:{:.4}ms'.format(
        endat-beginat, (endat-beginat)/repeat*1000))


if __name__ == '__main__':
    try:
        setlog()
        test_network()
    except KeyboardInterrupt:
        os._exit(1)

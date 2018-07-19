import threading
import requests
import logging
import os
import multiprocessing
import time

def setlog():
    logging.basicConfig(filename="testnetwork.log", level=logging.DEBUG, format='%(asctime)s %(processName)s %(threadName)s %(levelname)s %(message)s')


def test_network(ip=None, repeat=10):
    if ip == None:
        ip = 'api.fcoin.com'
    
    base_url = 'https://'+ip+'/v2'
    api_url = '/public/server-time'
    url = base_url+api_url

    with requests.Session() as s:
        # call url once to complete 3 hand shakes.
        s.get(url)
        beginat = time.time()
        logging.info('begin url connect test:{}'.format(url))
        for i in range(repeat):
            r = s.get(url)
            logging.info(r.json())
        endat = time.time()
        logging.info('total time:{} avg time:{}'.format(
            endat-beginat, (endat-beginat)/repeat))
        print('connect:{} total time:{} avg time:{}'.format(
            ip, endat-beginat, (endat-beginat)/repeat))

if __name__ == '__main__':
    try:
        setlog()
        test_network()
    except KeyboardInterrupt:
        os._exit(1)

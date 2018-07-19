# -*- coding: utf-8 -*-
# @Author: zz
# @Date:   2018-06-24 18:15:55
# @Last Modified by:   zhiz
# @Last Modified time: 2018-06-25 13:24:31

from fcoin import Fcoin
from auth import api_key, api_secret
from config import symbol_type
import logging
import time

# 初始化
fcoin = Fcoin(api_key, api_secret)

# 查询账户余额
def get_balance_action(symbols):
    balance_info = fcoin.get_balance()
    # logging.debug(balance_info)
    balances = []
    for info in balance_info['data']:
        for symbol in symbols:
            if info['currency'] == symbol:
                balance = info
                print(balance['currency'], '账户余额', balance['balance'], '可用', balance['available'], '冻结', balance['frozen'])
                balances.append(balance)
                logging.info("{} 账户余额 {} 可用 {} 冻结 {}".format(balance['currency'], balance['balance'], balance['available'], balance['frozen']))
    return balances


def total_balance_as_token(symbol, balances):
    symbols_info = fcoin.get_symbols()
    # logging.debug(symbols_info)
    total = 0
    for balance in balances:
        balance_symbol = balance['currency']
        this_balance = float(balance["balance"])
        if balance_symbol == symbol:
            total += this_balance
        else:
            for info in symbols_info:
                if info['quote_currency'] == symbol and info['base_currency'] == balance_symbol:
                    price = fcoin.get_market_price(info['name'])
                    total += this_balance * price
                    break
                if info['quote_currency'] == balance_symbol and info['base_currency'] == symbol:
                    price = fcoin.get_market_price(info['name'])
                    total += this_balance / price
                    break
            else:
                print("not found symbols for {} and {}".format(
                    balance_symbol, symbol))
                return
    print("账户总价值", total, symbol)
    logging.info("账户总价值{} {}".format(total, symbol))


def total_balance():
    # all tokens should be change to eth or usdt directly
    balance_info = fcoin.get_balance()
    balances = balance_info['data']
    symbols_info = fcoin.get_symbols()
    # logging.debug(symbols_info)
    totalusdt = 0
    totaleth = 0
    usdt = "usdt"
    eth = "eth"
    totalft = 0
    ft = "ft"
    for balance in balances:
        balance_symbol = balance['currency']
        this_balance = float(balance["balance"])
        if this_balance == 0:
            continue
        if balance_symbol == usdt:
            totalusdt += this_balance
        elif balance_symbol == eth:
            totaleth += this_balance
        else:
            for info in symbols_info:
                if info['quote_currency'] == usdt and info['base_currency'] == balance_symbol:
                    price = fcoin.get_market_price(info['name'])
                    totalusdt += this_balance * price
                    break
                if info['quote_currency'] == balance_symbol and info['base_currency'] == usdt:
                    price = fcoin.get_market_price(info['name'])
                    totalusdt += this_balance / price
                    break
                if info['quote_currency'] == eth and info['base_currency'] == balance_symbol:
                    price = fcoin.get_market_price(info['name'])
                    totaleth += this_balance * price
                    break
                if info['quote_currency'] == balance_symbol and info['base_currency'] == eth:
                    price = fcoin.get_market_price(info['name'])
                    totaleth += this_balance / price
                    break
                if info['quote_currency'] == ft and info['base_currency'] == balance_symbol:
                    price = fcoin.get_market_price(info['name'])
                    totalft += this_balance * price
                    break
                if info['quote_currency'] == balance_symbol and info['base_currency'] == ft:
                    price = fcoin.get_market_price(info['name'])
                    totalft += this_balance / price
                    break
            else:
                print("invalid symbol {}".format(balance_symbol))
                return
    ethprice = fcoin.get_market_price('ethusdt')
    ftprice = fcoin.get_market_price('ftusdt')
    total = totalusdt + totaleth * ethprice + totalft * ftprice
    print("账户总价值", total, "usdt")
    print("账户总价值", total/ethprice, "eth")
    print("账户总价值", total/ftprice, "ft")
    logging.info("账户总价值{} usdt".format(total))
    logging.info("账户总价值{} eth".format(total/ethprice))
    logging.info("账户总价值{} ft".format(total/ftprice))


def balance(all=False):
    # 账户余额
    if all:
        total_balance()
    else:
        balances = get_balance_action(symbol_type)
        total_balance_as_token("usdt", balances)
        total_balance_as_token("eth", balances)
        total_balance_as_token("ft", balances)


# 守护进程
if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    print(time.ctime())
    balance(False)

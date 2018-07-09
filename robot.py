# -*- coding: utf-8 -*-
# @Author: zz
# @Date:   2018-06-24 18:15:55
# @Last Modified by:   zhiz
# @Last Modified time: 2018-06-25 17:23:56

from fcoin import Fcoin
from fcoin_websocket.fcoin_client import fcoin_client
from auth import api_key, api_secret
from config import symbols, second, amount, price_difference, is_direct_buy
import os, time
import math
import balance
import logging

symbol = symbols[0] + symbols[1]
logfile = "robot.log"

is_mutable_amount = False
miniamount = 0.01
maxamount = 0.02


def lprint(msg, level=logging.INFO):
	print(msg)
	logging.log(level, msg)


class Robot(object):
	"""docstring for Robot"""
	def __init__(self):
		self.fcoin = Fcoin(api_key, api_secret)
		# self.ticker = []

	# 截取指定小数位数
	def trunc(self, f, n):
		# return round(f, n)
		return math.floor(f*10**n)/10**n

	def ticker_handler(self, message):
		if 'ticker' in message:
			self.ticker = message['ticker']
		# print('ticker', self.ticker)

	def symbols_action(self):
		all_symbols = self.fcoin.get_symbols()
		for info in all_symbols:
			if symbol == info['name']:
				self.price_decimal = int(info['price_decimal'])
				self.amount_decimal = int(info['amount_decimal'])
				# print('price_decimal:', self.price_decimal, 'amount_decimal:', self.amount_decimal)
				return

	# 查询账户余额
	def get_balance_action(self, symbols, specfic_symbol = None):
		balance_info = self.fcoin.get_balance()
		specfic_balance = 0
		for info in balance_info['data']:
			for symbol in symbols:
				if info['currency'] == symbol:
					balance = info
					print(balance['currency'], '账户余额', balance['balance'], '可用', balance['available'], '冻结', balance['frozen'])
					if info['currency'] == specfic_symbol:
						specfic_balance = float(info['available'])
		return specfic_balance

	# 买操作
	def buy_action(self, this_symbol, this_price, this_amount, should_repeat = 0):
		ticker = self.ticker
		# print('准备买入', this_price, ticker)
		buy_result = self.fcoin.buy(this_symbol, self.trunc(this_price, self.price_decimal), this_amount)
		# print('buy_result is', buy_result)
		buy_order_id = buy_result['data']
		if buy_order_id:
			lprint('买单{} 价格成功委托 订单ID{}'.format(this_price, buy_order_id))
		return buy_order_id

	# 卖操作
	def sell_action(self, this_symbol, this_price, this_amount):
		ticker = self.ticker
		# print('准备卖出', this_price, ticker)
		if is_direct_buy == 1:
			sell_result = self.fcoin.sell(this_symbol, self.trunc(this_price * (1 - 0.0002), self.price_decimal), this_amount)
		else:
			sell_result = self.fcoin.sell(this_symbol, this_price, this_amount)
		# print('sell_result is: ', sell_result)
		sell_order_id = sell_result['data']
		if sell_order_id:
			lprint('卖单{} 价格成功委托 订单ID{}'.format(this_price, sell_order_id))
		return sell_order_id


	def strategy(self, symbol, order_price, amount):
		# print('使用单边震荡策略')
		gap = price_difference/4
		buy_price = self.trunc(order_price-gap, self.price_decimal)
		sell_price = self.trunc(order_price+gap, self.price_decimal)
		buy_id = self.buy_action(symbol, buy_price, amount)
		sell_id = self.sell_action(symbol, sell_price, amount)


	def trade(self):
		time.sleep(second)
		# print(bytes.decode(base64.b64decode(b'6LSt5Lmw6K+36K6k5YeG5b6u5L+h5Y+3YXJjaGVyemhz77yM5LiN6KaB55u45L+h5YW25LuW55qE5p2l5rqQ')))
		ticker = self.ticker
		# if len(ticker) == 0:
			# return
		# newest_price = ticker[0]
		high_bids = ticker[2]
		high_bids_amount = ticker[3]
		low_ask = ticker[4]
		low_ask_amount = ticker[5]
		order_price = self.trunc((low_ask + high_bids) / 2, self.price_decimal)
		real_price_difference = float(low_ask - high_bids)
		print('最低卖价:', low_ask, '最高买价', high_bids, '欲下订单价: ', order_price, 
				'当前差价:', '{:.9f}'.format(real_price_difference), '设定差价:', '{:.9f}'.format(price_difference))
		if real_price_difference > price_difference:
			# print('现在价格:', newest_price, '挂单价格', order_price)
			trade_amount = min(high_bids_amount, low_ask_amount) / 2
			if is_mutable_amount:
				if trade_amount > maxamount:
					trade_amount = maxamount
				if trade_amount < miniamount:
					trade_amount = miniamount
				trade_amount = self.trunc(trade_amount, self.amount_decimal)
				self.strategy(symbol, order_price, trade_amount)
			else:
				self.strategy(symbol, order_price, amount)
		else:
			print('差价太小，放弃本次成交')

	def run(self):
		self.client = fcoin_client(self.on_close)
		# self.client = fcoin_client()
		self.client.start()
		self.client.subscribe_tickers([symbol], self.ticker_handler)
		self.symbols_action()
		# self.get_balance_action(symbols)
		balance.balance()
		while True:
			self.trade()

	def on_close(self):
		print("websocket closed, try to restart...")
		time.sleep(second)
		self.client = fcoin_client(self.on_close)
		self.client.start()
		self.client.subscribe_tickers([symbol], self.ticker_handler)


if __name__ == '__main__':
	try:
		logging.basicConfig(filename=logfile, level=logging.INFO,
                      format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
		logging.warning("开始刷单")
		robot = Robot()
		robot.run()
	except KeyboardInterrupt:
		os._exit(1)





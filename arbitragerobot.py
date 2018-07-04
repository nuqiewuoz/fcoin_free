from fcoin import Fcoin
from fcoin_websocket.fcoin_client import fcoin_client
from auth import api_key, api_secret
from config import second
import os
import time
import math
import logging
import pandas as pd
import balance

# symbol = symbols[0] + symbols[1]
symbol_pairs = ['ethusdt', 'ftusdt', 'fteth']
symbols = ['eth', 'usdt', 'ft']
ethamount = 0.01
difference = 1.0018


def lprint(msg, level=logging.INFO):
	print(msg)
	logging.log(level, msg)

class ArbitrageRobot(object):
	"""docstring for Robot"""

	def __init__(self):
		self.fcoin = Fcoin(api_key, api_secret)
		self.price_decimals = {}
		self.amount_decimals = {}
		self.tickers = {}

	# 截取指定小数位数
	def trunc(self, f, n):
		# return round(f, n)
		return math.floor(f*10**n)/10**n

	def ticker_handler(self, message):
		# print(message)
		if 'ticker' in message:
			symbol = message['type'].split('.')[1]
			self.tickers[symbol] = message['ticker']
			logging.debug("ticker: {}".format(message['ticker']))
		else :
			logging.debug("ticker message: {}".format(message))

	def symbols_action(self):
		all_symbols = self.fcoin.get_symbols()
		for symbol in symbol_pairs:
			for info in all_symbols:
				if symbol == info['name']:
					self.price_decimals[symbol] = int(info['price_decimal'])
					self.amount_decimals[symbol] = int(info['amount_decimal'])
					break
		logging.info("price_decimals: {}".format(self.price_decimals))


	# 买操作
	def buy_action(self, this_symbol, this_price, this_amount, should_repeat=0):
		this_price = self.trunc(this_price, self.price_decimals[this_symbol])
		this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		# ticker = self.tickers[this_symbol]
		# print('准备买入', this_price, ticker)
		buy_result = self.fcoin.buy(this_symbol, this_price, this_amount)
		# print('buy_result is', buy_result)
		buy_order_id = buy_result['data']
		if buy_order_id:
			lprint("买单 {} 价格成功委托, 订单ID {}".format(this_price, buy_order_id))
		return buy_order_id

	# 卖操作
	def sell_action(self, this_symbol, this_price, this_amount):
		this_price = self.trunc(this_price, self.price_decimals[this_symbol])
		this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		# ticker = self.tickers[this_symbol]
		# print('准备卖出', this_price, ticker)
		sell_result = self.fcoin.sell(this_symbol, this_price, this_amount)
		# print('sell_result is: ', sell_result)
		sell_order_id = sell_result['data']
		if sell_order_id:
			lprint("卖单 {} 价格成功委托, 订单ID {}".format(this_price, sell_order_id))
		return sell_order_id

	def strategy(self, type, pricedf, amount):
		print('使用套利策略')
		if type == 1:
			usdtamount = amount*pricedf["ethusdt"]
			ftamount = usdtamount/pricedf["ftusdt"]
			self.sell_action("fteth", pricedf["fteth"], ftamount)
			self.buy_action("ftusdt", pricedf["ftusdt"], ftamount)
			self.sell_action("ethusdt", pricedf["ethusdt"], amount)
		
		elif type == 2:
			ftamount = amount/pricedf["fteth"]
			self.buy_action("ethusdt", pricedf["ethusdt"], amount)
			self.sell_action("ftusdt", pricedf["ftusdt"], ftamount)
			self.buy_action("fteth", pricedf["fteth"], ftamount)
		

	def trade(self):
		"""套利策略，寻找一个三元pair，看是不是满足套利规则。
    ETH/USDT, FT/ETH, FT/USDT
    ethusdt买一价 * fteth买一价 / ftusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程：usdt买ft，卖ft换回eth，卖eth换回usdt
    ftusdt买一价 / fteth卖一价 / ethusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程为：usdt买eth，eht买ft，卖ft换回usdt
    买一下标为2， 卖一下标为4"""
		time.sleep(second)
		
		if len(self.tickers) == len(symbol_pairs):
			info_df = pd.DataFrame(self.tickers).T
			# 买一卖一的均价
			info_df["price"] = (info_df[2]+info_df[4])/2
			taoli1 = info_df.price["ethusdt"] * \
				info_df.price["fteth"] / info_df.price["ftusdt"]
			taoli2 = info_df.price["ftusdt"] / \
				info_df.price["fteth"] / info_df.price["ethusdt"]
			# print(taoli1, taoli2)
			# 从eth开始交易
			if taoli1 > difference:
				self.strategy(1, info_df.price, ethamount)
				lprint("满足套利条件1 套利值为{:.4}‰".format(taoli1*1000-1000))
				lprint("ethusdt卖价：{} ftusdt买价：{} fteth卖价：{}".format(
					info_df.price["ethusdt"], info_df.price["ftusdt"], info_df.price["fteth"]))
			elif taoli2 > difference:
				self.strategy(2, info_df.price, ethamount)
				lprint("满足套利条件2 套利值比为{:.4}‰".format(taoli2*1000-1000))
				lprint("fteth买价：{} ftusdt卖价：{} ethusdt买价：{}".format(
					info_df.price["fteth"], info_df.price["ftusdt"], info_df.price["ethusdt"]))
			else:
				lprint('差价太小，本次无法套利 方式一{} 方式二{}'.format(taoli1, taoli2), logging.DEBUG)

	def run(self):
		self.client = fcoin_client()
		self.client.start()
		self.client.subscribe_tickers(symbol_pairs, self.ticker_handler)
		self.symbols_action()
		# self.get_balance_action(symbols)
		balance.balance()
		while True:
			self.trade()


if __name__ == '__main__':
	try:
		logging.basicConfig(filename='arbitragerobot1.log', level=logging.INFO,
                      format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
		logging.warning("套利成功！")
		lprint("每单金额{}eth，最小利差{:.2}‰".format(ethamount, (difference-1)*1000))
		robot = ArbitrageRobot()
		robot.run()
	except KeyboardInterrupt:
		os._exit(1)

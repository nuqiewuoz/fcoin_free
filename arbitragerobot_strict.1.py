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
import threading
import queue

symbol_pairs = ['ethusdt', 'fiusdt', 'fieth']
symbols = ['eth', 'usdt', 'fi']
_ethamount = 0.01
_halfeth = _ethamount/2
# 为了减少计算量，避免单位换算
_fiamount = 50	#0.01*5000
_halffi = _fiamount/2

difference = 1.001
is_use_amount = True

heartbeat_interval = 60
# is_mutable_amount = False
# miniamount = 0.003
# maxamount = 0.01
logfile = "arbitrage_strict1.log"

ticker_queue = queue.Queue()


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
		pd.set_option('precision', 10)
		self.time_last_call = time.time()


	# 截取指定小数位数
	def trunc(self, f, n):
		return round(f, n)
		# return math.floor(f*10**n)/10**n


	def ticker_handler(self, message):
		# print(message)
		if 'ticker' in message:
			symbol = message['type'].split('.')[1]
			self.tickers[symbol] = message['ticker']
			ticker_queue.put(self.tickers, block=False)
			logging.debug("get ticker")
			# logging.info("ticker message: {}".format(message))
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
		logging.info("amount_decimals: {}".format(self.amount_decimals))


	# 买操作
	def buy_action(self, this_symbol, this_price, this_amount, type="limit"):
		# this_price = self.trunc(this_price, self.price_decimals[this_symbol])
		this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		buy_result = self.fcoin.buy(this_symbol, this_price, this_amount, type)
		# print('buy_result is', buy_result)
		buy_order_id = buy_result['data']
		if buy_order_id:
			lprint("买单 {} 价格成功委托, 订单ID {}".format(this_price, buy_order_id))
		return buy_order_id


	# 卖操作
	def sell_action(self, this_symbol, this_price, this_amount, type="limit"):
		# this_price = self.trunc(this_price, self.price_decimals[this_symbol])
		this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		sell_result = self.fcoin.sell(this_symbol, this_price, this_amount, type)
		# print('sell_result is: ', sell_result)
		sell_order_id = sell_result['data']
		if sell_order_id:
			lprint("卖单 {} 价格成功委托, 订单ID {}".format(this_price, sell_order_id))
		return sell_order_id


	def strategy(self, type, pricedf, amount):
		# 从fieth开始交易, 因为它成交量最小
		# print('使用套利策略')
		self.time_last_call = time.time()
		if type == 1:
			# usdtamount = amount*pricedf["ethusdt"]
			fiamount = amount/pricedf["fieth"]

			thread1 = threading.Thread(target=self.sell_action, args=("fieth", pricedf["fieth"], fiamount))
			thread2 = threading.Thread(target=self.buy_action, args=("fiusdt", pricedf["fiusdt"], fiamount))
			thread3 = threading.Thread(target=self.sell_action, args=("ethusdt", pricedf["ethusdt"], amount))
			thread1.start()
			thread2.start()
			thread3.start()
		elif type == 2:
			fiamount = amount/pricedf["fieth"]
			# usdtamount = amount*pricedf["ethusdt"]
			
			thread1 = threading.Thread(target=self.buy_action, args=("fieth", pricedf["fieth"], fiamount))
			thread2 = threading.Thread(target=self.sell_action, args=("fiusdt", pricedf["fiusdt"], fiamount))
			thread3 = threading.Thread(target=self.buy_action, args=("ethusdt", pricedf["ethusdt"], amount))
			thread1.start()
			thread2.start()
			thread3.start()
		

	def trade(self, tickers=None):
		"""套利策略，寻找一个三元pair，看是不是满足套利规则。
    ETH/USDT, FI/ETH, FI/USDT
    ethusdt买一价 * fieth买一价 / fiusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程：usdt买fi，卖fi换回eth，卖eth换回usdt
    fiusdt买一价 / fieth卖一价 / ethusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程为：usdt买eth，eht买fi，卖fi换回usdt
    买一下标为2， 卖一下标为4"""
		# time.sleep(second)
		amount = _ethamount

		self_tickers = tickers
		if tickers == None:
			self_tickers = self.tickers

		if len(self_tickers) == len(symbol_pairs):
			info_df = pd.DataFrame(self_tickers).T
			# 买一卖一的均价
			info_df["price"] = (info_df[2]+info_df[4])/2
			
			taoli1 = info_df.loc["ethusdt", 2] * \
				info_df.loc["fieth", 2] / info_df.loc["fiusdt", 4]
			taoli2 = info_df.loc["fiusdt", 2] / \
				info_df.loc["fieth", 4] / info_df.loc["ethusdt", 4]
			
			if taoli1 > difference:
				info_df["price"] = info_df[2]
				info_df.loc["fiusdt", "price"] = info_df.loc["fiusdt", 4]
				if is_use_amount:
					if info_df.loc["ethusdt", 3] < _halfeth or info_df.loc["fiusdt", 5] < _halffi or info_df.loc["fieth", 3] < _halffi:
						lprint('挂单量太小，本次无法套利 方式一', logging.DEBUG)
						return
						
				lprint("满足套利条件1 套利值为{:.4}‰".format(taoli1*1000-1000))
				self.strategy(1, info_df.price, amount)
				lprint("fieth卖价：{} fiusdt买价：{} ethusdt卖价：{}".format(
					info_df.price["fieth"], info_df.price["fiusdt"], info_df.price["ethusdt"]))
				time.sleep(second)

			elif taoli2 > difference:
				info_df["price"] = info_df[4]
				info_df.loc["fiusdt", "price"] = info_df.loc["fiusdt", 2]
				if is_use_amount:
					if info_df.loc["ethusdt", 5] < _halfeth or info_df.loc["fiusdt", 3] < _halffi or info_df.loc["fieth", 5] < _halffi:
						lprint('挂单量太小，本次无法套利 方式二', logging.DEBUG)
						return
					# else:
					# 	if is_mutable_amount:
					# 		amount = min(rates) * amount
					# 		if amount > maxamount:
					# 			amount = maxamount
					# 		lprint("每单金额{}eth，最小利差{:.2}‰".format(amount, (difference-1)*1000))

				lprint("满足套利条件2 套利值比为{:.4}‰".format(taoli2*1000-1000))
				self.strategy(2, info_df.price, amount)
				lprint("fieth买价：{} fiusdt卖价：{} ethusdt买价：{}".format(
					info_df.price["fieth"], info_df.price["fiusdt"], info_df.price["ethusdt"]))
				time.sleep(second)
			else:
				lprint('差价太小，本次无法套利 方式一{} 方式二{}'.format(taoli1, taoli2), logging.DEBUG)

		if time.time() - self.time_last_call > heartbeat_interval:
			self.time_last_call = time.time()
			thread1 = threading.Thread(target=self.fcoin.get_server_time)
			thread2 = threading.Thread(target=self.fcoin.get_server_time)
			thread3 = threading.Thread(target=self.fcoin.get_server_time)
			thread1.start()
			thread2.start()
			thread3.start()
			


	def run(self):
		self.symbols_action()
		# self.get_balance_action(symbols)
		balance.balance()
		self.client = fcoin_client(self.on_close)
		self.client.start()
		self.client.subscribe_tickers(symbol_pairs, self.ticker_handler)
		while True:
			tickers = ticker_queue.get()
			self.trade(tickers)
			ticker_queue.queue.clear()


	def on_close(self):
		print("websocket closed, try to restart...")
		time.sleep(second)
		self.client = fcoin_client(self.on_close)
		self.client.start()
		self.client.subscribe_tickers(symbol_pairs, self.ticker_handler)



if __name__ == '__main__':
	try:
		logging.basicConfig(filename=logfile, level=logging.INFO,
                      format='%(asctime)s %(levelname)s %(threadName)s %(message)s')
		logging.warning("开始套利")
		lprint("每单金额{}eth，最小利差{:.2}‰".format(_ethamount, (difference-1)*1000))
		robot = ArbitrageRobot()
		robot.run()
	except KeyboardInterrupt:
		os._exit(1)

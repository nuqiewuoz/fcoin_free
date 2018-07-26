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

symbol_pairs = ['ethusdt', 'zipusdt', 'zipeth']
symbols = ['eth', 'usdt', 'zip']
ethamount = 0.005
difference = 1.0006
is_use_amount = True

heartbeat_interval = 60
is_mutable_amount = True
miniamount = 0.003
maxamount = 0.03
logfile = "arbitrage_strict.log"

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
		# return round(f, n)
		return math.floor(f*10**n)/10**n


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


	# 买操作
	def buy_action(self, this_symbol, this_price, this_amount, type="limit"):
		this_price = self.trunc(this_price, self.price_decimals[this_symbol])
		this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		buy_result = self.fcoin.buy(this_symbol, this_price, this_amount, type)
		# print('buy_result is', buy_result)
		buy_order_id = buy_result['data']
		if buy_order_id:
			lprint("买单 {} 价格成功委托, 订单ID {}".format(this_price, buy_order_id))
		return buy_order_id


	# 卖操作
	def sell_action(self, this_symbol, this_price, this_amount, type="limit"):
		this_price = self.trunc(this_price, self.price_decimals[this_symbol])
		this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		sell_result = self.fcoin.sell(this_symbol, this_price, this_amount, type)
		# print('sell_result is: ', sell_result)
		sell_order_id = sell_result['data']
		if sell_order_id:
			lprint("卖单 {} 价格成功委托, 订单ID {}".format(this_price, sell_order_id))
		return sell_order_id


	def strategy(self, type, pricedf, amount):
		# 从zipeth开始交易, 因为它成交量最小
		print('使用套利策略')
		self.time_last_call = time.time()
		amount = self.trunc(amount, 4)
		if type == 1:
			usdtamount = self.trunc(amount*pricedf["ethusdt"], 2)
			zipamount = self.trunc(usdtamount/pricedf["zipusdt"], 2)

			thread1 = threading.Thread(target=self.sell_action, args=("zipeth", pricedf["zipeth"], zipamount))
			thread2 = threading.Thread(target=self.buy_action, args=("zipusdt", pricedf["zipusdt"], zipamount))
			thread3 = threading.Thread(target=self.sell_action, args=("ethusdt", pricedf["ethusdt"], amount))
			thread1.start()
			thread2.start()
			thread3.start()
		elif type == 2:
			zipamount = self.trunc(amount/pricedf["zipeth"], 2)
			usdtamount = self.trunc(amount*pricedf["ethusdt"], 2)
			
			thread1 = threading.Thread(target=self.buy_action, args=("zipeth", pricedf["zipeth"], zipamount))
			thread2 = threading.Thread(target=self.sell_action, args=("zipusdt", pricedf["zipusdt"], zipamount))
			thread3 = threading.Thread(target=self.buy_action, args=("ethusdt", pricedf["ethusdt"], amount))
			thread1.start()
			thread2.start()
			thread3.start()
		

	def trade(self, tickers=None):
		"""套利策略，寻找一个三元pair，看是不是满足套利规则。
    ETH/USDT, ZIP/ETH, ZIP/USDT
    ethusdt买一价 * zipeth买一价 / zipusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程：usdt买zip，卖zip换回eth，卖eth换回usdt
    zipusdt买一价 / zipeth卖一价 / ethusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程为：usdt买eth，eht买zip，卖zip换回usdt
    买一下标为2， 卖一下标为4"""
		# time.sleep(second)
		amount = ethamount

		self_tickers = tickers
		if tickers == None:
			self_tickers = self.tickers

		if len(self_tickers) == len(symbol_pairs):
			info_df = pd.DataFrame(self_tickers).T
			# 买一卖一的均价
			info_df["price"] = (info_df[2]+info_df[4])/2
			
			taoli1 = info_df.loc["ethusdt", 2] * \
				info_df.loc["zipeth", 2] / info_df.loc["zipusdt", 4]
			taoli2 = info_df.loc["zipusdt", 2] / \
				info_df.loc["zipeth", 4] / info_df.loc["ethusdt", 4]
			
			if taoli1 > difference:
				info_df["price"] = info_df[2]
				info_df.loc["zipusdt", "price"] = info_df.loc["zipusdt", 4]
				if is_use_amount:
					info_df["amount"] = info_df[3]
					info_df.loc["zipusdt", "amount"] = info_df.loc["zipusdt", 5]
					zipamount = amount / info_df.price["zipeth"]
					rates = [info_df.amount["ethusdt"] / amount,
                                            info_df.amount["zipusdt"] / zipamount, info_df.amount["zipeth"] / zipamount]
					if min(rates) * amount < miniamount:
						lprint('挂单量太小，本次无法套利 方式一', logging.DEBUG)
						return
					else:
						if is_mutable_amount:
							amount = min(rates) * amount
							if amount > maxamount:
								amount = maxamount
							lprint("每单金额{}eth，最小利差{:.2}‰".format(amount, (difference-1)*1000))
				if ticker_queue.empty():
					lprint("满足套利条件1 套利值为{:.4}‰".format(taoli1*1000-1000))
					self.strategy(1, info_df.price, amount)
					lprint("zipeth卖价：{} zipusdt买价：{} ethusdt卖价：{}".format(
						info_df.price["zipeth"], info_df.price["zipusdt"], info_df.price["ethusdt"]))
					time.sleep(second)
				else:
					lprint("已经收到新的ticker数据，取消本次交易")

			elif taoli2 > difference:
				info_df["price"] = info_df[4]
				info_df.loc["zipusdt", "price"] = info_df.loc["zipusdt", 2]
				if is_use_amount:
					info_df["amount"] = info_df[5]
					info_df.loc["zipusdt", "amount"] = info_df.loc["zipusdt", 3]
					zipamount = amount / info_df.price["zipeth"]
					rates = [info_df.amount["ethusdt"] / amount,
                                            info_df.amount["zipusdt"] / zipamount, info_df.amount["zipeth"] / zipamount]
					if min(rates) * amount < miniamount:
						lprint('挂单量太小，本次无法套利 方式二', logging.DEBUG)
						return
					else:
						if is_mutable_amount:
							amount = min(rates) * amount
							if amount > maxamount:
								amount = maxamount
							lprint("每单金额{}eth，最小利差{:.2}‰".format(amount, (difference-1)*1000))
				if ticker_queue.empty():
					lprint("满足套利条件2 套利值比为{:.4}‰".format(taoli2*1000-1000))
					self.strategy(2, info_df.price, amount)
					lprint("zipeth买价：{} zipusdt卖价：{} ethusdt买价：{}".format(
						info_df.price["zipeth"], info_df.price["zipusdt"], info_df.price["ethusdt"]))
					time.sleep(second)
				else:
					lprint("已经收到新的ticker数据，取消本次交易")
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
		logging.basicConfig(filename=logfile, level=logging.DEBUG,
                      format='%(asctime)s %(levelname)s %(threadName)s %(message)s')
		logging.warning("开始套利")
		lprint("每单金额{}eth，最小利差{:.2}‰".format(ethamount, (difference-1)*1000))
		robot = ArbitrageRobot()
		robot.run()
	except KeyboardInterrupt:
		os._exit(1)

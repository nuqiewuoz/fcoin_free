from fcoin import Fcoin
from fcoin_websocket.fcoin_client import fcoin_client
from auth import api_key, api_secret
import os
import time
# import math
import logging
import balance
import threading
import queue
import sys


sleepsecond = 0.5	# 每单结束后的休息时间
s1 = 'fi'
s2 = 'eth'
s3 = 'usdt'
# 为了减少计算量，避免单位换算
_s2amount = 0.01
_s1amount = 50  # 0.01*5000
symbols = [s1, s2, s3]
sp1 = s1+s2	# 'fieth'
sp2 = s1+s3	# 'fiusdt'
sp3 = s2+s3	# 'ethusdt'
symbol_pairs = [sp1, sp2, sp3]
# 超过目标量的一半，就可以下单
halfs2 = _s2amount/2
halfs1 = _s1amount/2

# 套利比例，1.001意味着1‰
difference = 1.001
is_use_amount = True

heartbeat_interval = 60
is_mutable_amount = False
# miniamount = 0.01
# maxamount = 0.04
logfile = "{}_{}_{}_arbitrage.log".format(s1, s2, s3)

ticker_queue = queue.Queue()


class ArbitrageRobot(object):
	"""docstring for Robot"""

	def __init__(self):
		self.fcoin = Fcoin(api_key, api_secret)
		self.price_decimals = {}
		self.amount_decimals = {}
		self.tickers = {}
		self.time_last_call = time.time()


	# 截取指定小数位数
	def trunc(self, f, n):
		return round(f, n)
		# return math.floor(f*10**n)/10**n


	def ticker_handler(self, message):
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
		buy_order_id = buy_result['data']
		if buy_order_id:
			logging.info("买单 {} 价格成功委托, 订单ID {}".format(this_price, buy_order_id))
		return buy_order_id


	# 卖操作
	def sell_action(self, this_symbol, this_price, this_amount, type="limit"):
		# this_price = self.trunc(this_price, self.price_decimals[this_symbol])
		this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		sell_result = self.fcoin.sell(this_symbol, this_price, this_amount, type)
		sell_order_id = sell_result['data']
		if sell_order_id:
			logging.info("卖单 {} 价格成功委托, 订单ID {}".format(this_price, sell_order_id))
		return sell_order_id


	def strategy(self, type, pricedf, amount):
		self.time_last_call = time.time()
		if type == 1:
			s1amount = amount/pricedf[sp1]

			thread1 = threading.Thread(target=self.sell_action, args=(sp1, pricedf[sp1], s1amount))
			thread2 = threading.Thread(target=self.buy_action, args=(sp2, pricedf[sp2], s1amount))
			thread3 = threading.Thread(target=self.sell_action, args=(sp3, pricedf[sp3], amount))
			thread1.start()
			thread2.start()
			thread3.start()
		elif type == 2:
			s1amount = amount/pricedf[sp1]
			
			thread1 = threading.Thread(target=self.buy_action, args=(sp1, pricedf[sp1], s1amount))
			thread2 = threading.Thread(target=self.sell_action, args=(sp2, pricedf[sp2], s1amount))
			thread3 = threading.Thread(target=self.buy_action, args=(sp3, pricedf[sp3], amount))
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
		# time.sleep(sleepsecond)
		amount = _s2amount

		self_tickers = tickers

		if len(self_tickers) == len(symbol_pairs):
			taoli1 = self_tickers[sp3][2] * \
				self_tickers[sp1][2] / self_tickers[sp2][4]
			taoli2 = self_tickers[sp2][2] / \
				self_tickers[sp1][4] / self_tickers[sp3][4]
			
			if taoli1 > difference:
				pricedf = {sp3: self_tickers[sp3][2],
                                    sp2: self_tickers[sp2][4],
                                    sp1: self_tickers[sp1][2]}
				if is_use_amount:
					if self_tickers[sp3][3] < halfs2 or self_tickers[sp2][5] < halfs1 or self_tickers[sp1][3] < halfs1:
						logging.debug('挂单量太小，本次无法套利 方式一')
						return
						
				logging.info("满足套利条件1 套利值为{:.4}‰".format(taoli1*1000-1000))
				self.strategy(1, pricedf, amount)
				logging.info("{}卖价：{} {}买价：{} {}卖价：{}".format(sp1,
                                                  pricedf[sp1], sp2, pricedf[sp2], sp3, pricedf[sp3]))
				time.sleep(sleepsecond)
				print("满足套利条件1 套利值为{:.4}‰".format(taoli1*1000-1000))
			elif taoli2 > difference:
				pricedf = {sp3: self_tickers[sp3][4],
                                    sp2: self_tickers[sp2][2],
                                    sp1: self_tickers[sp1][4]}
				if is_use_amount:
					if self_tickers[sp3][5] < halfs2 or self_tickers[sp2][3] < halfs1 or self_tickers[sp1][5] < halfs1:
						logging.debug('挂单量太小，本次无法套利 方式二')
						return

				logging.info("满足套利条件2 套利值比为{:.4}‰".format(taoli2*1000-1000))
				self.strategy(2, pricedf, amount)
				logging.info("{}买价：{} {}卖价：{} {}买价：{}".format(sp1,
                                                  pricedf[sp1], sp2, pricedf[sp2], sp3, pricedf[sp3]))
				time.sleep(sleepsecond)
				print("满足套利条件2 套利值比为{:.4}‰".format(taoli2*1000-1000))
			else:
				logging.debug('差价太小，本次无法套利 方式一{} 方式二{}'.format(taoli1, taoli2))
				print('差价太小，本次无法套利 方式一{} 方式二{}'.format(taoli1, taoli2))

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
		balance.balance(symbols)
		self.client = fcoin_client(self.on_close)
		self.client.start()
		self.client.subscribe_tickers(symbol_pairs, self.ticker_handler)
		while True:
			tickers = ticker_queue.get()
			self.trade(tickers)
			ticker_queue.queue.clear()


	def on_close(self):
		print("websocket closed, try to restart...")
		time.sleep(sleepsecond)
		self.client = fcoin_client(self.on_close)
		self.client.start()
		self.client.subscribe_tickers(symbol_pairs, self.ticker_handler)


if __name__ == '__main__':
	try:
		if len(sys.argv) == 2:
			configfile = sys.argv[1]
			import importlib
			config_module = importlib.import_module(configfile)
			s1 = config_module.s1
			s2 = config_module.s2
			s3 = config_module.s3
			halfs1 = config_module.halfs1
			halfs2 = config_module.halfs2
			sleepsecond = config_module.sleepsecond
			difference = config_module.difference
			is_use_amount = config_module.is_use_amount

			symbols = [s1, s2, s3]
			sp1 = s1+s2
			sp2 = s1+s3
			sp3 = s2+s3
			symbol_pairs = [sp1, sp2, sp3]
			logfile = "{}_{}_{}_arbitrage.log".format(s1, s2, s3)


		logging.basicConfig(filename=logfile, level=logging.INFO,
                      format='%(asctime)s %(levelname)s %(threadName)s %(message)s')
		logging.warning("开始套利")
		logging.info("每单金额{}{}，最小利差{:.2}‰".format(_s2amount, s2, (difference-1)*1000))
		logging.info("是否进行数量检查:{}，是否灵活调整每单金额:{}".format(is_use_amount, is_mutable_amount))
		robot = ArbitrageRobot()
		robot.run()
	except KeyboardInterrupt:
		os._exit(1)

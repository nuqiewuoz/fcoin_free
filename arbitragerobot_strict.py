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

symbol_pairs = ['ethusdt', 'ftusdt', 'fteth']
symbols = ['eth', 'usdt', 'ft']
ethamount = 0.01
difference = 1.0005
is_market_order = False
need_calc_slippage = False
is_use_amount = True
is_mutable_amount = True
miniamount = 0.005
maxamount = 0.02
logfile = "arbitrage_strict1.log"

if is_market_order:
	logfile = "arbitrage_strict6.log"
	# need_calc_slippage = True


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
		pd.set_option('precision', 8)


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
	def buy_action(self, this_symbol, this_price, this_amount, type="limit"):
		if not is_market_order:
			this_price = self.trunc(this_price, self.price_decimals[this_symbol])
			this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		buy_result = self.fcoin.buy(this_symbol, this_price, this_amount, type)
		# print('buy_result is', buy_result)
		buy_order_id = buy_result['data']
		if buy_order_id:
			if is_market_order:
				lprint("{} 买单成功委托, 订单ID {}".format(this_symbol, buy_order_id))
			else:
				lprint("买单 {} 价格成功委托, 订单ID {}".format(this_price, buy_order_id))
		return buy_order_id


	# 卖操作
	def sell_action(self, this_symbol, this_price, this_amount, type="limit"):
		if not is_market_order:
			this_price = self.trunc(this_price, self.price_decimals[this_symbol])
			this_amount = self.trunc(this_amount, self.amount_decimals[this_symbol])
		sell_result = self.fcoin.sell(this_symbol, this_price, this_amount, type)
		# print('sell_result is: ', sell_result)
		sell_order_id = sell_result['data']
		if sell_order_id:
			if is_market_order:
				lprint("{} 卖单成功委托, 订单ID {}".format(this_symbol, sell_order_id))
			else:
				lprint("卖单 {} 价格成功委托, 订单ID {}".format(this_price, sell_order_id))
		return sell_order_id


	def slippage(self, orderid, price):
		# 单位是千分之一
		result = self.fcoin.order_result(orderid)
		print(result)
		while result == None or len(result['data']) == 0:
			print("reconnect...order...")
			time.sleep(0.1)
			result = self.fcoin.order_result(orderid)
		slip = 0
		amount = 0
		total = 0
		for order in result['data']:
			amount += float(order["filled_amount"])
			total += float(order["filled_amount"])*float(order["price"])
		realprice = total/amount
		lprint("实际成交均价为{}".format(realprice))
		if result['data'][0]['type'] == "sell_market":
			slip = (price-realprice)/price
		else:
			slip = (realprice-price)/price
		return slip*1000


	def strategy(self, type, pricedf, amount):
		# 从fteth开始交易, 因为它成交量最小
		print('使用套利策略')
		amount = self.trunc(amount, 4)
		if type == 1:
			usdtamount = self.trunc(amount*pricedf["ethusdt"], 2)
			ftamount = self.trunc(usdtamount/pricedf["ftusdt"], 2)
			if is_market_order:
				# 市价单的标的不同
				order_id1 = self.sell_action("fteth", 0, ftamount, "market")
				order_id2 = self.buy_action("ftusdt", 0, usdtamount, "market")
				order_id3 = self.sell_action("ethusdt", 0, amount, "market")
				if need_calc_slippage:
					# 统计滑点
					slippage1 = self.slippage(order_id1, pricedf["fteth"])
					print("卖出 fteth 滑点为{:.3}‰".format(slippage1))
					slippage2 = self.slippage(order_id2, pricedf["ftusdt"])
					print("买入 ftusdt 滑点为{:.3}‰".format(slippage2))
					slippage3 = self.slippage(order_id3, pricedf["ethusdt"])
					print("卖出 ethusdt 滑点为{:.3}‰".format(slippage3))
					lprint("总滑点为{:.3}‰ 依次为{:.3}‰ {:.3}‰ {:.3}‰".format(
						slippage1+slippage2+slippage3, slippage1, slippage2, slippage3))
			else:
				self.sell_action("fteth", pricedf["fteth"], ftamount)
				self.buy_action("ftusdt", pricedf["ftusdt"], ftamount)
				self.sell_action("ethusdt", pricedf["ethusdt"], amount)
		elif type == 2:
			ftamount = self.trunc(amount/pricedf["fteth"], 2)
			usdtamount = self.trunc(amount*pricedf["ethusdt"], 2)
			if is_market_order:
				# 市价单的标的不同
				order_id1 = self.buy_action("fteth", 0, amount, "market")
				order_id2 = self.sell_action("ftusdt", 0, ftamount, "market")
				order_id3 = self.buy_action("ethusdt", 0, usdtamount, "market")
				if need_calc_slippage:
					# 统计滑点
					slippage1 = self.slippage(order_id1, pricedf["fteth"])
					print("买入 fteth 滑点为{:.3}‰".format(slippage1))
					slippage2 = self.slippage(order_id2, pricedf["ftusdt"])
					print("卖出 ftusdt 滑点为{:.3}‰".format(slippage2))
					slippage3 = self.slippage(order_id3, pricedf["ethusdt"])
					print("买入 ethusdt 滑点为{:.3}‰".format(slippage3))
					lprint("总滑点为{:.3}‰ 依次为{:.3}‰ {:.3}‰ {:.3}‰".format(
						slippage1+slippage2+slippage3, slippage1, slippage2, slippage3))
			else:
				self.buy_action("fteth", pricedf["fteth"], ftamount)
				self.sell_action("ftusdt", pricedf["ftusdt"], ftamount)
				self.buy_action("ethusdt", pricedf["ethusdt"], amount)
		

	def trade(self):
		"""套利策略，寻找一个三元pair，看是不是满足套利规则。
    ETH/USDT, FT/ETH, FT/USDT
    ethusdt买一价 * fteth买一价 / ftusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程：usdt买ft，卖ft换回eth，卖eth换回usdt
    ftusdt买一价 / fteth卖一价 / ethusdt卖一价, 如果大于1很多，就存在套利空间
    操作流程为：usdt买eth，eht买ft，卖ft换回usdt
    买一下标为2， 卖一下标为4"""
		time.sleep(second)
		amount = ethamount
		
		if len(self.tickers) == len(symbol_pairs):
			info_df = pd.DataFrame(self.tickers).T
			# 买一卖一的均价
			info_df["price"] = (info_df[2]+info_df[4])/2
			
			taoli1 = info_df.loc["ethusdt", 2] * \
				info_df.loc["fteth", 2] / info_df.loc["ftusdt", 4]
			taoli2 = info_df.loc["ftusdt", 2] / \
				info_df.loc["fteth", 4] / info_df.loc["ethusdt", 4]
			
			if taoli1 > difference:
				info_df["price"] = info_df[2]
				info_df.loc["ftusdt", "price"] = info_df.loc["ftusdt", 4]
				if is_use_amount:
					info_df["amount"] = info_df[3]
					info_df.loc["ftusdt", "amount"] = info_df.loc["ftusdt", 5]
					ftamount = amount / info_df.price["fteth"]
					rates = [info_df.amount["ethusdt"] / amount,
                                            info_df.amount["ftusdt"] / ftamount, info_df.amount["fteth"] / ftamount]
					if min(rates) * amount < miniamount:
						lprint('挂单量太小，本次无法套利 方式一', logging.DEBUG)
						print("{} {}".format(amount, ftamount))
						print(info_df.amount)
						return
					else:
						if is_mutable_amount:
							amount = min(rates) * amount
							if amount > maxamount:
								amount = maxamount
							lprint("每单金额{}eth，最小利差{:.2}‰".format(amount, (difference-1)*1000))
				self.strategy(1, info_df.price, amount)
				lprint("满足套利条件1 套利值为{:.4}‰".format(taoli1*1000-1000))
				lprint("fteth卖价：{} ftusdt买价：{} ethusdt卖价：{}".format(
					info_df.price["fteth"], info_df.price["ftusdt"], info_df.price["ethusdt"]))
				# print(info_df)
			elif taoli2 > difference:
				info_df["price"] = info_df[4]
				info_df.loc["ftusdt", "price"] = info_df.loc["ftusdt", 2]
				if is_use_amount:
					info_df["amount"] = info_df[5]
					info_df.loc["ftusdt", "amount"] = info_df.loc["ftusdt", 3]
					ftamount = amount / info_df.price["fteth"]
					rates = [info_df.amount["ethusdt"] / amount,
                                            info_df.amount["ftusdt"] / ftamount, info_df.amount["fteth"] / ftamount]
					if min(rates) * amount < miniamount:
						lprint('挂单量太小，本次无法套利 方式二', logging.DEBUG)
						print("{} {}".format(amount, ftamount))
						print(info_df.amount)
						return
					else:
						if is_mutable_amount:
							amount = min(rates) * amount
							if amount > maxamount:
								amount = maxamount
							lprint("每单金额{}eth，最小利差{:.2}‰".format(amount, (difference-1)*1000))
				self.strategy(2, info_df.price, amount)
				lprint("满足套利条件2 套利值比为{:.4}‰".format(taoli2*1000-1000))
				lprint("fteth买价：{} ftusdt卖价：{} ethusdt买价：{}".format(
					info_df.price["fteth"], info_df.price["ftusdt"], info_df.price["ethusdt"]))
				# print(info_df)
			else:
				lprint('差价太小，本次无法套利 方式一{} 方式二{}'.format(taoli1, taoli2), logging.DEBUG)


	def run(self):
		self.client = fcoin_client(self.on_close)
		self.client.start()
		self.client.subscribe_tickers(symbol_pairs, self.ticker_handler)
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
		self.client.subscribe_tickers(symbol_pairs, self.ticker_handler)



if __name__ == '__main__':
	try:
		logging.basicConfig(filename=logfile, level=logging.INFO,
                      format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
		logging.warning("套利成功！")
		lprint("每单金额{}eth，最小利差{:.2}‰".format(ethamount, (difference-1)*1000))
		robot = ArbitrageRobot()
		robot.run()
	except KeyboardInterrupt:
		os._exit(1)

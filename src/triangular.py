import time
from exchange import Binance, Poloniex
import json
from datetime import datetime
import sys
import binance.client
import os
import applog
from config import Config


def str8(v):
    return str(round(v, 8))


class Triangular:
    def __init__(self, *args, **kwargs):
        self.binance = Binance()
        self.poloniex = Poloniex()
        self.tsv_filepath = "./log/triangular.tsv"
        self.only_binance_tsv_filepath = "./log/triangular_only_binance.tsv"
        self.interval = 3

    def log(self, row, exchange):
        record = "\t".join(row)
        print(record)
        with open(self.tsv_filepath, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(record + '\n')

        if exchange == "Binance":
            with open(self.only_binance_tsv_filepath, mode = 'a', encoding = 'utf-8') as fh:
                fh.write(record + '\n')

    def run(self, run_mode, is_binance, is_poloniex):
        if run_mode == "RealTrade":
            dryrun = False
        else:
            dryrun = True

        self.binance.refresh_exchange_info()

        while True:
            total = 0
            hope = 0

            if is_binance:
                hash = self.binance.refresh_ticker_all()
                triangle_orders = []
                for symbol in hash:
                    r = self.triangle_all_check(triangle_orders, "Binance", "BTC", "ETH", symbol, hash, self.binance.comission_fee, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Binance", "BTC", "BNB", symbol, hash, self.binance.comission_fee, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Binance", "ETH", "BNB", symbol, hash, self.binance.comission_fee, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                self.trade_binance(triangle_orders, dryrun)

            if is_poloniex:
                j = self.poloniex.refresh_ticker_all()
                hash ={}
                for symbol in j:
                    r = symbol.split("_")
                    newsymbol = r[1] + r[0]
                    hash[newsymbol] = {
                        "askPrice": j[symbol]["lowestAsk"],
                        "askQty": -1,
                        "bidPrice": j[symbol]["highestBid"],
                        "bidQty": -1
                    }
                triangle_orders = []
                for symbol in hash:
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "BTC", "ETH", symbol, hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "BTC", "XMR", symbol, hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "ETH", "XMR", symbol, hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "USDT", "BTC", symbol, hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "USDT", "ETH", symbol, hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                # self.trade_poloniex(orders)  <= TODO

            print("hope/total = " + str(hope) + "/" + str(total))
            time.sleep(self.interval)

    def triangle_all_check(self, triangle_orders, exchange_name, base_currency_name, via_currency_name, symbol, hash, fee, dryrun):
        i = symbol.find(via_currency_name)
        if not (i == -1 or i == 0):
            currency_name = symbol[0:len(symbol) - len(via_currency_name)]
            btcpair_symbol = currency_name + base_currency_name
            viapair_symbol = currency_name + via_currency_name
            viabtcpair_symbol = via_currency_name + base_currency_name
            if currency_name in ["BTC", "ETH", "BNB", "XMR", "USDT"]:
                return -1
            if not (btcpair_symbol in hash and viapair_symbol in hash and viabtcpair_symbol in hash):
                return -1

            xbtc_ask_price   = float(hash[btcpair_symbol]["askPrice"])    # Buy X at BTC
            xbtc_ask_lot     = float(hash[btcpair_symbol]["askQty"])
            xvia_bid_price   = float(hash[viapair_symbol]["bidPrice"])    # Buy (VIA) at X
            xvia_bid_lot     = float(hash[viapair_symbol]["bidQty"])
            viabtc_bid_price = float(hash[viabtcpair_symbol]["bidPrice"]) # Buy BTC at (VIA)
            viabtc_bid_lot   = float(hash[viabtcpair_symbol]["bidQty"])
            rate_via_bid     = 1 / xbtc_ask_price * xvia_bid_price * viabtc_bid_price * (1 - fee)**3

            viabtc_ask_price = float(hash[viabtcpair_symbol]["askPrice"]) # Buy (VIA) at BTC
            viabtc_ask_lot   = float(hash[viabtcpair_symbol]["askQty"])
            xvia_ask_price   = float(hash[viapair_symbol]["askPrice"])    # Buy X at (VIA)
            xvia_ask_lot     = float(hash[viapair_symbol]["askQty"])
            xbtc_bid_price   = float(hash[btcpair_symbol]["bidPrice"])    # Buy BTC at X
            xbtc_bid_lot     = float(hash[btcpair_symbol]["bidQty"])
            rate_via_ask     = 1 / viabtc_ask_price / xvia_ask_price * xbtc_bid_price * (1 - fee)**3

            hope = 0
            if rate_via_bid > 1:
                row_via_bid = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    exchange_name,
                    base_currency_name + "->" + currency_name + "->" + via_currency_name + "->" + base_currency_name, str8(rate_via_bid),
                    btcpair_symbol + ":BUY", str8(xbtc_ask_price), str8(xbtc_ask_lot), str8(xbtc_ask_price * xbtc_ask_lot),
                    viapair_symbol + ":SELL", str8(xvia_bid_price), str8(xvia_bid_lot), str8(xvia_bid_price * xvia_bid_lot * viabtc_bid_price),
                    viabtcpair_symbol + ":SELL", str8(viabtc_bid_price), str8(viabtc_bid_lot), str8(viabtc_bid_price * viabtc_bid_lot)
                ]
                self.log(row_via_bid, exchange_name)
                triangle_orders.extend([row_via_bid])
                hope += 1
            if rate_via_ask > 1:
                row_via_ask = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    exchange_name,
                    base_currency_name + "->" + via_currency_name + "->" + currency_name + "->" + base_currency_name, str8(rate_via_ask),
                    viabtcpair_symbol + ":BUY", str8(viabtc_ask_price), str8(viabtc_ask_lot), str8(viabtc_ask_price * viabtc_ask_lot),
                    viapair_symbol + ":BUY", str8(xvia_ask_price), str8(xvia_ask_lot), str8(xvia_ask_price * xvia_ask_lot * viabtc_ask_price),
                    btcpair_symbol + ":SELL", str8(xbtc_bid_price), str8(xbtc_bid_lot), str8(xbtc_bid_price * xbtc_bid_lot)
                ]
                self.log(row_via_ask, exchange_name)
                triangle_orders.extend([row_via_ask])
                hope += 1
            return hope
        else:
            return -1

    def trade_binance(self, triangle_orders, dryrun):
        for triangle_order in triangle_orders:
            rate = float(triangle_order[3])
            if rate - 1 < 0.003:
                print("Profits too small. rate=%s" % rate) 
                continue

            base_currency_name = triangle_order[2][:3]
            viasymbole = triangle_order[8].split(":")[0]
            via_currency_name = viasymbole[len(viasymbole)-3:]
            orders = [
                {
                    "symbol": triangle_order[4].split(":")[0],
                    "side": triangle_order[4].split(":")[1],
                    "price": float(triangle_order[5]),
                    "lot": float(triangle_order[6]),
                    "base_lot": float(triangle_order[7]),
                },
                {
                    "symbol": triangle_order[8].split(":")[0],
                    "side": triangle_order[8].split(":")[1],
                    "price": float(triangle_order[9]),
                    "lot": float(triangle_order[10]),
                    "base_lot": float(triangle_order[11]),
                },
                {
                    "symbol": triangle_order[12].split(":")[0],
                    "side": triangle_order[12].split(":")[1],
                    "price": float(triangle_order[13]),
                    "lot": float(triangle_order[14]),
                    "base_lot": float(triangle_order[15]),
                },
            ]

            min_base_lot = min([orders[0]["base_lot"], orders[1]["base_lot"], orders[2]["base_lot"]]) * 0.5 # risk hedge
            min_base_lot = min(min_base_lot, self.__get_asset_lot(base_currency_name))

            if min_base_lot < self.__get_lower_limit(base_currency_name, True):
                print("Total must be at latest %f%s. (min_base_lot = %0.8f)" % (self.__get_lower_limit(base_currency_name, True), base_currency_name, min_base_lot))
                continue

            orders[0]["final_lot"] = self.binance.lot_filter(orders[0]["symbol"], orders[0]["lot"] * min_base_lot / orders[0]["base_lot"])
            if orders[1]["side"] == "BUY":
                orders[1]["final_lot"] = self.binance.lot_filter(orders[1]["symbol"], orders[0]["final_lot"] / orders[1]["price"])
            elif orders[1]["side"] == "SELL":
                orders[1]["final_lot"] = self.binance.lot_filter(orders[1]["symbol"], orders[0]["final_lot"] * orders[1]["price"])
            orders[2]["final_lot"] = orders[1]["final_lot"]

            via_lot = orders[1]["final_lot"] * orders[1]["price"]
            if via_lot < self.__get_lower_limit(via_currency_name, False):
                print("Total must be at latest %f%s. (via_lot = %0.8f)" % (self.__get_lower_limit(via_currency_name, False), via_currency_name, via_lot))
                continue

            msgs = []
            msgs.append("1st order:%s(%s), price:%0.8f, lot:%0.8f, btc_lot:%0.8f, final_lot:%0.8f" % (orders[0]["symbol"], orders[0]["side"], orders[0]["price"], orders[0]["lot"], orders[0]["base_lot"], orders[0]["final_lot"]))
            msgs.append("2nd order:%s(%s), price:%0.8f, lot:%0.8f, btc_lot:%0.8f, final_lot:%0.8f" % (orders[1]["symbol"], orders[1]["side"], orders[1]["price"], orders[1]["lot"], orders[1]["base_lot"], orders[1]["final_lot"]))
            msgs.append("3rd order:%s(%s), price:%0.8f, lot:%0.8f, btc_lot:%0.8f, final_lot:%0.8f" % (orders[2]["symbol"], orders[2]["side"], orders[2]["price"], orders[2]["lot"], orders[2]["base_lot"], orders[2]["final_lot"]))

            expected_revenue = orders[2]["final_lot"] * orders[2]["price"] - orders[0]["final_lot"] * orders[0]["price"]
            msgs.append("Expected Revenue:%0.8f%s    1st lot(%0.8f(%0.8f%s)) => 3rd lot(%0.8f(%0.8f%s))" % (
                expected_revenue,
                base_currency_name,
                orders[0]["final_lot"],
                orders[0]["final_lot"] * orders[0]["price"],
                base_currency_name,
                orders[2]["final_lot"],
                orders[2]["final_lot"] * orders[2]["price"],
                base_currency_name,
            ))
            expected_fee = (lambda x: x - x * (1 - self.binance.comission_fee)**3)(orders[0]["final_lot"] * orders[0]["price"])
            msgs.append("Expected fee:%0.8f%s" % (expected_fee, base_currency_name))
            msgs.append("Expected Final Revenue:%0.8f%s" % (expected_revenue, base_currency_name))

            for msg in msgs:
                applog.info(msg)

            if dryrun:
                continue

            order_count = 0
            for order in orders:
                r = self.binance.client.create_order(
                    symbol = order["symbol"],
                    side = order["side"],
                    type = binance.client.Client.ORDER_TYPE_LIMIT,
                    timeInForce = binance.client.Client.TIME_IN_FORCE_GTC,
                    quantity = order["final_lot"],
                    price = "%0.8f" % order["price"],
                )
                applog.info("binance.create_order" + str(r))
                i = 0
                while True:
                    r = self.binance.client.get_order(symbol = r["symbol"], orderId = r["orderId"])
                    if r["status"] == binance.client.Client.ORDER_STATUS_FILLED:
                        applog.info("filled.")
                        order_count += 1
                        break
                    elif r["status"] in [
                        binance.client.Client.ORDER_STATUS_NEW,
                        binance.client.Client.ORDER_STATUS_PARTIALLY_FILLED,
                    ]:
                        applog.info("%s,%s,order_count:%d,price:%s,lot:%s,status:%s(%d)" % (r["symbol"], r["side"], order_count, r["price"], r["origQty"], r["status"], i))
                        if i < 30:
                            time.sleep(0.001)
                        elif i < 100:
                            if order_count == 0 and r["status"] == binance.client.Client.ORDER_STATUS_NEW:
                                applog.warning("Skip triangular arbitrage. status=" + r["status"])
                                break
                            time.sleep(0.01)
                        else:
                            time.sleep(3)
                        i += 1
                    else:
                        # binance.client.Client.ORDER_STATUS_CANCELED
                        # binance.client.Client.ORDER_STATUS_EXPIRED
                        # binance.client.Client.ORDER_STATUS_PENDING_CANCEL
                        # binance.client.Client.ORDER_STATUS_REJECTED
                        if order_count == 0:
                            applog.warning("Skip triangular arbitrage. status=" + r["status"])
                            break
                        else:
                            applog.error("Failed triangular arbitrage. status=" + r["status"])
                            raise "Failed triangular arbitrage."
                if order_count == 0:
                    break


    @staticmethod
    def __get_lower_limit(base_currency_name, put_the_margin):
        lower_limit = 0.001  # "BTC"
        if base_currency_name == "ETH":
            lower_limit = 0.01
        elif base_currency_name == "BNB":
            lower_limit = 1

        if put_the_margin:
            lower_limit = lower_limit * 10

        return lower_limit

    @staticmethod
    def __get_asset_lot(base_currency_name):
        return Config.get_triangular_asset()["binance"][base_currency_name]


if __name__ == '__main__':
    applog.init("app_triangular")

    if len(sys.argv) > 1 and sys.argv[1] in {"RealTrade", "DemoTrade", "Batch"}:
        run_mode = sys.argv[1]
    else:
        applog.error("bad argument!")
        sys.exit()

    triangular = Triangular()
    triangular.run(run_mode, True, False)
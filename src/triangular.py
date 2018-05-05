import time
from exchange import Binance, Poloniex
import json
from datetime import datetime
import sys
import binance.client
from binance.exceptions import BinanceAPIException
import os
import applog
from config import Config
from mailer import Mailer


def str8(v):
    return "%0.8f" % v


class Triangular:
    def __init__(self, *args, **kwargs):
        self.binance = Binance()
        self.poloniex = Poloniex()
        self.log_dir = Config.get_log_dir() + "/triangular"
        self.interval = 3
        self.profit_lower_limit = Config.get_triangular_profit_lower_limit()

    def run(self, run_mode, is_binance, is_poloniex):
        applog.init(self.__prepare_dir(self.log_dir + "/app.log"))

        if run_mode == "RealTrade":
            dryrun = False
        else:
            dryrun = True

        mailer = Mailer()
        if mailer.is_use():
            if not mailer.checkmailer():
                applog.error("mailer not activation!")
                sys.exit()

        applog.info("========================================")
        applog.info("Start Triangular Arbitrage. RunMode = " + run_mode)
        applog.info("binance.comission_fee: %0.8f" % self.binance.comission_fee)
        applog.info("profit_lower_limit: %0.8f" % self.profit_lower_limit)
        applog.info("========================================")

        self.binance.refresh_exchange_info()

        while True:
            total = 0
            hope = 0

            if is_binance:
                book_ticker_hash = self.binance.refresh_ticker_all()
                triangle_orders = []
                for symbol in book_ticker_hash:
                    r = self.triangle_all_check(triangle_orders, "Binance", "BTC", "ETH", symbol, book_ticker_hash, self.binance.comission_fee, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Binance", "BTC", "BNB", symbol, book_ticker_hash, self.binance.comission_fee, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Binance", "ETH", "BNB", symbol, book_ticker_hash, self.binance.comission_fee, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                triangle_order = self.choice_order(triangle_orders)
                if triangle_order is not None:
                    self.trade_binance(triangle_order, dryrun)

            if is_poloniex:
                j = self.poloniex.refresh_ticker_all()
                book_ticker_hash ={}
                for symbol in j:
                    r = symbol.split("_")
                    newsymbol = r[1] + r[0]
                    book_ticker_hash[newsymbol] = {
                        "askPrice": j[symbol]["lowestAsk"],
                        "askQty": -1,
                        "bidPrice": j[symbol]["highestBid"],
                        "bidQty": -1
                    }
                triangle_orders = []
                for symbol in book_ticker_hash:
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "BTC", "ETH", symbol, book_ticker_hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "BTC", "XMR", symbol, book_ticker_hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "ETH", "XMR", symbol, book_ticker_hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "USDT", "BTC", symbol, book_ticker_hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                    r = self.triangle_all_check(triangle_orders, "Poloniex", "USDT", "ETH", symbol, book_ticker_hash, 0.0025, dryrun)
                    if r >=0:
                        total += 2
                        hope += r
                # self.trade_poloniex(orders)  <= TODO

            print("hope/total = " + str(hope) + "/" + str(total))
            time.sleep(self.interval)

    def triangle_all_check(self, triangle_orders, exchange_name, base_currency_name, via_currency_name, symbol, book_ticker_hash, fee, dryrun):
        i = symbol.find(via_currency_name)
        if not (i == -1 or i == 0):
            currency_name = symbol[0:len(symbol) - len(via_currency_name)]
            basepair_symbol = currency_name + base_currency_name
            viapair_symbol = currency_name + via_currency_name
            viabasepair_symbol = via_currency_name + base_currency_name
            if currency_name in ["BTC", "ETH", "BNB", "XMR", "USDT"]:
                return -1
            if not (basepair_symbol in book_ticker_hash and viapair_symbol in book_ticker_hash and viabasepair_symbol in book_ticker_hash):
                return -1

            risk_hedge = 1

            xbase_ask_price   = float(book_ticker_hash[basepair_symbol]["askPrice"])    # Buy (BASE) -> X
            xbase_ask_lot     = float(book_ticker_hash[basepair_symbol]["askQty"])
            xvia_bid_price    = float(book_ticker_hash[viapair_symbol]["bidPrice"])     # Sell X -> (VIA)
            xvia_bid_price    = xvia_bid_price - self.binance.get_tick_size(viapair_symbol) * risk_hedge
            xvia_bid_lot      = float(book_ticker_hash[viapair_symbol]["bidQty"])
            viabase_bid_price = float(book_ticker_hash[viabasepair_symbol]["bidPrice"]) # Sell (VIA) -> (BASE)
            viabase_bid_lot   = float(book_ticker_hash[viabasepair_symbol]["bidQty"])
            rate_via_bid      = 1 / xbase_ask_price * xvia_bid_price * viabase_bid_price * (1 - fee)**3

            viabase_ask_price = float(book_ticker_hash[viabasepair_symbol]["askPrice"]) # Buy (BASE) -> (VIA)
            viabase_ask_lot   = float(book_ticker_hash[viabasepair_symbol]["askQty"])
            xvia_ask_price    = float(book_ticker_hash[viapair_symbol]["askPrice"])     # Buy (VIA) -> X
            xvia_ask_lot      = float(book_ticker_hash[viapair_symbol]["askQty"])
            xbase_bid_price   = float(book_ticker_hash[basepair_symbol]["bidPrice"])    # Sell X -> (BASE)
            xbase_bid_price   = xbase_bid_price - self.binance.get_tick_size(basepair_symbol) * risk_hedge
            xbase_bid_lot     = float(book_ticker_hash[basepair_symbol]["bidQty"])
            rate_via_ask      = 1 / viabase_ask_price / xvia_ask_price * xbase_bid_price * (1 - fee)**3

            hope = 0

            # BUY->BUY->SELL
            if rate_via_bid > 1:
                row_via_bid = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    exchange_name,
                    base_currency_name + "->" + currency_name + "->" + via_currency_name + "->" + base_currency_name, str8(rate_via_bid),
                    basepair_symbol + ":BUY", str8(xbase_ask_price), str8(xbase_ask_lot), str8(xbase_ask_price * xbase_ask_lot),
                    viapair_symbol + ":SELL", str8(xvia_bid_price), str8(xvia_bid_lot), str8(xvia_bid_price * xvia_bid_lot * viabase_bid_price),
                    viabasepair_symbol + ":SELL", str8(viabase_bid_price), str8(viabase_bid_lot), str8(viabase_bid_price * viabase_bid_lot)
                ]
                self.log(row_via_bid, exchange_name)
                triangle_orders.extend([row_via_bid])
                hope += 1

            # BUY->SELL->SELL
            if rate_via_ask > 1:
                row_via_ask = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    exchange_name,
                    base_currency_name + "->" + via_currency_name + "->" + currency_name + "->" + base_currency_name, str8(rate_via_ask),
                    viabasepair_symbol + ":BUY", str8(viabase_ask_price), str8(viabase_ask_lot), str8(viabase_ask_price * viabase_ask_lot),
                    viapair_symbol + ":BUY", str8(xvia_ask_price), str8(xvia_ask_lot), str8(xvia_ask_price * xvia_ask_lot * viabase_ask_price),
                    basepair_symbol + ":SELL", str8(xbase_bid_price), str8(xbase_bid_lot), str8(xbase_bid_price * xbase_bid_lot)
                ]
                self.log(row_via_ask, exchange_name)
                triangle_orders.extend([row_via_ask])
                hope += 1
            return hope
        else:
            return -1

    def choice_order(self, triangle_orders):
        for triangle_order in triangle_orders:
            rate = float(triangle_order[3])
            if rate - 1 >= self.profit_lower_limit:
                return triangle_order
            else:
                print("Profits too small. rate=%s" % rate)
        return None

    def trade_binance(self, triangle_order, dryrun):
        start_t = datetime.now()
        mailer = Mailer()

        route = triangle_order[2]
        base_currency_name = route[:3]
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
            applog.info("Total must be at latest %f%s. (min_base_lot = %0.8f)" % (self.__get_lower_limit(base_currency_name, True), base_currency_name, min_base_lot))
            return

        if orders[1]["side"] == "SELL":
            # BUY->SELL->SELL
            orders[0]["final_lot"] = self.binance.lot_filter(orders[0]["lot"] * min_base_lot / orders[0]["base_lot"], orders[0]["symbol"], orders[1]["symbol"]) # target lot
            orders[1]["final_lot"] = orders[0]["final_lot"]                                                                                                     # target lot
            orders[2]["final_lot"] = self.binance.lot_filter(orders[1]["final_lot"] * orders[1]["price"],             orders[2]["symbol"])                      # via lot
        else:
            # BUY->BUY->SELL
            orders[0]["final_lot"] = self.binance.lot_filter(orders[0]["lot"] * min_base_lot / orders[0]["base_lot"], orders[0]["symbol"])                      # via lot
            orders[1]["final_lot"] = self.binance.lot_filter(orders[0]["final_lot"] / orders[1]["price"],             orders[1]["symbol"], orders[2]["symbol"]) # target lot
            orders[2]["final_lot"] = orders[1]["final_lot"]                                                                                                     # target lot

        via_lot = orders[1]["final_lot"] * orders[1]["price"]
        if via_lot < self.__get_lower_limit(via_currency_name, False):
            applog.info("Total must be at latest %f%s. (via_lot = %0.8f)" % (self.__get_lower_limit(via_currency_name, False), via_currency_name, via_lot))
            return

        expected_revenue = orders[2]["final_lot"] * orders[2]["price"] - orders[0]["final_lot"] * orders[0]["price"]
        expected_fee = (lambda x: x - x * (1 - self.binance.comission_fee)**3)(orders[0]["final_lot"] * orders[0]["price"])
        expected_final_revenue = expected_revenue - expected_fee

        if expected_final_revenue <= 0:
            applog.info("Round of error. expected_final_revenue = %0.8f", expected_final_revenue)

        msgs = [""]
        msgs.append("[beta] %d JPY" % ((expected_final_revenue) * 1000000))
        msgs.append("Expected Final Revenue:%0.8f%s" % (expected_final_revenue, base_currency_name))
        msgs.append("Expected fee:%0.8f%s" % (expected_fee, base_currency_name))
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
        msgs.append("")
        msgs.append("1st order:%s(%s), price:%0.8f, lot:%0.8f, base_lot:%0.8f, final_lot:%0.8f" % (orders[0]["symbol"], orders[0]["side"], orders[0]["price"], orders[0]["lot"], orders[0]["base_lot"], orders[0]["final_lot"]))
        msgs.append("2nd order:%s(%s), price:%0.8f, lot:%0.8f, base_lot:%0.8f, final_lot:%0.8f" % (orders[1]["symbol"], orders[1]["side"], orders[1]["price"], orders[1]["lot"], orders[1]["base_lot"], orders[1]["final_lot"]))
        msgs.append("3rd order:%s(%s), price:%0.8f, lot:%0.8f, base_lot:%0.8f, final_lot:%0.8f" % (orders[2]["symbol"], orders[2]["side"], orders[2]["price"], orders[2]["lot"], orders[2]["base_lot"], orders[2]["final_lot"]))

        for msg in msgs:
            applog.info(msg)

        mailer.sendmail("\n".join(msgs), "%s - Create order - Daryl Triangular" % route)

        if dryrun:
            return

        order_count = 0
        final_status = ""
        for order in orders:
            r = self.binance.order(
                order["symbol"],
                order["side"],
                binance.client.Client.ORDER_TYPE_LIMIT,
                binance.client.Client.TIME_IN_FORCE_GTC,
                order["final_lot"],
                "%0.8f" % order["price"],
            )
            applog.info("binance.create_order" + str(r))
            i = 0
            while True:
                try:
                    r = self.binance.get_order(r["symbol"], r["orderId"])
                except BinanceAPIException as e:
                    if e.status_code == -2013:   # NO_SUCH_ORDER
                        applog.info("BinanceAPIException: Order does not exist. (%d)" % i)
                        if i < 30:
                            time.sleep(0.001)
                        else:
                            time.sleep(10)
                        i += 1
                        continue

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
                            cancel_result = self.binance.cancel_order(r["symbol"], r["orderId"])
                            applog.info("Canceled. result=" + str(cancel_result))
                            mailer.sendmail("%s,%s" % (r["symbol"], r["orderId"]), "Canceled - Daryl Triangular")
                            final_status = "cancel"
                            break
                        time.sleep(0.01)
                    else:
                        time.sleep(10)
                    i += 1
                else:
                    # binance.client.Client.ORDER_STATUS_CANCELED
                    # binance.client.Client.ORDER_STATUS_EXPIRED
                    # binance.client.Client.ORDER_STATUS_PENDING_CANCEL
                    # binance.client.Client.ORDER_STATUS_REJECTED
                    if order_count == 0:
                        applog.warning("Skip triangular arbitrage. status=" + r["status"])
                        cancel_result = self.binance.cancel_order(r["symbol"], r["orderId"])
                        applog.info("Canceled. result=" + str(cancel_result))
                        mailer.sendmail("%s,%s" % (r["symbol"], r["orderId"]), "Canceled - Daryl Triangular")
                        final_status = "cancel"
                        break
                    else:
                        applog.error("Failed triangular arbitrage. status=" + r["status"])
                        mailer.sendmail("%s,%s" % (r["symbol"], r["orderId"]), "Failed - Daryl Triangular")
                        final_status = "failed"
                        break
            if final_status in ["cancel", "failed"]:
                break
        if order_count == 3:
            mailer.sendmail(route, "Successful - Daryl Triangular")
            final_status = "successful"
        self.trade_log(start_t, "Binance", route, expected_final_revenue, final_status)

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

    def trade_log(self, start_t, exchange, route, expected_final_revenue, final_status):
        row = [
            start_t.strftime("%Y-%m-%d %H:%M:%S"),
            exchange,
            route,
            str8(expected_final_revenue),
            final_status,
            str((datetime.now() - start_t).total_seconds()),
        ]
        with open(self.log_dir + "/" + exchange + "_trade.tsv", mode = 'a', encoding = 'utf-8') as fh:
            fh.write("\t".join(row) + '\n')

    def log(self, row, exchange):
        record = "\t".join(row)
        print(record)
        with open(self.__prepare_log_filepath(exchange + "_mon"), mode = 'a', encoding = 'utf-8') as fh:
            fh.write(record + '\n')

    def __prepare_dir(self, filepath):
        dir = os.path.dirname(filepath)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return filepath

    def __prepare_log_filepath(self, name):
        date = datetime.now().strftime("%Y-%m-%d")
        filepath = self.log_dir + "/" + name + "_" + date + ".tsv"
        return self.__prepare_dir(filepath)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in {"RealTrade", "DemoTrade", "Batch"}:
        run_mode = sys.argv[1]
    else:
        print("bad argument!")
        sys.exit()

    triangular = Triangular()
    triangular.run(run_mode, True, False)
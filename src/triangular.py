import time
from exchange import Binance
import json
from datetime import datetime


def str8(v):
    return str(round(v, 8))

class Triangular:
    def __init__(self, *args, **kwargs):
        self.binance = Binance()
        self.tsv_filepath = "./log/triangular.tsv"
        self.interval = 5

    def log(self, row):
        record = "\t".join(row)
        print(record)
        with open(self.tsv_filepath, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(record + '\n')

    def run(self):
        hash = {}
        while True:
            j = self.binance.refresh_ticker_all()

            for currency in j:
                hash[currency["symbol"]] = currency

            total = 0
            hope = 0

            for currency in j:
                r = self.triangle_all_check("BTC", "ETH", currency, hash)
                if r >=0:
                    total += 2
                    hope += r

                r = self.triangle_all_check("BTC", "BNB", currency, hash)
                if r >=0:
                    total += 2
                    hope += r

                r = self.triangle_all_check("ETH", "BNB", currency, hash)
                if r >=0:
                    total += 2
                    hope += r

            print("hope/total = " + str(hope) + "/" + str(total))
            time.sleep(self.interval)

    def triangle_all_check(self, base_currency_name, via_currency_name, currency, hash):
        i = currency["symbol"].find(via_currency_name)
        if not (i == -1 or i == 0):
            currency_name = currency["symbol"][0:len(currency["symbol"]) - 3]
            btcpair_symbol = currency_name + base_currency_name
            viapair_symbol = currency_name + via_currency_name
            viabtcpair_symbol = via_currency_name + base_currency_name
            if currency_name in ["BTC", "ETH", "BNB"]:
                return -1
            if viabtcpair_symbol in ["BTC", "ETH", "BNB"]:
                return -1

            xbtc_ask_price   = float(hash[btcpair_symbol]["askPrice"])    # Buy X at BTC
            xbtc_ask_lot     = float(hash[btcpair_symbol]["askQty"])
            xvia_bid_price   = float(hash[viapair_symbol]["bidPrice"])    # Buy (VIA) at X
            xvia_bid_lot     = float(hash[viapair_symbol]["bidQty"])
            viabtc_bid_price = float(hash[viabtcpair_symbol]["bidPrice"]) # Buy BTC at (VIA)
            viabtc_bid_lot   = float(hash[viabtcpair_symbol]["bidQty"])
            rate_via_bid     = 1 / xbtc_ask_price * xvia_bid_price * viabtc_bid_price * (1 - self.binance.comission_fee)**3

            viabtc_ask_price = float(hash[viabtcpair_symbol]["askPrice"]) # Buy (VIA) at BTC
            viabtc_ask_lot   = float(hash[viabtcpair_symbol]["askQty"])
            xvia_ask_price   = float(hash[viapair_symbol]["askPrice"])    # Buy X at (VIA)
            xvia_ask_lot     = float(hash[viapair_symbol]["askQty"])
            xbtc_bid_price   = float(hash[btcpair_symbol]["bidPrice"])    # Buy BTC at X
            xbtc_bid_lot     = float(hash[btcpair_symbol]["bidQty"])
            rate_via_ask     = 1 / viabtc_ask_price / xvia_ask_price * xbtc_bid_price * (1 - self.binance.comission_fee)**3

            hope = 0
            if rate_via_bid > 1:
                row_via_bid = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    base_currency_name + "->" + currency_name + "->" + via_currency_name + "->" + base_currency_name, str8(rate_via_bid),
                    btcpair_symbol + "(ask)", str8(xbtc_ask_price), str8(xbtc_ask_lot),
                    viapair_symbol + "(bid)", str8(xvia_bid_price), str8(xvia_bid_lot),
                    via_currency_name + "BTC(bid)", str8(viabtc_bid_price), str8(viabtc_bid_lot)
                ]
                self.log(row_via_bid)
                hope += 1
            if rate_via_ask > 1:
                row_via_ask = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    base_currency_name + "->" + via_currency_name + "->" + currency_name + "->" + base_currency_name, str8(rate_via_ask),
                    via_currency_name + "BTC(ask)", str8(viabtc_ask_price), str8(viabtc_ask_lot),
                    viapair_symbol + "(ask)", str8(xvia_ask_price), str8(xvia_ask_lot),
                    btcpair_symbol + "(bid)", str8(xbtc_bid_price), str8(xbtc_bid_lot)
                ]
                self.log(row_via_ask)
                hope += 1
            return hope
        else:
            return -1


if __name__ == '__main__':
    triangular = Triangular()
    triangular.run()
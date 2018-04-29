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

            xbtc_ask = float(hash[btcpair_symbol]["askPrice"])  # Buy X at BTC
            xvia_bid = float(hash[viapair_symbol]["bidPrice"])  # Buy (VIA) at X
            viabtc_bid = float(hash[viabtcpair_symbol]["bidPrice"])      # Buy BTC at (VIA)
            rate_via_bid = 1 / xbtc_ask * xvia_bid * viabtc_bid * (1 - self.binance.comission_fee)**3

            viabtc_ask = float(hash[viabtcpair_symbol]["askPrice"])      # Buy (VIA) at BTC
            xvia_ask = float(hash[viapair_symbol]["askPrice"])  # Buy X at (VIA)
            xbtc_bid = float(hash[btcpair_symbol]["bidPrice"])  # Buy BTC at X
            rate_via_ask = 1 / viabtc_ask / xvia_ask * xbtc_bid * (1 - self.binance.comission_fee)**3

            hope = 0
            if rate_via_bid > 1:
                row_via_bid = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    base_currency_name + "->" + currency_name + "->" + via_currency_name + "->" + base_currency_name, str8(rate_via_bid),
                    btcpair_symbol + "(ask)", str8(xbtc_ask),
                    viapair_symbol + "(bid)", str8(xvia_bid),
                    via_currency_name + "BTC(bid)", str8(viabtc_bid)
                ]
                self.log(row_via_bid)
                hope += 1
            if rate_via_ask > 1:
                row_via_ask = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    base_currency_name + "->" + via_currency_name + "->" + currency_name + "->" + base_currency_name, str8(rate_via_ask),
                    via_currency_name + "BTC(ask)", str8(viabtc_ask),
                    viapair_symbol + "(ask)", str8(xvia_ask),
                    btcpair_symbol + "(bid)", str8(xbtc_bid)
                ]
                self.log(row_via_ask)
                hope += 1
            return hope
        else:
            return -1


if __name__ == '__main__':
    triangular = Triangular()
    triangular.run()
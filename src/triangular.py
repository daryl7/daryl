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
                i = currency["symbol"].find("ETH")
                if not (i == -1 or i == 0):
                    currency_name = currency["symbol"][0:len(currency["symbol"]) - 3]
                    btcpair_symbol = currency_name + "BTC"
                    ethpair_symbol = currency_name + "ETH"

                    xbtc_ask = float(hash[btcpair_symbol]["askPrice"])  # Buy X at BTC
                    xeth_bid = float(hash[ethpair_symbol]["bidPrice"])  # Buy ETH at X
                    ethbtc_bid = float(hash["ETHBTC"]["bidPrice"])      # Buy BTC at ETH
                    rate_via_eth_bid = 1 / xbtc_ask * xeth_bid * ethbtc_bid * (1 - self.binance.comission_fee)**3

                    ethbtc_ask = float(hash["ETHBTC"]["askPrice"])      # Buy ETH at BTC
                    xeth_ask = float(hash[ethpair_symbol]["askPrice"])  # Buy X at ETH
                    xbtc_bid = float(hash[btcpair_symbol]["bidPrice"])  # Buy BTC at X
                    rate_via_eth_ask = 1 / ethbtc_ask / xeth_ask * xbtc_bid * (1 - self.binance.comission_fee)**3

                    total += 2
                    if rate_via_eth_bid > 1:
                        row_via_eth_bid = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "BTC->" + currency_name + "->ETH->BTC", str8(rate_via_eth_bid),
                            btcpair_symbol + "(ask)", str8(xbtc_ask),
                            ethpair_symbol + "(bid)", str8(xeth_bid),
                            "ETHBTC(bid)", str8(ethbtc_bid)
                        ]
                        self.log(row_via_eth_bid)
                        hope += 1
                    if rate_via_eth_ask > 1:
                        row_via_eth_ask = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "BTC->ETH->" + currency_name + "->BTC", str8(rate_via_eth_ask),
                            "ETHBTC(ask)", str8(ethbtc_ask),
                            ethpair_symbol + "(ask)", str8(xeth_ask),
                            btcpair_symbol + "(bid)", str8(xbtc_bid)
                        ]
                        self.log(row_via_eth_ask)
                        hope += 1

                i = currency["symbol"].find("BNB")
                if not (i == -1 or i == 0):
                    currency_name = currency["symbol"][0:len(currency["symbol"]) - 3]
                    btcpair_symbol = currency_name + "BTC"
                    bnbpair_symbol = currency_name + "BNB"

                    xbtc_ask = float(hash[btcpair_symbol]["askPrice"])  # Buy X at BTC
                    xbnb_bid = float(hash[bnbpair_symbol]["bidPrice"])  # Buy BNB at X
                    bnbbtc_bid = float(hash["BNBBTC"]["bidPrice"])      # Buy BTC at BNB
                    rate_via_bnb_bid = 1 / xbtc_ask * xbnb_bid * bnbbtc_bid * (1 - self.binance.comission_fee)**3

                    bnbbtc_ask = float(hash["BNBBTC"]["askPrice"])      # Buy BNB at BTC
                    xbnb_ask = float(hash[bnbpair_symbol]["askPrice"])  # Buy X at BNB
                    xbtc_bid = float(hash[btcpair_symbol]["bidPrice"])  # Buy BTC at X
                    rate_via_bnb_ask = 1 / bnbbtc_ask / xbnb_ask * xbtc_bid * (1 - self.binance.comission_fee)**3

                    total += 2
                    if rate_via_bnb_bid > 1:
                        row_via_bnb_bid = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "BTC->" + currency_name + "->BNB->BTC", str8(rate_via_bnb_bid),
                            btcpair_symbol + "(ask)", str8(xbtc_ask),
                            bnbpair_symbol + "(bid)", str8(xbnb_bid),
                            "BNBBTC(bid)", str8(bnbbtc_bid)
                        ]
                        self.log(row_via_bnb_bid)
                        hope += 1
                    if rate_via_bnb_ask > 1:
                        row_via_bnb_ask = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "BTC->BNB->" + currency_name + "->BTC", str8(rate_via_bnb_ask),
                            "BNBBTC(ask)", str8(bnbbtc_ask),
                            bnbpair_symbol + "(ask)", str8(xbnb_ask),
                            btcpair_symbol + "(bid)", str8(xbtc_bid)
                        ]
                        self.log(row_via_bnb_ask)
                        hope += 1

            print("hope/total = " + str(hope) + "/" + str(total))
            time.sleep(self.interval)


if __name__ == '__main__':
    triangular = Triangular()
    triangular.run()
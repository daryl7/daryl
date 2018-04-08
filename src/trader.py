import csv
import time
import os
import yaml
import monitor
from enum import IntEnum, auto
from monitor import Monitor
from exchange import BitFlyer, Binance

class CoinStatus(IntEnum):
    BitFlyer = auto()
    CoinCheck = auto()
    Binance = auto()

class Trader:
    def __init__(self, *args, **kwargs):
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            self.upper_limit = config['trader']['upper_limit']
            self.under_limit = config['trader']['under_limit']
            self.output_filename = './trade_timing.txt'

    def write_trade_timing(self, row):
        print(".")
        with open(self.output_filename, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(row + '\n')

    def inspect_backtradelog(self):
        tsv = csv.reader(open("results_BF_BN.txt", "r"), delimiter = '\t')
        if os.path.exists(self.output_filename):
            os.remove(self.output_filename)

        coin_status = CoinStatus.BitFlyer
        for row in tsv:
            diff = float(row[1])

            if coin_status == CoinStatus.BitFlyer and diff >= self.upper_limit:
                coin_status = CoinStatus.Binance
                self.write_trade_timing("\t".join(row))
            elif coin_status == CoinStatus.Binance and diff < self.under_limit:
                coin_status = CoinStatus.BitFlyer
                self.write_trade_timing("\t".join(row))

    def decision_and_order(self, monitor, buying_exchange_cls, selling_exchange_cls, dryrun):
        buying_exchange_cls.buy_order(dryrun)
        selling_exchange_cls.sell_order(dryrun)

    def trade(self, dryrun = True):
        coin_status = CoinStatus.BitFlyer
        mon = Monitor()
        while True:
            mon.refresh()

            if coin_status == CoinStatus.BitFlyer and mon.bf_bn_diff >= self.upper_limit:
                coin_status = CoinStatus.Binance
                self.decision_and_order(mon, BitFlyer, Binance, dryrun)
            elif coin_status == CoinStatus.Binance and mon.bf_bn_diff < self.under_limit:
                coin_status = CoinStatus.BitFlyer
                self.decision_and_order(mon, Binance, BitFlyer, dryrun)

            time.sleep(3)

if __name__ == '__main__':
    trader = Trader()
    trader.trade()


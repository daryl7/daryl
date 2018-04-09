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
            self.bf_bn_limit = config['trader']['bf_bn_limit']
            self.bn_bf_limit = config['trader']['bn_bf_limit']
            self.output_filename = './trade_timing.txt'

    def write_trade_timing(self, row):
        with open(self.output_filename, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(row + '\n')

    def decision_and_order(self, monitor, buying_exchange, selling_exchange, diff, dryrun):
        print(selling_exchange.__class__.__name__ + "->" + buying_exchange.__class__.__name__ + "(" + monitor.dt + ", diff:" + str(diff) + ")")
        buying_exchange.buy_order(dryrun)
        selling_exchange.sell_order(dryrun)

    def trade(self, dryrun = True):
        if os.path.exists(self.output_filename):
            os.remove(self.output_filename)

        coin_status = CoinStatus.BitFlyer
        mon = Monitor()
        # while True:
        tsv = csv.reader(open("results_BF_BN.txt", "r"), delimiter = '\t')
        for row in tsv:
            # mon.refresh()
            mon.dt = str(row[0])
            mon.bf_bn_diff = float(row[1])
            mon.bn_bf_diff = float(row[2])
            mon.bitflyer.bid = float(row[3])
            mon.bitflyer.ask = float(row[4])
            mon.binance.bid = float(row[5])
            mon.binance.ask = float(row[6])

            # skip when invalid value
            if mon.bitflyer.ask < mon.bitflyer.bid or mon.binance.ask < mon.binance.bid:
                continue

            if coin_status == CoinStatus.BitFlyer and mon.bf_bn_diff >= self.bf_bn_limit:
                coin_status = CoinStatus.Binance
                self.decision_and_order(mon, mon.binance, mon.bitflyer, mon.bf_bn_diff, dryrun)
                self.write_trade_timing("\t".join(row))
            elif coin_status == CoinStatus.Binance and mon.bn_bf_diff >= self.bn_bf_limit:
                coin_status = CoinStatus.BitFlyer
                self.decision_and_order(mon, mon.bitflyer, mon.binance, mon.bn_bf_diff, dryrun)
                self.write_trade_timing("\t".join(row))

            #time.sleep(3)

if __name__ == '__main__':
    trader = Trader()
    trader.trade(False)

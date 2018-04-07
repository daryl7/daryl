import csv
import time
import os
import yaml
from enum import IntEnum, auto

class CoinStatus(IntEnum):
    BitFlyer = auto()
    CoinCheck = auto()

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

    def main(self):
        tsv = csv.reader(open("results_BF_BN.txt", "r"), delimiter = '\t')
        if os.path.exists(self.output_filename):
            os.remove(self.output_filename)

        coin_status = CoinStatus.BitFlyer
        for row in tsv:
            diff = float(row[1])

            if coin_status == CoinStatus.BitFlyer and diff >= self.upper_limit:
                coin_status = CoinStatus.CoinCheck
                self.write_trade_timing("\t".join(row))
            elif coin_status == CoinStatus.CoinCheck and diff < self.under_limit:
                coin_status = CoinStatus.BitFlyer
                self.write_trade_timing("\t".join(row))


if __name__ == '__main__':
    trader = Trader()
    trader.main()


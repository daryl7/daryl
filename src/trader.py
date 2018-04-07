import csv
import time
import os
from enum import IntEnum, auto

output_filename = './trade_timing.txt'
upper_limit = 7000
under_limit = 3000

class CoinStatus(IntEnum):
    BitFlyer = auto()
    CoinCheck = auto()

tsv = csv.reader(open("results_BF_BN.txt", "r"), delimiter = '\t')
if os.path.exists(output_filename):
    os.remove(output_filename)

coin_status = CoinStatus.BitFlyer

def write_trade_timing(row):
    print(".")
    with open(output_filename, mode = 'a', encoding = 'utf-8') as fh:
        fh.write(row + '\n')

for row in tsv:
    diff = float(row[1])

    if coin_status == CoinStatus.BitFlyer and diff >= upper_limit:
        coin_status = CoinStatus.CoinCheck
        write_trade_timing("\t".join(row))
    elif coin_status == CoinStatus.CoinCheck and diff < under_limit:
        coin_status = CoinStatus.BitFlyer
        write_trade_timing("\t".join(row))

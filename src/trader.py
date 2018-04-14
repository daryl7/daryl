import csv
import time
import os
import yaml
import monitor
from enum import IntEnum, auto
from monitor import Monitor
from exchange import BitFlyer, Binance, Context
import smtplib
from email.mime.text import MIMEText
import sys

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
            self.trade_log_full_filepath = './log/trade_full.log'
            self.trade_log_filepath = './log/trade.log'

    def write_trade_timing(self, row):
        with open(self.output_filename, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(row + '\n')
        with open(self.trade_log_full_filepath, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(row + '\n')
        with open(self.trade_log_filepath, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(row + '\n')

    def order(self, monitor, buying_exchange, selling_exchange, diff, dryrun):
        message1 = selling_exchange.__class__.__name__ + "->" + buying_exchange.__class__.__name__ + "(" + monitor.dt + ", diff:" + str(diff) + ")"
        message2 = buying_exchange.buy_order(dryrun)
        message3 = selling_exchange.sell_order(dryrun)
        print(message1)
        print(message2)
        print(message3)
        with open(self.trade_log_full_filepath, mode = 'a', encoding = 'utf-8') as fh:
            fh.write(message1 + '\n')
            fh.write(message2 + '\n')
            fh.write(message3 + '\n')
        Context.set_coin_status(buying_exchange.__class__.__name__)

        with open('config.yml', 'r') as yml:
           config = yaml.load(yml)
        if not config['notifycation']['email']['to'] == "":
            you = config['notifycation']['email']['to']
            me = config['notifycation']['email']['from']
            msg = MIMEText(message1 + "\n" + message2 + "\n" + message3)
            msg['Subject'] = config['notifycation']['email']['subject']
            msg['To'] = you
            msg['From'] = me
            s = smtplib.SMTP()
            s.connect()
            s.sendmail(me, [you], msg.as_string())
            s.close()

    def decision_and_order(self, coin_status, mon, dryrun):
        # skip when invalid value
        if mon.bitflyer.ask < mon.bitflyer.bid or mon.binance.ask < mon.binance.bid:
            return coin_status

        row = [mon.dt, str(mon.bf_bn_diff), str(mon.bn_bf_diff), str(mon.bitflyer.bid), str(mon.bitflyer.ask), str(mon.binance.bid), str(mon.binance.ask), str(mon.usdjpy)]
        if coin_status == CoinStatus.BitFlyer and mon.bf_bn_diff >= self.bf_bn_limit:
            coin_status = CoinStatus.Binance
            self.order(mon, mon.binance, mon.bitflyer, mon.bf_bn_diff, dryrun)
            self.write_trade_timing("\t".join(row))
        elif coin_status == CoinStatus.Binance and mon.bn_bf_diff >= self.bn_bf_limit:
            coin_status = CoinStatus.BitFlyer
            self.order(mon, mon.bitflyer, mon.binance, mon.bn_bf_diff, dryrun)
            self.write_trade_timing("\t".join(row))
        return coin_status

    def trade(self, run_mode):
        if os.path.exists(self.output_filename):
            os.remove(self.output_filename)

        if run_mode == "RealTrade":
            dryrun = False
        else:
            dryrun = True

        coin_status = CoinStatus.BitFlyer if Context.get_coin_status() == "BitFlyer" else CoinStatus.Binance
        mon = Monitor()

        if run_mode == "Batch":
            tsv = csv.reader(open("results_BF_BN.txt", "r"), delimiter = '\t')
            for row in tsv:
                mon.dt = str(row[0])
                mon.bf_bn_diff = float(row[1])
                mon.bn_bf_diff = float(row[2])
                mon.bitflyer.bid = float(row[3])
                mon.bitflyer.ask = float(row[4])
                mon.binance.bid = float(row[5])
                mon.binance.ask = float(row[6])
                mon.usdjpy = float(row[7])
                coin_status = self.decision_and_order(coin_status, mon, dryrun)
        else:
            while True:
                mon.refresh()
                coin_status = self.decision_and_order(coin_status, mon, dryrun)
                time.sleep(3)

if __name__ == '__main__':

    if len(sys.argv) > 1 and sys.argv[1] in {"ReadTrade", "DemoTrade", "Batch"}:
        run_mode = sys.argv[1]
    else:
        print("bad argument!")
        sys.exit()

    trader = Trader()
    trader.trade(run_mode)

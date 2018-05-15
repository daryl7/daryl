import csv
import time
import os
import yaml
import monitor
from enum import IntEnum, auto
from monitor import Monitor
from exchange import BitFlyer, Binance
import smtplib
from email.mime.text import MIMEText
import sys
import applog
from config import Config
import traceback
from mailer import Mailer


class CoinStatus:
    BitFlyer = "BitFlyer"
    Binance = "Binance"


class LogFiles:
    batch_output_filename = './trade_simulation.tsv'
    trade_log_full_filepath = './log/trade_full.log'


class Trader:
    def __init__(self, *args, **kwargs):
        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            self.order_offset_jpy = config['trader']['order_offset_jpy']
            self.order_offset_usd = config['trader']['order_offset_usd']
        self.load_positions()

    def trade(self, run_mode):
        if os.path.exists(LogFiles.batch_output_filename):
            os.remove(LogFiles.batch_output_filename)

        mailer = Mailer()
        if mailer.is_use():
            if not mailer.checkmailer():
                applog.error("mailer not activation!")
                sys.exit()

        if run_mode == "RealTrade":
            dryrun = False
        else:
            dryrun = True

        mon = Monitor()

        applog.info("========================================")
        applog.info("Start Trader. RunMode = " + run_mode)
        applog.info("binance.comission_fee: " + str(mon.binance.comission_fee))
        applog.info("order_offset_jpy = " + str(self.order_offset_jpy))
        applog.info("order_offset_usd = " + str(self.order_offset_usd))
        applog.info("notification_email_to = " + mailer.notification_email_to)
        applog.info("notification_email_from = " + mailer.notification_email_from)
        applog.info("notification_email_subject = " + mailer.notification_email_subject)
        applog.info("========================================")

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
                for position in self.positions:
                    position.decision_and_order(mon, dryrun)
        else:
            try:
                while True:
                    mon.refresh()
                    if mon.validation_check():
                        execution = False
                        for position in self.positions:
                            if position.decision_and_order(mon, dryrun):
                                execution = True
                        if execution:
                            self.save_positions()
                    time.sleep(3)
            except Exception as e:
                applog.error(traceback.format_exc())
                mailer.sendmail(traceback.format_exc())

    def load_positions(self):
        self.positions = []
        with open('positions.yml', 'r') as yml:
            yml_positions = yaml.load(yml)
        for hash in yml_positions:
            self.positions.append(Position(hash))

    def save_positions(self):
        yml_positions = []
        for position in self.positions:
            yml_positions.append(position.hash)
        with open('positions.yml', 'w') as yml:
            yml.write(yaml.dump(yml_positions, default_flow_style=False))


class Position:
    def __init__(self, hash):
        self.hash = hash

    def decision_and_order(self, mon, dryrun):
        execution = False
        row = [mon.dt, str(mon.bf_bn_diff), str(mon.bn_bf_diff), str(mon.bitflyer.bid), str(mon.bitflyer.ask), str(mon.binance.bid), str(mon.binance.ask), str(mon.usdjpy)]
        if self.hash["coin_status"] == CoinStatus.BitFlyer and mon.bf_bn_diff >= self.hash["bf_bn_limit"]:
            if mon.health_check(dryrun):
                execution = True
                message1 = "BitFlyer->Binance(" + mon.dt + ", diff:" + str(mon.bf_bn_diff) + ")"
                message2 = mon.bitflyer.sell_order_from_available_balance(self.hash["asset"]["bitflyer"]["btc"], dryrun)
                message3 = mon.binance.buy_order_from_available_balance(self.hash["asset"]["binance"]["usd"], dryrun)
                row.extend([
                    "SELL",
                    str(mon.bitflyer.last_sell_price),
                    str(mon.bitflyer.last_sell_lot),
                    str(mon.bitflyer.last_sell_commission),
                    "BUY",
                    str(mon.binance.last_buy_price),
                    str(mon.binance.last_buy_lot),
                    str(mon.binance.last_buy_comission)
                ])
                self.exchange_bitflyer(mon.bitflyer.last_sell_price, False)
                self.exchange_binance(mon.binance.last_buy_price, True)
                self.hash["coin_status"] = CoinStatus.Binance
        elif self.hash["coin_status"] == CoinStatus.Binance and mon.bn_bf_diff >= self.hash["bn_bf_limit"]:
            if mon.health_check(dryrun):
                execution = True
                message1 = "Binance->BitFlyer(" + mon.dt + ", diff:" + str(mon.bn_bf_diff) + ")"
                message2 = mon.bitflyer.buy_order_from_available_balance(self.hash["asset"]["bitflyer"]["jpy"], dryrun)
                message3 = mon.binance.sell_order_from_available_balance(self.hash["asset"]["binance"]["btc"], dryrun)
                row.extend([
                    "BUY",
                    str(mon.bitflyer.last_buy_price),
                    str(mon.bitflyer.last_buy_lot),
                    str(mon.bitflyer.last_buy_commission),
                    "SELL",
                    str(mon.binance.last_sell_price),
                    str(mon.binance.last_sell_lot),
                    str(mon.binance.last_sell_comission)
                ])
                self.exchange_bitflyer(mon.bitflyer.last_buy_price, True)
                self.exchange_binance(mon.binance.last_sell_price, False)
                self.hash["coin_status"] = CoinStatus.BitFlyer

        if execution:
            self.trade_log(row, self.hash["_label"])

            applog.info(message1)
            applog.info(message2)
            applog.info(message3)
            with open(LogFiles.trade_log_full_filepath, mode = 'a', encoding = 'utf-8') as fh:
                fh.write('\n'.join(["", message1, message2, message3, ""]))

            mailer = Mailer()
            if mailer.is_use():
                mailer.sendmail(message1 + "\n" + message2 + "\n" + message3)

        return execution

    def trade_log(self, row, label):
        record = "\t".join(row)
        files = [
            LogFiles.batch_output_filename,
            LogFiles.trade_log_full_filepath,
            "./log/trade(%s).tsv" % label,
        ]
        for file in files:
            with open(file, mode = 'a', encoding = 'utf-8') as fh:
                fh.write(record + '\n')

    def exchange_bitflyer(self, price, is_to_btc):
        asset = self.hash["asset"]
        if(is_to_btc):
            assert not float(asset['bitflyer']['jpy']) == 0.0, "bitflyer jpy is 0"
            asset['bitflyer']['btc'] = round(float(asset['bitflyer']['jpy']) / float(price), 8)
            asset['bitflyer']['jpy'] = 0.0
        else:
            assert not float(asset['bitflyer']['btc']) == 0.0, "bitflyer btc is 0"
            asset['bitflyer']['jpy'] = float(asset['bitflyer']['btc']) * price
            asset['bitflyer']['btc'] = 0.0

    def exchange_binance(self, price, is_to_btc):
        asset = self.hash["asset"]
        if(is_to_btc):
            assert not float(asset['binance']['usd']) == 0.0, "binance usd is 0"
            asset['binance']['btc'] = round(float(asset['binance']['usd']) / float(price), 6)
            asset['binance']['usd'] = 0.0
        else:
            assert not float(asset['binance']['btc']) == 0.0, "binance btc is 0"
            asset['binance']['usd'] = float(asset['binance']['btc']) * price
            asset['binance']['btc'] = 0.0


if __name__ == '__main__':
    applog.init(Config.get_log_dir() + "/app.log",)

    if len(sys.argv) > 1 and sys.argv[1] in {"RealTrade", "DemoTrade", "Batch"}:
        run_mode = sys.argv[1]
    else:
        applog.error("bad argument!")
        sys.exit()

    trader = Trader()
    trader.trade(run_mode)

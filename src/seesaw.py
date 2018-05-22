import time
import os
import glob
import yaml
import exchange
from exchange import LegalTender
import smtplib
from email.mime.text import MIMEText
import sys
import applog
from config import Config
import traceback
from mailer import Mailer
from datetime import datetime


class LogFiles:
    batch_output_filename = './trade_simulation.tsv'
    trade_log_full_filepath = './log/trade_full.log'


class Seesaw:
    def __init__(self, rule):
        self.rule = rule

        r = rule.split("_")
        target_currency = r[0]
        base_currency = r[1]
        self.exchange1 = getattr(exchange, r[2])(target_currency, base_currency)
        self.exchange2 = getattr(exchange, r[3])(target_currency, base_currency)
        self.context_filepath = "./context/seesaw/" + rule + ".yml"
        self.load_positions()

        self.legal_tender = LegalTender()

        with open('config.yml', 'r') as yml:
            config = yaml.load(yml)
            self.order_offset_jpy = config['trader']['order_offset_jpy']
            self.order_offset_usd = config['trader']['order_offset_usd']

    def trade(self, run_mode):
        mailer = Mailer()
        if mailer.is_use():
            if not mailer.checkmailer():
                applog.error("mailer not activation!")
                sys.exit()

        dryrun = False if run_mode == "RealTrade" else True

        applog.info("========================================")
        applog.info("Start Trader. RunMode = " + run_mode)
        applog.info("order_offset_jpy = " + str(self.order_offset_jpy))
        applog.info("order_offset_usd = " + str(self.order_offset_usd))
        applog.info("notification_email_to = " + mailer.notification_email_to)
        applog.info("notification_email_from = " + mailer.notification_email_from)
        applog.info("notification_email_subject = " + mailer.notification_email_subject)
        applog.info("========================================")

        try:
            while True:
                if self.refresh():
                    if self.validation_check():
                        execution = False
                        for position in self.positions:
                            if position.decision_and_order(self, dryrun):
                                execution = True
                        if execution:
                            self.save_positions()
                time.sleep(3)
        except Exception as e:
            applog.error(traceback.format_exc())
            mailer.sendmail(traceback.format_exc())

    def refresh(self, limit_second = 3):
        start_t = datetime.now()
        self.dt = start_t.strftime("%Y-%m-%d %H:%M:%S")

        self.exchange1.refresh_ticker()
        if not self.exchange1.validation_check(True):
            return False

        self.exchange2.refresh_ticker()
        if not self.exchange2.validation_check(True):
            return False

        if (datetime.now() - start_t).total_seconds() > limit_second:
            applog.warning("Network is to busy. Total seconds = %d" % (datetime.now() - start_t).total_seconds())
            return False

        if self.exchange1.get_base_currency() == "JPY":
            self.usdjpy = self.legal_tender.get_rate_of_usdjpy()
            ex1_bid_jpy, ex1_ask_jpy = self.exchange1.to_jpy(self.usdjpy)
            ex2_bid_jpy, ex2_ask_jpy = self.exchange2.to_jpy(self.usdjpy)
            self.diff_ex1_ex2 = int(ex1_bid_jpy - ex2_ask_jpy)
            self.diff_ex2_ex1 = int(ex2_bid_jpy - ex1_ask_jpy)
            res = '\t'.join([self.dt, str(self.diff_ex1_ex2), str(self.diff_ex2_ex1), str(self.exchange1.bid), str(self.exchange1.ask), str(self.exchange2.bid), str(self.exchange2.ask), str(self.usdjpy)])
        else:
            self.diff_ex1_ex2 = self.exchange1.bid - self.exchange2.ask
            self.diff_ex2_ex1 = self.exchange2.bid - self.exchange1.ask
            res = '\t'.join([self.dt, str(self.diff_ex1_ex2), str(self.diff_ex2_ex1), str(self.exchange1.bid), str(self.exchange1.ask), str(self.exchange2.bid), str(self.exchange2.ask)])
        print(res)

        with open(self.__prepare_log_filepath(self.rule), mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

        return True

    def validation_check(self):
        return self.exchange1.validation_check() and self.exchange2.validation_check()

    def health_check(self, dryrun):
        return self.exchange1.health_check(dryrun) and self.exchange2.health_check(dryrun)

    def load_positions(self):
        self.positions = []
        with open(self.context_filepath, 'r') as yml:
            yml_positions = yaml.load(yml)
        for hash in yml_positions:
            self.positions.append(Position(hash))

    def save_positions(self):
        yml_positions = []
        for position in self.positions:
            yml_positions.append(position.hash)
        with open(self.context_filepath, 'w') as yml:
            yml.write(yaml.dump(yml_positions, default_flow_style=False))

    def __prepare_log_filepath(self, name):
        date = datetime.now().strftime("%Y-%m-%d")
        filepath = "./log/seesaw/monitor/" + name + "_" + date + ".tsv"
        dir = os.path.dirname(filepath)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return filepath


class Position:
    def __init__(self, hash):
        self.hash = hash

    def decision_and_order(self, seesaw, dryrun):
        execution = False
        pair = self.hash["pair"]
        row = [seesaw.dt, str(seesaw.diff_ex1_ex2), str(seesaw.diff_ex2_ex1), str(seesaw.exchange1.bid), str(seesaw.exchange1.ask), str(seesaw.exchange2.bid), str(seesaw.exchange2.ask), str(seesaw.usdjpy)]
        if self.hash["coin_status"] == seesaw.exchange1.get_name() and seesaw.diff_ex1_ex2 >= pair[seesaw.exchange1.get_name()]["limit_diff_other_one"]:
            if seesaw.health_check(dryrun):
                execution = True
                message1 = "%s->%s(%s, diff:%0.8f)" % (seesaw.exchange1.get_name(), seesaw.exchange2.get_name(), seesaw.dt, seesaw.diff_ex1_ex2)
                message2 = seesaw.exchange1.sell_order_from_available_balance(pair[seesaw.exchange1.get_name()]["balance"][seesaw.exchange1.get_target_currency()], dryrun)
                message3 = seesaw.exchange2.buy_order_from_available_balance(pair[seesaw.exchange2.get_name()]["balance"][seesaw.exchange2.get_base_currency()], dryrun)
                row.extend([
                    "SELL",
                    str(seesaw.exchange1.last_sell_price),
                    str(seesaw.exchange1.last_sell_lot),
                    str(seesaw.exchange1.last_sell_commission),
                    "BUY",
                    str(seesaw.exchange2.last_buy_price),
                    str(seesaw.exchange2.last_buy_lot),
                    str(seesaw.exchange2.last_buy_comission)
                ])
                self.exchange_balance(seesaw.exchange1, "SELL")
                self.exchange_balance(seesaw.exchange2, "BUY")
                self.hash["coin_status"] = seesaw.exchange2.get_name()
        elif self.hash["coin_status"] == seesaw.exchange2.get_name() and seesaw.diff_ex2_ex1 >= pair[seesaw.exchange2.get_name()]["limit_diff_other_one"]:
            if seesaw.health_check(dryrun):
                execution = True
                message1 = "%s->%s(%s, diff:%0.8f)" % (seesaw.exchange2.get_name(), seesaw.exchange1.get_name(), seesaw.dt, seesaw.diff_ex2_ex1)
                message2 = seesaw.exchange1.buy_order_from_available_balance(pair[seesaw.exchange1.get_name()]["balance"][seesaw.exchange1.get_base_currency()], dryrun)
                message3 = seesaw.exchange2.sell_order_from_available_balance(pair[seesaw.exchange2.get_name()]["balance"][seesaw.exchange2.get_target_currency()], dryrun)
                row.extend([
                    "BUY",
                    str(seesaw.exchange1.last_buy_price),
                    str(seesaw.exchange1.last_buy_lot),
                    str(seesaw.exchange1.last_buy_commission),
                    "SELL",
                    str(seesaw.exchange2.last_sell_price),
                    str(seesaw.exchange2.last_sell_lot),
                    str(seesaw.exchange2.last_sell_comission)
                ])
                self.exchange_balance(seesaw.exchange1, "BUY")
                self.exchange_balance(seesaw.exchange2, "SELL")
                self.hash["coin_status"] = seesaw.exchange1.get_name()

        if execution:
            self.trade_log(row, self.hash["_position"])

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

    def exchange_balance(self, exchange, side):
        pair = self.hash["pair"]
        if(side == "BUY"):
            assert not float(pair[exchange.get_name()]["balance"][exchange.get_base_currency()]) == 0.0, "base_currency is 0"
            pair[exchange.get_name()]["balance"][exchange.get_target_currency()] = round(float(pair[exchange.get_name()]["balance"][exchange.get_base_currency()]) / float(exchange.last_buy_price), 8)
            pair[exchange.get_name()]["balance"][exchange.get_base_currency()] = 0.0
        else:
            assert not float(pair[exchange.get_name()]["balance"][exchange.get_target_currency()]) == 0.0, "target_currency is 0"
            pair[exchange.get_name()]["balance"][exchange.get_base_currency()] = float(pair[exchange.get_name()]["balance"][exchange.get_target_currency()]) * exchange.last_sell_price
            pair[exchange.get_name()]["balance"][exchange.get_target_currency()] = 0.0


if __name__ == '__main__':
    applog.init(Config.get_log_dir() + "/app.log",)

    if len(sys.argv) > 2 and sys.argv[1] in {"RealTrade", "DemoTrade", "Batch"}:
        run_mode = sys.argv[1]
        rule = sys.argv[2]
    else:
        applog.error("bad argument!")
        sys.exit()

    seesaw = Seesaw(rule)
    seesaw.trade(run_mode)
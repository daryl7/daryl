"""Usage:
    seesaw.py <run_mode> <rule> [--echo] [--interval <second>]
    seesaw.py -h | --help

Options:
    --echo                   Echo refresh message to stdout.
    --interval <second>      Monitoring Interval.
    -h --help                Show this screen and exit.
"""

from docopt import docopt
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
    def __init__(self, rule, is_echo, interval):
        self.rule = rule
        self.is_echo = is_echo
        self.interval = 3 if interval is None else int(interval)

        r = rule.split("_")
        target_currency = r[0]
        base_currency = r[1]
        self.exchange1 = getattr(exchange, r[2])(target_currency, base_currency)
        self.exchange2 = getattr(exchange, r[3])(target_currency, base_currency)
        self.context_filepath = "./context/seesaw/" + rule + ".yml"
        self.lock_filepath = "./context/seesaw/" + rule + ".lock"
        self.load_positions()

        self.legal_tender = LegalTender()

    def trade(self, run_mode):
        if self.is_lock():
            applog.error("locked")
            raise Exception

        mailer = Mailer()
        if mailer.is_use():
            if not mailer.checkmailer():
                applog.error("mailer not activation!")
                sys.exit()

        dryrun = False if run_mode == "RealTrade" else True

        applog.info("========================================")
        applog.info("Start Trader. RunMode = " + run_mode)
        applog.info("Start Trader. Interval = " + str(self.interval))
        applog.info("notification_email_to = " + mailer.notification_email_to)
        applog.info("notification_email_from = " + mailer.notification_email_from)
        for position in self.positions:
            applog.info(position.hash)
        applog.info("========================================")

        try:
            while True:
                if self.refresh():
                    if self.validation_check():
                        execution = False
                        for position in self.positions:
                            try:
                                if position.decision_and_order(self, dryrun):
                                    execution = True
                            except Exception as e:
                                trace_msg = traceback.format_exc()
                                self.lock(trace_msg)
                                applog.error(trace_msg)
                                mailer.sendmail(traceback.format_exc(), "Critical Assertion - Daryl Trade - %s" % self.rule)
                                sys.exit()
                        if execution:
                            self.save_positions()
                time.sleep(self.interval)
        except Exception as e:
            applog.error(traceback.format_exc())
            mailer.sendmail(traceback.format_exc(), "Assertion - Daryl Trade - %s" % self.rule)

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
            self.usdjpy = 0
            self.diff_ex1_ex2 = self.exchange1.bid - self.exchange2.ask
            self.diff_ex2_ex1 = self.exchange2.bid - self.exchange1.ask
            res = '\t'.join([self.dt, str8(self.diff_ex1_ex2), str8(self.diff_ex2_ex1), str8(self.exchange1.bid), str8(self.exchange1.ask), str8(self.exchange2.bid), str8(self.exchange2.ask)])

        if self.is_echo:
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

    def lock(self, message):
        with open(self.lock_filepath, 'w') as yml:
            yml.write(message)

    def is_lock(self):
        return os.path.exists(self.lock_filepath)

    def __prepare_log_filepath(self, name):
        date = datetime.now().strftime("%Y-%m-%d")
        filepath = "./log/seesaw/monitor/" + name + "_" + date + ".tsv"
        dir = os.path.dirname(filepath)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return filepath


class Position:
    __reach_max_count = 2

    def __init__(self, hash):
        self.hash = hash
        self.reach = 0

    def decision_and_order(self, seesaw, dryrun):
        execution = False
        pair = self.hash["pair"]
        row = [seesaw.dt, str(seesaw.diff_ex1_ex2), str(seesaw.diff_ex2_ex1), str(seesaw.exchange1.bid), str(seesaw.exchange1.ask), str(seesaw.exchange2.bid), str(seesaw.exchange2.ask), str(seesaw.usdjpy)]
        if self.hash["coin_status"] == seesaw.exchange1.get_name() and seesaw.diff_ex1_ex2 >= pair[seesaw.exchange1.get_name()]["limit_diff_other_one"]:
            self.reach += 1
            applog.info("Reach position(%s). Count is %d." % (self.hash["_position"], self.reach))
            if seesaw.health_check(dryrun) and self.reach >= self.__reach_max_count:
                execution = True
                self.reach = 0
                message1 = "%s->%s(%s, diff:%0.8f)" % (seesaw.exchange1.get_name(), seesaw.exchange2.get_name(), seesaw.dt, seesaw.diff_ex1_ex2)
                message2 = seesaw.exchange1.sell_order_from_available_balance(
                    pair[seesaw.exchange1.get_name()]["balance"][seesaw.exchange1.get_target_currency()],
                    pair[seesaw.exchange1.get_name()]["price_tension"],
                    dryrun
                )
                message3 = seesaw.exchange2.buy_order_from_available_balance(
                    pair[seesaw.exchange2.get_name()]["balance"][seesaw.exchange2.get_base_currency()],
                    pair[seesaw.exchange2.get_name()]["price_tension"],
                    dryrun
                )
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
            self.reach += 1
            applog.info("Reach position(%s). Count is %d." % (self.hash["_position"], self.reach))
            if seesaw.health_check(dryrun) and self.reach >= self.__reach_max_count:
                execution = True
                self.reach = 0
                message1 = "%s->%s(%s, diff:%0.8f)" % (seesaw.exchange2.get_name(), seesaw.exchange1.get_name(), seesaw.dt, seesaw.diff_ex2_ex1)
                message2 = seesaw.exchange1.buy_order_from_available_balance(
                    pair[seesaw.exchange1.get_name()]["balance"][seesaw.exchange1.get_base_currency()],
                    pair[seesaw.exchange1.get_name()]["price_tension"],
                    dryrun
                )
                message3 = seesaw.exchange2.sell_order_from_available_balance(
                    pair[seesaw.exchange2.get_name()]["balance"][seesaw.exchange2.get_target_currency()],
                    pair[seesaw.exchange2.get_name()]["price_tension"],
                    dryrun
                )
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
                mailer.sendmail(message1 + "\n" + message2 + "\n" + message3, "Daryl Trade - %s" % seesaw.rule)

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


def str8(v):
    return "%0.8f" % v


if __name__ == '__main__':
    args = docopt(__doc__)

    rule = args["<rule>"]

    applog.init(Config.get_log_dir() + "/seesaw/%s.log" % rule)

    run_mode = args["<run_mode>"]
    if not run_mode in {"RealTrade", "DemoTrade"}:
        applog.error("bad argument!")
        sys.exit()

    seesaw = Seesaw(rule, args["--echo"], args["--interval"])
    seesaw.trade(run_mode)

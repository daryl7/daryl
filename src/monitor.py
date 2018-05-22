from exchange import BitFlyer, CoinCheck, Binance, LegalTender
from datetime import datetime
import time
import os
import applog


class Monitor:
    def __init__(self, log_dir = "./log"):
        self.bitflyer = BitFlyer()
        self.binance = Binance()
        self.legal_tender = LegalTender()
        self.log_dir = log_dir

    def __prepare_log_filepath(self, name):
        date = datetime.now().strftime("%Y-%m-%d")
        filepath = self.log_dir + "/" + name + "_" + date + ".tsv"
        dir = os.path.dirname(filepath)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return filepath

    def refresh(self, limit_second = 3):
        start_t = datetime.now()
        self.dt = start_t.strftime("%Y-%m-%d %H:%M:%S")

        self.bitflyer = BitFlyer()
        self.bitflyer.refresh_ticker()
        if not self.bitflyer.validation_check(True):
            return False
        bf_bid = self.bitflyer.bid
        bf_ask = self.bitflyer.ask

        self.coincheck = CoinCheck()
        self.coincheck.refresh_ticker()
        cc_bid = self.coincheck.bid
        cc_ask = self.coincheck.ask

        self.bf_cc_diff = bf_bid - cc_ask
        self.cc_bf_diff = cc_bid - bf_ask
        res = '\t'.join([self.dt, str(self.bf_cc_diff), str(self.cc_bf_diff), str(bf_bid), str(bf_ask), str(cc_bid), str(cc_ask)])
        with open(self.__prepare_log_filepath('monitor_BTCJPY_BF_CC/monitor_BTCJPY_BF_CC'), mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

        self.usdjpy = self.legal_tender.get_rate_of_usdjpy()

        self.binance = Binance()
        self.binance.refresh_ticker()
        if not self.binance.validation_check(True):
            return False
        if (datetime.now() - start_t).total_seconds() > limit_second:
            applog.warning("Network is to busy. Total seconds = %d" % (datetime.now() - start_t).total_seconds())
            return False
        bn_bid_usd = self.binance.bid
        bn_ask_usd = self.binance.ask
        bn_bid_jpy = int(float(bn_bid_usd) * self.usdjpy)
        bn_ask_jpy = int(float(bn_ask_usd) * self.usdjpy)
        self.bf_bn_diff = bf_bid - bn_ask_jpy
        self.bn_bf_diff = bn_bid_jpy - bf_ask
        res = '\t'.join([self.dt, str(self.bf_bn_diff), str(self.bn_bf_diff), str(bf_bid), str(bf_ask), str(bn_bid_usd), str(bn_ask_usd), str(self.usdjpy)])
        print(res)
        with open(self.__prepare_log_filepath('monitor_BTCJPY_BF_BN/monitor_BTCJPY_BF_BN'), mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

        return True

    def validation_check(self):
        return self.bitflyer.validation_check() and self.binance.validation_check()

    def health_check(self, dryrun):
        return self.bitflyer.health_check(dryrun) and self.binance.health_check(dryrun)

def monitor_test_mode():
    mon = Monitor()
    while True:
        mon.refresh()
        time.sleep(3)

if __name__ == '__main__':
    monitor_test_mode()

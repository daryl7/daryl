from exchange import BitFlyer, CoinCheck, Binance, LegalTender
import datetime
import time

class Monitor:
    def __init__(self, *args, **kwargs):
        self.bitflyer = BitFlyer()
        self.binance = Binance()

    def refresh(self):
        self.dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.bitflyer = BitFlyer()
        self.bitflyer.refresh_ticker()
        bf_bid = self.bitflyer.bid
        bf_ask = self.bitflyer.ask

        self.coincheck = CoinCheck()
        self.coincheck.refresh_ticker()
        cc_bid = self.coincheck.bid
        cc_ask = self.coincheck.ask

        self.bf_cc_diff = bf_ask - cc_bid
        self.cc_bf_diff = cc_ask - bf_bid
        res = '\t'.join([self.dt, str(self.bf_cc_diff), str(self.cc_bf_diff), str(bf_bid), str(bf_ask), str(cc_bid), str(cc_ask)])
        # print(res)
        with open('results_BF_CC.txt', mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

        usdjpy = LegalTender.get_rate_of_usdjpy()

        self.binance = Binance()
        self.binance.refresh_ticker()
        bn_bid_usd = self.binance.bid
        bn_ask_usd = self.binance.ask
        bn_bid_jpy = int(float(bn_bid_usd) * usdjpy)
        bn_ask_jpy = int(float(bn_ask_usd) * usdjpy)
        self.bf_bn_diff = bf_ask - bn_bid_jpy
        self.bn_bf_diff = bn_ask_jpy - bf_bid
        res = '\t'.join([self.dt, str(self.bf_bn_diff), str(self.bn_bf_diff), str(bf_bid), str(bf_ask), str(bn_bid_usd), str(bn_ask_usd), str(usdjpy)])
        print(res)
        with open('results_BF_BN.txt', mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

def monitor_test_mode():
    mon = Monitor()
    while True:
        mon.refresh()
        time.sleep(3)

if __name__ == '__main__':
    monitor_test_mode()

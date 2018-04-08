from exchange import BitFlyer, CoinCheck, Binance, LegalTender
import datetime
import time

class Monitor:
    def refresh(self):
        self.dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.bf_bid = BitFlyer.get_bid()
        self.bf_ask = BitFlyer.get_ask()
        self.cc_bid = CoinCheck.get_bid()
        self.cc_ask = CoinCheck.get_ask()
        self.bf_cc_diff = self.bf_bid - self.cc_bid
        res = '\t'.join([self.dt, str(self.bf_cc_diff), str(self.bf_bid), str(self.cc_bid), str(self.bf_ask), str(self.cc_ask)])
        # print(res)
        with open('results_BF_CC.txt', mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

        self.usdjpy = LegalTender.get_rate_of_usdjpy()
        self.bn_bid_usd = Binance.get_bid()
        self.bn_ask_usd = Binance.get_ask()
        self.bn_bid_jpy = int(float(self.bn_bid_usd) * self.usdjpy)
        self.bn_ask_jpy = int(float(self.bn_ask_usd) * self.usdjpy)
        self.bf_bn_diff = self.bf_bid - self.bn_bid_jpy
        res = '\t'.join([self.dt, str(self.bf_bn_diff), str(self.bf_bid), str(self.bf_ask), str(self.bn_bid_usd), str(self.bn_ask_usd), str(self.usdjpy)])
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

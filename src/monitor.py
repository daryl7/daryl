# -*- coding:utf-8 -*-

import json
import time
import hmac
import hashlib
import urllib.request
import json
import sys
import datetime
import yaml

with open('config.yml', 'r') as yml:
    config = yaml.load(yml)

bitflyer_api_key = config['bitflyer']['api_key']
bitflyer_api_secret = config['bitflyer']['api_secret']

def fetch_url(req, max_times=100, sleep_sec=10):
    retry_count = 0
    while True:
        if retry_count > max_times:
            print("fetch_url error")
            break

        try:
            retry_count += 1
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as err:
            print("HTTPError:" + str(err.code) + ":" + req.get_full_url())
            time.sleep(sleep_sec)
        except urllib.error.URLError as err:
            print("URLError:" + str(err.reason) + ":" + req.get_full_url())
            time.sleep(sleep_sec)

class BitFlyer:
    __api_endpoint = 'https://api.bitflyer.jp'
    def urlopen(method, path, *, param={}):
        timestamp = str(time.time())
        text = timestamp + method + path
        sign = hmac.new(bytes(bitflyer_api_secret.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()

        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'ACCESS-KEY': bitflyer_api_key,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-SIGN': sign,
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=BitFlyer.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def urlopen_public(method, path, *, param={}):
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=BitFlyer.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def get_bid():
        with BitFlyer.urlopen_public("GET", "/v1/ticker", param = {"product_code":"BTC_JPY"}) as res:
            html = res.read().decode("utf-8")
            v = int(json.loads(html)["best_bid"])
        return v

    def get_ask():
        with BitFlyer.urlopen_public("GET", "/v1/ticker", param = {"product_code":"BTC_JPY"}) as res:
            html = res.read().decode("utf-8")
            v = int(json.loads(html)["best_ask"])
        return v


class CoinCheck:
    __api_endpoint = "https://coincheck.com"
    def urlopen(method, path, *, param={}):
        timestamp = str(time.time())
        headers = {
            'ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=CoinCheck.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def get_bid():
        with CoinCheck.urlopen("GET", "/api/ticker") as res:
            html = res.read().decode("utf-8")
            v = int(json.loads(html)["bid"])
        return v

    def get_ask():
        with CoinCheck.urlopen("GET", "/api/ticker") as res:
            html = res.read().decode("utf-8")
            v = int(json.loads(html)["ask"])
        return v

class Binance:
    __api_endpoint = "https://api.binance.com"
    def urlopen(method, path, *, param={}):
        timestamp = str(time.time())
        headers = {
            'ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=Binance.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def get_bid():
        with Binance.urlopen("GET", "/api/v3/ticker/bookTicker", param = {"symbol":"BTCUSDT"}) as res:
            html = res.read().decode("utf-8")
            v = float(json.loads(html)["bidPrice"])
        return v

    def get_ask():
        with Binance.urlopen("GET", "/api/v3/ticker/bookTicker", param = {"symbol":"BTCUSDT"}) as res:
            html = res.read().decode("utf-8")
            v = float(json.loads(html)["askPrice"])
        return v

class LegalTender:
    def get_rate_of_usdjpy():
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'ACCESS-TIMESTAMP': str(time.time()),
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url="https://www.gaitameonline.com/rateaj/getrate", headers=headers)
        with fetch_url(req) as res:
            html = res.read().decode("utf-8")
            v = float(json.loads(html)['quotes'][20]['ask'])
        return v

# with BitFlyer.urlopen("GET", "/v1/me/getpermissions") as res:
#     html = res.read().decode("utf-8")
#     open("permissions.json","w").write(html)
#     print(json.loads(html))
# sys.exit()

def monitor():
    while True:
        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        bf_bid = BitFlyer.get_bid()
        bf_ask = BitFlyer.get_ask()
        cc_bid = CoinCheck.get_bid()
        cc_ask = CoinCheck.get_ask()
        res = '\t'.join([dt, str(bf_bid - cc_bid), str(bf_bid), str(cc_bid), str(bf_ask), str(cc_ask)])
        # print(res)
        with open('results_BF_CC.txt', mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

        usdjpy = LegalTender.get_rate_of_usdjpy()
        bn_bid_usd = Binance.get_bid()
        bn_ask_usd = Binance.get_ask()
        bn_bid_jpy = int(float(bn_bid_usd) * usdjpy)
        bn_ask_jpy = int(float(bn_ask_usd) * usdjpy)

        res = '\t'.join([dt, str(bf_bid - bn_bid_jpy), str(bf_bid), str(bf_ask), str(bn_bid_usd), str(bn_ask_usd), str(usdjpy)])
        print(res)
        with open('results_BF_BN.txt', mode = 'a', encoding = 'utf-8') as fh:
            fh.write(res + '\n')

        time.sleep(3)

if __name__ == '__main__':
    monitor()

import json
import time
import hmac
import hashlib
import urllib.request
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


class Context:
    @staticmethod
    def exchange_bitflyer(price, is_to_btc):
        with open('context.yml', 'r') as yml:
            context = yaml.load(yml)

        if(is_to_btc):
            assert not float(context['asset']['bitflyer']['jpy']) == 0.0, "bitflyer jpy is 0"
            context['asset']['bitflyer']['btc'] = float(context['asset']['bitflyer']['jpy']) / float(price)
            context['asset']['bitflyer']['jpy'] = 0.0
        else:
            assert not float(context['asset']['bitflyer']['btc']) == 0.0, "bitflyer btc is 0"
            context['asset']['bitflyer']['jpy'] = float(context['asset']['bitflyer']['btc']) * price
            context['asset']['bitflyer']['btc'] = 0.0

        with open('context.yml', 'w') as yml:
            yml.write(yaml.dump(context, default_flow_style=False))

    @staticmethod
    def get_bitflyer_btc():
        with open('context.yml', 'r') as yml:
            context = yaml.load(yml)
        return float(context['asset']['bitflyer']['btc'])

    @staticmethod
    def get_bitflyer_jpy():
        with open('context.yml', 'r') as yml:
            context = yaml.load(yml)
        return float(context['asset']['bitflyer']['jpy'])

    @staticmethod
    def exchange_binance(price, is_to_btc):
        with open('context.yml', 'r') as yml:
            context = yaml.load(yml)

        if(is_to_btc):
            assert not float(context['asset']['binance']['usd']) == 0.0, "binance usd is 0"
            context['asset']['binance']['btc'] = float(context['asset']['binance']['usd']) / float(price)
            context['asset']['binance']['usd'] = 0.0
        else:
            assert not float(context['asset']['binance']['btc']) == 0.0, "binance btc is 0"
            context['asset']['binance']['usd'] = float(context['asset']['binance']['usd']) * price
            context['asset']['binance']['btc'] = 0.0

        with open('context.yml', 'w') as yml:
            yml.write(yaml.dump(context, default_flow_style=False))

    @staticmethod
    def get_binance_btc():
        with open('context.yml', 'r') as yml:
            context = yaml.load(yml)
        return float(context['asset']['binance']['btc'])

    @staticmethod
    def get_binance_usd():
        with open('context.yml', 'r') as yml:
            context = yaml.load(yml)
        return float(context['asset']['binance']['usd'])


class BitFlyer:
    __api_endpoint = 'https://api.bitflyer.jp'
    @staticmethod
    def __urlopen(method, path, *, param=None, data={}):
        paramtext = ""
        body = ""
        if method == "POST":
            body = json.dumps(data)
        else:
            if(param):
                paramtext = "?" + urllib.parse.urlencode(param)

        timestamp = str(time.time())
        text = timestamp + method + path + body
        sign = hmac.new(bytes(bitflyer_api_secret.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()

        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'ACCESS-KEY': bitflyer_api_key,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-SIGN': sign,
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=BitFlyer.__api_endpoint + path + paramtext, data=json.dumps(data).encode("utf-8"), headers=headers)
        return fetch_url(req)

    @staticmethod
    def __urlopen_public(method, path, *, param={}):
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=BitFlyer.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def refresh_ticker(self):
        with BitFlyer.__urlopen_public("GET", "/v1/ticker", param = {"product_code":"BTC_JPY"}) as res:
            html = res.read().decode("utf-8")
            self.bid = int(json.loads(html)["best_bid"])
            self.ask = int(json.loads(html)["best_ask"])

    def buy_order(self, dryrun):
        print("\tbuy_order: BitFlyer, " + str(self.ask + config['trader']['order_offset_jpy']))
        price = self.ask + config['trader']['order_offset_jpy']
        if(not dryrun):
            body = {
                "product_code": "BTC_JPY",
                "child_order_type": "LIMIT",
                "side": "BUY",
                "price": price,
                "size": Context.get_bitflyer_btc()
            }
            with BitFlyer.__urlopen("POST", "/v1/me/sendchildorder", data = body) as res:
                html = res.read().decode("utf-8")
                print(json.loads(html))
        Context.exchange_bitflyer(price, True)

    def sell_order(self, dryrun):
        print("\tsell_order: BitFlyer, " + str(self.bid - config['trader']['order_offset_jpy']))
        price = self.bid - config['trader']['order_offset_jpy']
        if(not dryrun):
            body = {
                "product_code": "BTC_JPY",
                "child_order_type": "LIMIT",
                "side": "SELL",
                # todo
                #"price": price,
                #"size": Context.get_bitflyer_jpy() / float(price)
                "price": 1000000,
                "size": 0.1
            }
            with BitFlyer.__urlopen("POST", "/v1/me/sendchildorder", data = body) as res:
                html = res.read().decode("utf-8")
                print(json.loads(html))
        Context.exchange_bitflyer(price, False)


class CoinCheck:
    __api_endpoint = "https://coincheck.com"

    @staticmethod
    def __urlopen(method, path, *, param={}):
        timestamp = str(time.time())
        headers = {
            'ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=CoinCheck.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def refresh_ticker(self):
        with CoinCheck.__urlopen("GET", "/api/ticker") as res:
            html = res.read().decode("utf-8")
            self.bid = int(json.loads(html)["bid"])
            self.ask = int(json.loads(html)["ask"])


class Binance:
    __api_endpoint = "https://api.binance.com"

    @staticmethod
    def __urlopen(method, path, *, param={}):
        timestamp = str(time.time())
        headers = {
            'ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=Binance.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def refresh_ticker(self):
        with Binance.__urlopen("GET", "/api/v3/ticker/bookTicker", param = {"symbol":"BTCUSDT"}) as res:
            html = res.read().decode("utf-8")
            self.bid = float(json.loads(html)["bidPrice"])
            self.ask = float(json.loads(html)["askPrice"])

    def buy_order(self, dryrun):
        print("\tbuy_order: Binance, " + str(self.ask + config['trader']['order_offset_usd']))
        price = self.ask + config['trader']['order_offset_usd']
        if(not dryrun):
            print("todo")
        Context.exchange_binance(price, True)

    def sell_order(self, dryrun):
        print("\tsell_order: Binance, " + str(self.bid - config['trader']['order_offset_usd']))
        price = self.bid - config['trader']['order_offset_usd'])
        if(not dryrun):
            print("todo")
        Context.exchange_binance(price, False)


class LegalTender:
    @staticmethod
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

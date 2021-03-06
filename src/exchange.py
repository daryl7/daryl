import json
import time
import hmac
import hashlib
import urllib.request
import http
import sys
import datetime
import yaml
import binance.client
import applog
import traceback

with open('config.yml', 'r') as yml:
    config = yaml.load(yml)

bitflyer_api_key = config['bitflyer']['api_key']
bitflyer_api_secret = config['bitflyer']['api_secret']

def fetch_url(req, max_times=100, sleep_sec=10):
    retry_count = 0
    while True:
        if retry_count > max_times:
            applog.error("fetch_url error")
            break

        try:
            retry_count += 1
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as err:
            applog.warning("HTTPError(retry):" + str(err.code) + ":" + req.get_full_url())
        except urllib.error.URLError as err:
            applog.warning("URLError(retry):" + str(err.reason) + ":" + req.get_full_url())
        except http.client.RemoteDisconnected as err:
            applog.warning("RemoteDisconnected(retry):" + req.get_full_url())
        except http.client.BadStatusLine as err:
            applog.warning("BadStatusLine(retry):" + req.get_full_url())
        time.sleep(sleep_sec)


class Exchange:
    def __init__(self, target_currency, base_currency):
        self.ask = 0
        self.bid = 0
        self.symbol = target_currency + "_" + self.get_legal() if base_currency == "LEGAL" else target_currency + "_" + base_currency

    def validation_check(self, is_log = False):
        if self.ask == 0 or self.bid == 0 or self.ask < self.bid:
            if is_log:
                applog.warning("validation error at %s: ask = %0.8f, bid = %0.8f" % (self.__class__.__name__, self.ask, self.bid))
            return False
        return True

    def web_symbol(self):
        return self.symbol

    def get_name(self):
        return self.__class__.__name__

    def get_target_currency(self):
        return self.symbol.split("_")[0]

    def get_base_currency(self):
        return self.symbol.split("_")[1]

    def get_legal(self):
        raise "need override"

    def to_jpy(self, usdjpy):
        raise "need override"

    def refresh_ticker(self):
        raise "need override"

    def health_check(self, dryrun):
        raise "need override"

    def buy_order_from_available_balance(self, legal_lot, price_tension, dryrun):
        raise "need override"

    def sell_order_from_available_balance(self, lot, price_tension, dryrun):
        raise "need override"


class BitFlyer(Exchange):
    __api_endpoint = 'https://api.bitflyer.jp'

    def __init__(self, target_currency, base_currency):
        super(BitFlyer, self).__init__(target_currency, base_currency)

    def get_legal(self):
        return "JPY"

    def to_jpy(self, usdjpy):
        return self.bid, self.ask

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
        text = timestamp + method + path + paramtext + body
        applog.info(text)
        sign = hmac.new(bytes(bitflyer_api_secret.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()

        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'ACCESS-KEY': bitflyer_api_key,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-SIGN': sign,
            'Content-Type': 'application/json'
        }
        if method == "POST":
            req = urllib.request.Request(url=BitFlyer.__api_endpoint + path + paramtext, data=json.dumps(data).encode("utf-8"), headers=headers)
        else:
            req = urllib.request.Request(url=BitFlyer.__api_endpoint + path + paramtext, headers=headers)
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
        with BitFlyer.__urlopen_public("GET", "/v1/ticker", param = {"product_code":self.web_symbol()}) as res:
            html = res.read().decode("utf-8")
            self.bid = int(json.loads(html)["best_bid"])
            self.ask = int(json.loads(html)["best_ask"])

    def health_check(self, dryrun):
        if dryrun:
            return True

        with BitFlyer.__urlopen_public("GET", "/v1/getboardstate") as res:
            html = res.read().decode("utf-8")
        j = json.loads(html)
        if j["state"] == "RUNNING" and j["health"] in ["NORMAL", "BUSY", "VERY BUSY"]:
            applog.info("Bitflyer API status:" + j["state"] + ", health:" + j["health"])
            return True
        else:
            applog.warning("Bitflyer API has problem.")
            applog.warning("state:" + j["state"] + ", health:" + j["health"])
            applog.warning("watch:https://lightning.bitflyer.jp/docs?lang=ja&_ga=2.27791676.1496421283.1524886778-454668974.1522570784#%E6%9D%BF%E3%81%AE%E7%8A%B6%E6%85%8B")
            return False

    def order(self, body):
        with BitFlyer.__urlopen("POST", "/v1/me/sendchildorder", data = body) as res:
            html = res.read().decode("utf-8")
            applog.info(html)
            child_order_acceptance_id = json.loads(html)["child_order_acceptance_id"]

        retry_count = 0
        while True:
            if retry_count > 3:
                assert("failed order")

            time.sleep(3)
            retry_count += 1
            with BitFlyer.__urlopen("GET", "/v1/me/getchildorders", param = {"child_order_acceptance_id":child_order_acceptance_id}) as res:
                html = res.read().decode("utf-8")
                if len(json.loads(html)) > 0:
                    applog.info(html)
                    commission = json.loads(html)[0]["total_commission"]
                    break
        return [child_order_acceptance_id, commission]

    def buy_order_from_available_balance(self, jpy, price_tension, dryrun):
        price = self.ask + price_tension
        lot = round(jpy / float(price), 8)
        if not dryrun:
            body = {
                "product_code": "BTC_JPY",
                "child_order_type": "LIMIT",
                "side": "BUY",
                "price": price,
                "size": lot
            }
            r = self.order(body)
            child_order_acceptance_id = r[0]
            commission = r[1]
        else:
            child_order_acceptance_id = "demo"
            commission = round(lot * 0.0015,8)
        self.last_buy_price = price
        self.last_buy_lot = lot
        self.last_buy_commission = commission
        return "\tbuy_order:BitFlyer, price:" + str(price) + ", lot:" + str(lot) + ", commission:" + str(commission) + ", child_order_acceptance_id:" + child_order_acceptance_id

    def sell_order_from_available_balance(self, lot, price_tension, dryrun):
        price = self.bid - price_tension
        if not dryrun:
            body = {
                "product_code": "BTC_JPY",
                "child_order_type": "LIMIT",
                "side": "SELL",
                "price": price,
                "size": lot
            }
            r = self.order(body)
            child_order_acceptance_id = r[0]
            commission = r[1]
        else:
            child_order_acceptance_id = "demo"
            commission = round(lot * 0.0015,8)
        self.last_sell_price = price
        self.last_sell_lot = lot
        self.last_sell_commission = commission
        return "\tsell_order:BitFlyer, price:" + str(price) + ", lot:" + str(lot) + ", commission:" + str(commission) + ", child_order_acceptance_id:" + child_order_acceptance_id


class CoinCheck(Exchange):
    __api_endpoint = "https://coincheck.com"

    def __init__(self):
        super(CoinCheck, self).__init__()

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


class Binance(Exchange):
    __api_endpoint = "https://api.binance.com"

    def __init__(self, target_currency, base_currency):
        super(Binance, self).__init__(target_currency, base_currency)
        self.client = binance.client.Client(config['binance']['api_key'], config['binance']['api_secret'])
        self.comission_fee = config['binance']['comission_fee']
        self.all_ticker_hash = {}
        self.exchange_info_hash = {}

    def web_symbol(self):
        r = self.symbol.split("_")
        return r[0] + r[1]

    def get_legal(self):
        return "USDT"

    def to_jpy(self, usdjpy):
        return self.bid * usdjpy, self.ask * usdjpy

    @staticmethod
    def __urlopen_public(method, path, *, param={}):
        timestamp = str(time.time())
        headers = {
            'ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=Binance.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def refresh_ticker(self):
        with Binance.__urlopen_public("GET", "/api/v3/ticker/bookTicker", param = {"symbol":self.web_symbol()}) as res:
            html = res.read().decode("utf-8")
            self.bid = float(json.loads(html)["bidPrice"])
            self.ask = float(json.loads(html)["askPrice"])

    def refresh_ticker_all(self):
        with Binance.__urlopen_public("GET", "/api/v3/ticker/bookTicker") as res:
            html = res.read().decode("utf-8")
        j = json.loads(html)
        for currency in j:
            self.all_ticker_hash[currency["symbol"]] = currency
        return self.all_ticker_hash

    def refresh_exchange_info(self):
        with Binance.__urlopen_public("GET", "/api/v1/exchangeInfo") as res:
            html = res.read().decode("utf-8")
        j = json.loads(html)
        self.exchange_info_hash = {}
        for symbol in j["symbols"]:
            filters = {}
            for filter in symbol["filters"]:
                filters[filter["filterType"]] = filter
            symbol["filters"] = filters
            self.exchange_info_hash[symbol["symbol"]] = symbol

    def depth(self, symbol, limit = 10):
        with Binance.__urlopen_public("GET", "/api/v1/depth", param = {"symbol":symbol, "limit":limit}) as res:
            html = res.read().decode("utf-8")
        return json.loads(html)

    def lot_filter(self, lot, symbol1, symbol2 = ""):
        if symbol2 == "":
            minQty = float(self.exchange_info_hash[symbol1]["filters"]["LOT_SIZE"]["minQty"])
            return lot - lot % minQty
        else:
            minQty1 = float(self.exchange_info_hash[symbol1]["filters"]["LOT_SIZE"]["minQty"])
            minQty2 = float(self.exchange_info_hash[symbol2]["filters"]["LOT_SIZE"]["minQty"])
            return lot - lot % max(minQty1, minQty2)

    def get_tick_size(self, symbol):
        return float(self.exchange_info_hash[symbol]["filters"]["PRICE_FILTER"]["tickSize"])

    def health_check(self, dryrun):
        # TODO: implement
        return True

    def buy_order_from_available_balance(self, usd, price_tension, dryrun):
        price = self.ask + price_tension
        lot = round(usd / float(price), 6)
        if(not dryrun):
            order = self.client.create_order(
                symbol = 'BTCUSDT',
                side = binance.client.Client.SIDE_BUY,
                type = binance.client.Client.ORDER_TYPE_LIMIT,
                timeInForce = binance.client.Client.TIME_IN_FORCE_GTC,
                quantity = lot,
                price = price )
        self.last_buy_price = price
        self.last_buy_lot = lot
        self.last_buy_comission = round(lot * self.comission_fee, 8)
        return "\tbuy_order: Binance, " + str(price) + ", " + str(lot)

    def sell_order_from_available_balance(self, lot, price_tension, dryrun):
        price = self.bid - price_tension
        lot = round(lot, 6)
        if(not dryrun):
            order = self.client.create_order(
                symbol = 'BTCUSDT',
                side = binance.client.Client.SIDE_SELL,
                type = binance.client.Client.ORDER_TYPE_LIMIT,
                timeInForce = binance.client.Client.TIME_IN_FORCE_GTC,
                quantity = lot,
                price = price )
        self.last_sell_price = price
        self.last_sell_lot = lot
        self.last_sell_comission = round(lot * self.comission_fee, 8)
        return "\tsell_order: Binance, " + str(price) + ", " + str(lot)

    def order(self, symbol, side, _type, time_in_force, lot, price):
        return self.client.create_order(
            symbol = symbol,
            side = side,
            type = _type,
            timeInForce = time_in_force,
            quantity = lot,
            price = price,
        )

    def get_order(self, symbol, order_id):
        return self.client.get_order(symbol = symbol, orderId = order_id)

    def cancel_order(self, symbol, order_id):
        return self.client.cancel_order(symbol = symbol, orderId = order_id)


class Poloniex(Exchange):
    __api_endpoint = "https://poloniex.com"

    def __init__(self, target_currency, base_currency):
        super(Poloniex, self).__init__(target_currency, base_currency)

    def web_symbol(self):
        r = self.symbol.split("_")
        return r[1] + "_" + r[0]

    @staticmethod
    def __urlopen_public(method, path, *, param={}):
        headers = {
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=Poloniex.__api_endpoint + path + "?" + urllib.parse.urlencode(param), headers=headers)
        return fetch_url(req)

    def refresh_ticker_all(self):
        with Poloniex.__urlopen_public("GET", "/public", param = {"command":"returnTicker"}) as res:
            html = res.read().decode("utf-8")
            return json.loads(html)

    def get_legal(self):
        return "USDT"

    def to_jpy(self, usdjpy):
        return self.bid * usdjpy, self.ask * usdjpy

    def refresh_ticker(self):
        ticker = self.refresh_ticker_all()[self.web_symbol()]
        self.bid = float(ticker["highestBid"])
        self.ask = float(ticker["lowestAsk"])

    def health_check(self, dryrun):
        # TODO: implement
        return True

    def buy_order_from_available_balance(self, legal_lot, price_tension, dryrun):
        raise "need override"

    def sell_order_from_available_balance(self, lot, price_tension, dryrun):
        raise "need override"


class LegalTender:
    def __init__(self):
        self.last_v = -1

    def get_rate_of_usdjpy(self):
        url = "https://www.gaitameonline.com/rateaj/getrate"
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
            'ACCESS-TIMESTAMP': str(time.time()),
            'Content-Type': 'application/json'
        }
        req = urllib.request.Request(url=url, headers=headers)

        with fetch_url(req) as res:
            html = res.read().decode("utf-8")

            try:
                table = json.loads(html)['quotes'][20]
                if table['currencyPairCode'] == "USDJPY":
                    v = float(table['ask'])
                else:
                    applog.warning("Results is broken. currencyPairCode: " + table["currencyPairCode"] + ", Use last value:" + str(self.last_v) + " url: " + url)
                    v = self.last_v
            except (IndexError, KeyError) as e:
                applog.warning(e)
                applog.warning("Failed LegalTender. Use last value:" + str(self.last_v))
                applog.warning("html = " + html)
                v = self.last_v

        if v < 0:
            raise Exception

        self.last_v = v
        return v

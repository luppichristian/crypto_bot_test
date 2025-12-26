from pybit.unified_trading import HTTP
from datetime import datetime, timezone
from pytrends.request import TrendReq
from config import *
from enum import Enum
import yfinance as yf
import logging
import functools
import time
import requests
import math

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# =======================================================
# Setup Bybit Trading Session
# =======================================================

session = HTTP(
    testnet=True,
    api_key=api_keys["BYBIT_API_KEY"],
    api_secret=api_keys["BYBIT_API_SECRET"]
)

# =======================================================
# Helper Functions
# =======================================================

def retry_on_exception(max_retries=3, delay=2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logging.warning(f"Retry {attempt+1}/{max_retries} after error: {e}")
                    time.sleep(delay)
            logging.error(f"❌ Max retries reached for {func.__name__}")
            return None
        return wrapper
    return decorator

# =======================================================
# Price analysis functions
# =======================================================

def get_price_for_symbol(symbol):
    try:
        price_data = session.get_tickers(category="linear", symbol=symbol)
        return float(price_data['result']['list'][0]['indexPrice'])
    except Exception as e:
        logging.error(f"❌ Error fetching price for {symbol}: {e}")
        return None

def get_volatility_for_symbol_24hr(symbol):
    try:
        ticker = session.get_tickers(category="linear", symbol=symbol)
        change_24h = float(ticker['result']['list'][0]['price24hPcnt']) * 100
        return change_24h
    except Exception as e:
        logging.error(f"❌ Failed to fetch 24h change from Bybit: {e}")
        return 2.0

def get_price_history(symbol, limit=120, interval="D"):
    """
    Returns a list of dicts: {"time": timestamp, "price": price}
    interval: "D" (daily), "W" (weekly), "M" (monthly)
    """
    try:
        res = session.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        candles = res['result']['list']
        return [
            {
                "time": int(k[0]) // 1000.0,  # ms to s
                "price": float(k[4])
            }
            for k in candles
        ]
    except Exception as e:
        logging.error(f"❌ Failed to fetch price history for {symbol}: {e}")
        return []

# =======================================================
# CoinMarketCap API Functions
# =======================================================

@retry_on_exception(max_retries=3, delay=2)
def safe_cmc_request(url):
    headers = {"X-CMC_PRO_API_KEY": api_keys["CMC_API_KEY"]}
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error(f"❌ CMC request failed: {e}")
        return None

def get_btc_dominance():
    r = safe_cmc_request("https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest")
    return r["data"]["btc_dominance"] if r else None

def get_fear_and_greed_index():
    r = safe_cmc_request("https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest")
    return r["data"]["value"] if r else None

# =======================================================
# CryptoPanic Sentiment Analysis
# =======================================================

def get_cryptopanic_sentiment():
    """Fetch latest news from CryptoPanic and return sentiment score (-1=negative, 0=neutral, 1=positive)."""
    if not api_keys["CRYPTOPANIC_API_KEY"]:
        logging.warning("⚠️ No CryptoPanic API key set. Skipping news sentiment.")
        return 0
    params = {
        "auth_token": api_keys["CRYPTOPANIC_API_KEY"],
        "currencies": f"{config["INVESTED_SYMBOL"]},{config["LIQUIDITY_SYMBOL"]}",
        "filter": "hot",
        "public": "true"
    }
    try:
        r = requests.get("https://cryptopanic.com/api/v1/posts/", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        posts = data.get("results", [])
        sentiment = 0
        count = 0
        for post in posts:
            vote = post.get("vote", {})
            if vote.get("positive"):
                sentiment += 1
                count += 1
            elif vote.get("negative"):
                sentiment -= 1
                count += 1
        if count == 0:
            return 0
        avg_sentiment = sentiment / count
        if avg_sentiment > 0.2:
            return 1
        elif avg_sentiment < -0.2:
            return -1
        else:
            return 0
    except Exception as e:
        logging.error(f"❌ Error fetching CryptoPanic news: {e}")
        return 0

# =======================================================
# Bitcoin halving
# =======================================================

def get_halving_info():
    url = "https://api.blockchain.info/q/getblockcount"
    response = requests.get(url)
    current_block = int(response.text)

    halving_interval = 210000
    next_halving_block = ((current_block // halving_interval) + 1) * halving_interval
    blocks_remaining = next_halving_block - current_block

    # Assume 10 minutes per block
    minutes_remaining = blocks_remaining * 10
    days_remaining = minutes_remaining / (60 * 24)

    last_halving_block = next_halving_block - halving_interval
    blocks_since_last = current_block - last_halving_block
    minutes_since_last = blocks_since_last * 10
    days_since_last = minutes_since_last / (60 * 24)

    return {
        "current_block": current_block,
        "next_halving_block": next_halving_block,
        "blocks_remaining": blocks_remaining,
        "days_until_next_halving": round(days_remaining, 2),
        "days_since_last_halving": round(days_since_last, 2)
    }

# =======================================================
# Google Trends
# =======================================================

def get_today_google_search(symbol):
    pytrends = TrendReq(hl='en-US', tz=360)

    kw_list = [symbol]
    pytrends.build_payload(kw_list, cat=0, timeframe='all', geo='', gprop='') 

    data = pytrends.interest_over_time()

    if data.empty or symbol not in data.columns:
        print(f"No search data found for symbol: {symbol}")
        return None

    # Get the last available data point (typically the most recent)
    latest_value = data[symbol].iloc[-1]
    return int(latest_value)

# =======================================================
# Rainbow Bitcoin
# =======================================================

class RainbowColor(Enum):
    MAX_BUBBLE_TERRITORY = 1
    SELL_PLEASE = 2
    FOMO_INTENSIFIES = 3
    IS_THIS_A_BUBBLE = 4
    HODL = 5
    STILL_CHEAP = 6
    ACCUMULATE = 7
    BUY = 8
    BASICALLY_FIRE_SALE = 9

def get_bitcoin_rainbow_band():
    url = "https://openapiv1.coinstats.app/insights/rainbow-chart/bitcoin"
    headers = {
        "accept": "application/json",
        "X-API-KEY": api_keys["COINSTATS_API_KEY"]
    }

    rainbow_bands = [
        (RainbowColor.MAX_BUBBLE_TERRITORY, 7.0),
        (RainbowColor.SELL_PLEASE, 5.0),
        (RainbowColor.FOMO_INTENSIFIES, 3.0),
        (RainbowColor.IS_THIS_A_BUBBLE, 2.0),
        (RainbowColor.HODL, 1.0),
        (RainbowColor.STILL_CHEAP, 0.6),
        (RainbowColor.ACCUMULATE, 0.35),
        (RainbowColor.BUY, 0.2),
        (RainbowColor.BASICALLY_FIRE_SALE, 0.1)
    ]

    def determine_band(price, base_price):
        for band, multiplier in rainbow_bands:
            if price >= base_price * multiplier:
                return band
        return RainbowColor.BASICALLY_FIRE_SALE

    a = 0.173
    b = 4.02
    start_date = datetime(2009, 1, 9)

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch data: {response.status_code} - {response.text}")

    data = response.json()
    latest = data[-1]

    time_str = latest['time'].rstrip('Z')
    timestamp = datetime.fromisoformat(time_str)

    price = float(latest['price'])
    days_since_start = (timestamp.date() - start_date.date()).days
    base_price = 10 ** (a * math.log(days_since_start) + b)
    band = determine_band(price, base_price)
    return band, price, base_price

# =======================================================
# Trading account
# =======================================================

def get_current_liquidity():
    return get_balance_for_symbol(config["LIQUIDITY_SYMBOL"])

def get_current_investment():
    return get_balance_for_symbol(config["INVESTED_SYMBOL"]) * get_price_for_symbol(config["TRADING_SYMBOL"])

def get_current_balance():
    return get_current_investment() + get_current_liquidity()

def round_down(number, decimals=0):
    factor = 10 ** decimals
    return math.floor(number * factor) / factor

def buy(quantity):
    try:
        quantity = round_down(quantity, 6)
        order = session.place_order(
            category="spot",
            symbol=config["TRADING_SYMBOL"],
            side="Buy",
            order_type="Market",
            qty=quantity,
        )
        if not order or order.get("retCode", 1) != 0:
            error_msg = order.get("retMsg", "Unknown error") if order else "No response from API"
            logging.error(f"❌ Buy order failed for {quantity}: {error_msg}")
            return False
        logging.info(f"✅ Buy order placed for {quantity}")
        return True
    except Exception as e:
        logging.error(f"❌ Error placing buy order for {quantity}: {e}")
        return False

def sell(quantity):
    try:
        quantity = round_down(quantity, 6)
        order = session.place_order(
            category="spot",
            symbol=config["TRADING_SYMBOL"],
            side="Sell",
            order_type="Market",
            qty=quantity,
        )
        if not order or order.get("retCode", 1) != 0:
            error_msg = order.get("retMsg", "Unknown error") if order else "No response from API"
            logging.error(f"❌ Sell order failed for {quantity}: {error_msg}")
            return False
        logging.info(f"✅ Sell order placed for {quantity}")
        return True
    except Exception as e:
        logging.error(f"❌ Error placing sell order for {quantity}: {e}")
        return False
    
def get_balance_for_symbol(symbol):
    try:
        balance_data = session.get_wallet_balance(accountType="UNIFIED")
        balances = balance_data['result']['list'][0]['coin']
        for coin in balances:
            if coin['coin'] == symbol:
                return float(coin['walletBalance'])
    except Exception as e:
        logging.error(f"❌ Error fetching balance for {symbol}: {e}")
    return 0.0

# =======================================================
# Yahoo finance
# =======================================================

def get_dxy_history(ticker='DX-Y.NYB', lookback_weeks=4):
    dxy = yf.download(ticker, interval='1wk', period=f'{lookback_weeks+2}wk')

    if dxy.empty or 'Close' not in dxy.columns:
        return "Failed to fetch DXY data or 'Close' column is missing."

    close_prices = dxy['Close'].dropna()

    if len(close_prices) < lookback_weeks + 1:
        return "Not enough valid data points."

    # Get the last `lookback_weeks` close values
    trend = close_prices.iloc[-lookback_weeks:].values.tolist()
    return trend
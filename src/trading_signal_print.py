from trading_signal import *
from pycoingecko import CoinGeckoAPI
import requests

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    market_state = get_market_state()
    if market_state is not None:
        logging.info(f"📊 Market State: {market_state}")
        responses = get_ai_responses(market_state)
        logging.info(f"📊 AI Responses: {responses}")
        signal = get_trading_signal(market_state, responses)
        logging.info(f"📊 Trading Signal: {signal}")

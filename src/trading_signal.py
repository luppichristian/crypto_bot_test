from trading_api import *
from chatbot_api import *
import numpy as np  # Added for linear regression
from tradingview_ta import TA_Handler, Interval

# =======================================================
# Trading signal
# =======================================================

def get_trading_signal(market_state, responses):
    score = 0
    weights = 0

    if config["VERBOSE_LOGGING"]:
        logging.info("Verbose signal logging:");

    # NOTE: We want to increment the score to incentivize buying and decrement it the incentivize selling
    def apply_weight(
            name, 
            value = 0, 
            buy_min = 0, buy_max = 0, 
            sell_min  = 0, sell_max = 0, 
            inverse_buy = True, inverse_sell = False, 
            condition_buy = True, condition_sell = True,
            ignore_ranges = False):
        
        nonlocal score, weights

        weight = config["SIGNAL_WEIGHTS"][name]
        weights += weight

        buy_range_matched = value >= buy_min and value <= buy_max
        sell_range_matched = value >= sell_min and value <= sell_max
        if ignore_ranges:
            buy_range_matched = True
            sell_range_matched = True

        alpha = 1.0

        if buy_range_matched and condition_buy: # Apply buy weight
            if not ignore_ranges:
                buy_dim = buy_max - buy_min
                alpha = max(0.0, min((value - buy_min) / buy_dim, 1.0)) if buy_dim > 0 else 1.0
                if inverse_buy and buy_dim > 0:
                    alpha = 1.0 - alpha
            applied = weight * alpha 
            score += applied
            if config["VERBOSE_LOGGING"]:
                logging.info(f"\tApplying buy weight {name}: base_value: {weight}, applied: {applied}, alpha: {alpha}")

        elif sell_range_matched and condition_sell: # Apply sell weight
            if not ignore_ranges:
                sell_dim = sell_max - sell_min
                alpha = max(0.0, min((value - sell_min) / sell_dim, 1.0)) if sell_dim > 0 else 1.0
                if inverse_sell and sell_dim > 0:
                    alpha = 1.0 - alpha
            applied = weight * alpha
            score -= applied
            if config["VERBOSE_LOGGING"]:
                logging.info(f"\tApplying sell weight {name}: base_value: {weight}, applied: {applied}, alpha: {alpha}")

    # ---
    # --- Moving averages ---
    # ---
    
    price_history = market_state["price_history"] 
    ma = sum(price_history[:config["MA_LENGTH"]]) / config["MA_LENGTH"]
    ma_prev = sum(price_history[config["MA_LENGTH"]:config["MA_LENGTH"] * 2]) / config["MA_LENGTH"]
    slope = ma - ma_prev
    uptrend = slope > 0
    downtrend = slope < 0
    price_below_ma = market_state["current_price"] < ma
    price_over_ma = market_state["current_price"] > ma
    ath = max(price_history)

    # Generally if the price is below the moving average, its a good time to buy since a correction is more likely,
    # but if the price is over the moving average, its not a good idea to buy.
    apply_weight(
        name="price_ma",
        condition_buy=market_state["current_price"] < ma,
        condition_sell=market_state["current_price"] > ma,
        ignore_ranges=True
    )

    # ---
    # --- Fear and Greed Index ---
    # ---

    # If index is in the fear zone, we want to be more aggressive, a bullish correction is more likely
    # If index is in the greed zone, we want to be more cautious, a bearish correction is more likely
    apply_weight(
        name="fear_greed", 
        value=market_state["fear_greed"], 
        buy_min=0, 
        buy_max=config["FEAR_AND_GREED_EXTREME_FEAR"],
        sell_min=config["FEAR_AND_GREED_EXTREME_GREED"], 
        sell_max=100,
    )

    # ---
    # --- News Sentiment ---
    # ---

    # Incentivize buying if people are bullish, Incentivize selling if people are bearish
    apply_weight("news", market_state["news_sentiment"], 1, 1, -1, -1)

    # ---
    # --- Bitcoin Halving ---
    # ---

    # Historically, after around 5/6 months, bitcoin starts rising in price (good sell opportunity)    
    apply_weight(
        name="halving", 
        value=market_state["days_since_last_halving"], 
        buy_min=0, 
        buy_max=config["DAYS_HALVING_THRESHOLD"],
        inverse_buy=False,
        condition_sell=False
    )


    # ---
    # --- All time high bias ---
    # ---

    # If we are very close to the all time high and we are in an uptrend, its probably a good place to sell
    # If we are very far from the all time high and we are in a downtrend, its probably a good place to buy
    price_percentage_ath = market_state["current_price"] / ath
    apply_weight(
        name="ath", 
        value=price_percentage_ath, 
        buy_min=0, 
        buy_max=config["ATH_FAR_THRESHOLD"],
        sell_min=config["ATH_CLOSE_THRESHOLD"], 
        sell_max=1.0,
        condition_buy=downtrend,
        condition_sell=uptrend
    )

    # ---
    # --- Google trends ---
    # ---

    # If crypto is overvalued, searched by norms and retailers, probably a good time to sell.
    # Otherwise if crypto is undervalued, no one cares about it
    apply_weight(
        name="google_trends", 
        value=market_state["google_trends"], 
        buy_min=0, 
        buy_max=config["GOOGLE_TRENDS_LOW_POPULARITY_THRESHOULD"],
        sell_min=config["GOOGLE_TRENDS_HIGH_POPULARITY_THRESHOLD"], 
        sell_max=100,
    )

    # ---
    # --- Rainbow BTC
    # ---

    apply_weight(
        name="rainbow_btc_strong", 
        condition_buy=market_state["rainbow_band"] == str(RainbowColor.BASICALLY_FIRE_SALE),
        condition_sell=market_state["rainbow_band"] == str(RainbowColor.MAX_BUBBLE_TERRITORY),
        ignore_ranges=True
    )

    apply_weight(
        name="rainbow_btc", 
        condition_buy=market_state["rainbow_band"] == str(RainbowColor.BUY),
        condition_sell=market_state["rainbow_band"] == str(RainbowColor.SELL_PLEASE),
        ignore_ranges=True
    )

    # ---
    # --- Gemini AI ---
    # ---

    # Check ai prompt, 1 if ai wants us to buy, -1 if ai wants us to sell
    apply_weight("gemini_ai", responses["gemini"], 1, 1, -1, -1)

    # ---
    # --- DXY
    # ---

    # Normally when the dollar gains strength, crypto falls to match the value of the dollar. (and viceversa)
    dxy_is_rising = all(x < y for x, y in zip(market_state["dxy_history"], market_state["dxy_history"][1:]))
    dxy_is_falling = all(x > y for x, y in zip(market_state["dxy_history"], market_state["dxy_history"][1:]))
    apply_weight(
        name="dxy", 
        condition_buy=dxy_is_falling,
        condition_sell=dxy_is_rising,
        ignore_ranges=True
    )

    # ---
    # --- Tradingview analysis
    # ---

    apply_weight(
        name="tradingview_analysis_strong", 
        condition_buy=market_state["tradingview_analysis"] == "STRONG_BUY",
        condition_sell=market_state["tradingview_analysis"] == "STRONG_SELL",
        ignore_ranges=True
    )

    apply_weight(
        name="tradingview_analysis", 
        condition_buy=market_state["tradingview_analysis"] == "BUY",
        condition_sell=market_state["tradingview_analysis"] == "SELL",
        ignore_ranges=True
    )
  
    # ---
    # --- Verbose logging
    # ---

    verbose_details = {
        "ma" : ma,
        "ath" : ath,
        "ma_prev" : ma_prev,
        "slope" : slope,
        "uptrend" : uptrend,
        "downtrend" : downtrend,
        "price_below_ma" : price_below_ma,
        "price_over_ma" : price_over_ma,
        "price_percentage_ath" : price_percentage_ath,
        "dxy_is_rising": dxy_is_rising,
        "dxy_is_falling": dxy_is_falling,
    }

    if config["VERBOSE_LOGGING"]:
        logging.info(f"\tDetails: {verbose_details}")
        logging.info(f"\tScore: {score}")
        logging.info(f"\tWeights: {weights}")

    if weights == 0:
        return 0.0
    return min(max(round(score / weights, 3), -1.0), 1.0)

# =======================================================
# Market state
# =======================================================

def get_market_state():
    try:
        news_sentiment = get_cryptopanic_sentiment()
        if news_sentiment == -1:
            logging.info("\t📰 Negative news sentiment detected.")
        elif news_sentiment == 1:
            logging.info("\t📰 Positive news sentiment detected.")
        else:
            logging.info("\t📰 Neutral news sentiment.")

        fear_greed = get_fear_and_greed_index()
        btc_dom = get_btc_dominance()

        current_price = get_price_for_symbol(config["TRADING_SYMBOL"])

        halving = get_halving_info()

        price_history_raw = get_price_history(config["TRADING_SYMBOL"], interval="W", limit=max(config["MA_LENGTH"] * 2, 120))
        price_history = [x['price'] for x in price_history_raw] if price_history_raw else []

        google_trends = get_today_google_search("bitcoin")

        rainbow_band, rainbow_price, rainbow_base_price = get_bitcoin_rainbow_band()

        handler = TA_Handler(
            symbol=config["TRADING_SYMBOL"],
            screener="crypto",
            exchange="BINANCE",
            interval=Interval.INTERVAL_1_MONTH,
        )

        tradingview_analysis = handler.get_analysis().summary["RECOMMENDATION"]

        dxy_history = get_dxy_history(lookback_weeks=config["DXY_LENGTH"])

    except Exception as e:
        logging.error(f"❌ Error fetching necessary indicators for trade decision: {e} Skipping...")
        return None
    
    return {
        "current_price": current_price,
        "price_history": price_history,
        "fear_greed": fear_greed,
        "btc_dom": btc_dom,
        "news_sentiment": news_sentiment,
        "days_until_next_halving": halving["days_until_next_halving"],
        "days_since_last_halving": halving["days_since_last_halving"],
        "google_trends": google_trends,
        "rainbow_band": str(rainbow_band),
        "tradingview_analysis": tradingview_analysis,
        "dxy_history": dxy_history
    }

# =======================================================
# AI Responses
# =======================================================

def get_ai_responses(market_state):
    ai_prompt = f"""Analyze the current market state: {market_state}. 
    Please strictly respond with only one integer value: 
    respond with -1 if you think its a good time to sell and bad time to buy;
    respond with 1 if you think its good time to buy or bad time to sell;
    respond with 0 if you are neutral about buying/selling;"""

    # Gemini
    raw_gemini_response = get_gemini_response(ai_prompt)
    try:
        gemini_response = int(raw_gemini_response) if raw_gemini_response is not None else 0
    except ValueError:
        gemini_response = 0  # fallback in case response is not a valid integer
    
    return {
        "gemini": gemini_response,
    }

from trading_api import *
from chatbot_api import *
from trading_signal import *
import json
import os
import csv
import statistics
from enum import Enum

# =======================================================
# Setup Logging
# =======================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGGING_FILE, mode='a', encoding='utf-8')
    ]
)

# =======================================================
# Bot State
# =======================================================

state = {
    "initialized": False,
    "last_price": 0.0,
    "last_trade_time": 0.0,
    "start_balance": 0.0,
    "start_time": 0.0,
    "start_price": 0.0,
    "paid_for_investment": 0.0,
    "orders": [],
    "states": [],
    "trailing_high": 0.0,
    "lots": []  # Each lot: {"quantity": float, "price": float, "value": float}
}

# =======================================================
# Sell lots
# =======================================================

def sell_lots(current_price, signal_analysis):
    logging.info("\t📊 Evaluating sell decision...")

    # --- 
    # -- Check if we can place a sell order ---
    # ---

    if get_current_investment() <= config["MIN_TRADE_QUANTITY_LIQUID"]:
        logging.info("\t\t⚠️ Not enough investment to sell. Skipping sell.")
        return False
    lots = state["lots"]
    if not lots:
        logging.info("\t\t⚠️ No invested lots. Skipping sell.")
        return False
    if state["paid_for_investment"] == 0:
        logging.info("\t\t⚠️ No paid for investment. Skipping sell.")
        return False

    # ---
    # -- Calculate optimal stop loss and take profit thresholds for current market conditions ---
    # ---

    trailing_stop_pct = config["TRAILING_STOP_LOSS_PCT"]
    take_profit_pct = config["TAKE_PROFIT_PCT"]

    if signal_analysis["sell_signal"] and signal_analysis["sell_confirmation"]:
        logging.info(f"\t\t🔴 Bearish signal detected. Adjusting sell thresholds. Trailing stop loss slip is {config['TRAILING_STOP_LOSS_SLIP']:.2%}, Take profit slip is {config['TAKE_PROFIT_SPLIP']:.2%}")
        trailing_stop_pct = max(trailing_stop_pct - config["TRAILING_STOP_LOSS_SLIP"], config["TRAILING_STOP_LOSS_SLIP"])
        take_profit_pct = max(take_profit_pct - config["TAKE_PROFIT_SPLIP"], config["TAKE_PROFIT_SPLIP"])
    
    elif signal_analysis["buy_signal"] and signal_analysis["buy_confirmation"]:
        logging.info(f"\t\t🟢 Bullish signal detected. Adjusting sell thresholds. Trailing stop loss slip is {config['TRAILING_STOP_LOSS_SLIP']:.2%}, Take profit slip is {config['TAKE_PROFIT_SPLIP']:.2%}")
        trailing_stop_pct = trailing_stop_pct + config["TRAILING_STOP_LOSS_SLIP"]
        take_profit_pct = take_profit_pct + config["TAKE_PROFIT_SPLIP"]

    # ---
    # -- Update and maybe sell each lot ---
    # ---

    any_sold = False
    for lot in lots[:]:
        lot["trailing_high"] = max(current_price, lot["trailing_high"])

        realized_pct = (current_price - lot["price"]) / lot["price"]
        trailing_drawdown = (current_price - lot["trailing_high"]) / lot["trailing_high"]
        current_sold = False

        info = "Unspecified"

        # Trailing stop-loss: sell if price drops from trailing high by trailing_stop_pct
        if trailing_drawdown < -trailing_stop_pct:
            logging.info("\t\t🔴 Trailing stop-loss triggered for lot.")
            info = f"Trailing stop-loss triggered: Trailing drawdown is {trailing_drawdown:.2%}, realized percentage is {realized_pct:.2%}, trailing stop percentage is {trailing_stop_pct:.2%}"
            current_sold = True
        
        # Take profit: sell if price increases from lot price by take_profit_pct
        elif realized_pct > take_profit_pct:
            logging.info("\t\t🟢 Take-profit triggered for lot.")
            info = f"Take-profit triggered: Realized percentage is {realized_pct:.2%}, Take profit is {take_profit_pct:.2%}"
            current_sold = True
        
        # Sell the lot if conditions are met
        if current_sold and sell(lot["quantity"]):
            any_sold = True
            state["orders"].append({
                "type": "sell",
                "timestamp": time.time(),
                "price": current_price,
                "quantity": lot["quantity"],
                "value": lot["quantity"] * current_price,
                "info": info
            })
            state["last_trade_time"] = time.time()
            lots.remove(lot)
    
    if any_sold:
        state["paid_for_investment"] = sum(l["value"] for l in lots)
    else:
        logging.info("\t\t⚠️ No sell conditions met for any lot. Skipping sell.")
    return any_sold

# =======================================================
# Buy lots
# =======================================================

def buy_lot(quantity, current_price):
    if buy(quantity * current_price):
        return False

    state["orders"].append({
        "type": "buy",
        "timestamp": time.time(),
        "price": current_price,
        "quantity": quantity,
        "value": current_price * quantity,
        "info": "Bullish signal buy"
    })

    state["lots"].append({
        "quantity": quantity, 
        "price": current_price, 
        "value": quantity * current_price,
        "trailing_high": current_price
    })

    state["paid_for_investment"] = sum(l["value"] for l in state["lots"])
    state["last_trade_time"] = time.time()
    return True

def buy_lots(current_price, signal_analysis):
    logging.info("\t📊 Evaluating buy decision...")

    # --- 
    # -- Check if we can place a buy order ---
    # ---

    liquidity = get_current_liquidity()
    if liquidity < config["MIN_TRADE_QUANTITY_LIQUID"]:
        return False

    if len(state["states"]) < config["SIGNAL_ANALYSIS_COUNT"]:
        logging.info("\t\t⚠️ Not enough trading states to confirm bullish trend. Skipping buy.")
        return False
    
    invested_percentage = round(get_current_investment() / get_current_balance(), 2)
    logging.info(f"\t\t💰 Invested Percentage: {invested_percentage}%, Max invested percentage: {config['MAX_INVESTED_PERCENTAGE']}%")
    if invested_percentage >= config["MAX_INVESTED_PERCENTAGE"]:
        logging.info("\t\t⚠️ Already invested enough. Skipping buy.")
        return False
    
    # ---
    # -- Place buy order if conditions are met ---
    # ---

    if signal_analysis["buy_signal"] and signal_analysis["buy_confirmation"] and not signal_analysis["buy_signal_increasing"]:
        quantity = (liquidity / current_price) * config["MAX_INVESTED_PERCENTAGE"] * config["BUY_QUANTITY_PERCENTAGE"]  
        if buy_lot(quantity, current_price):
            logging.info(f"\t\t🟢 Buy signal detected");
            return True
    return False

# =======================================================
# Signal Analysis
# =======================================================

def get_signal_analysis(market_state, responses):
    signal = get_trading_signal(market_state, responses)
    buy_signal = signal >= config["BUY_SIGNAL_THRESHOLD"]
    sell_signal = signal <= config["SELL_SIGNAL_THRESHOLD"]
    buy_confirmation = all(s["signal_analysis"]["signal"] >= config["BUY_SIGNAL_THRESHOLD"] for s in state["states"][-config["SIGNAL_ANALYSIS_COUNT"]:]) if len(state["states"]) >= config["SIGNAL_ANALYSIS_COUNT"] else False
    sell_confirmation = all(s["signal_analysis"]["signal"] <= config["SELL_SIGNAL_THRESHOLD"] for s in state["states"][-config["SIGNAL_ANALYSIS_COUNT"]:]) if len(state["states"]) >= config["SIGNAL_ANALYSIS_COUNT"] else False

    # Compute buy_signal_increasing: slope between current signal and oldest in window
    buy_signal_increasing = False
    if len(state["states"]) >= config["SIGNAL_ANALYSIS_COUNT"]:
        oldest_signal = state["states"][-config["SIGNAL_ANALYSIS_COUNT"]]["signal_analysis"]["signal"]
        slope = signal - oldest_signal
        buy_signal_increasing = slope >= 0

    return {
        "signal": signal,
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
        "buy_confirmation": buy_confirmation,
        "sell_confirmation": sell_confirmation,
        "buy_signal_increasing": buy_signal_increasing,
    }

# =======================================================
# Trading decision
# =======================================================

def update_trades():
    logging.info("📊 Evaluating trade decision...")

    # ---
    # -- Market State --
    # ---

    market_state = get_market_state()
    if market_state is None:
        return  # Skip this iteration if market state could not be fetched
    logging.info(f"\t📊 Market State: {market_state}")

    # ---
    # --- AI Requests ---
    # ---

    responses = get_ai_responses(market_state)
    logging.info(f"\t📊 AI Responses: {responses}")

    # ---
    # --- Trading Signal Analysis ---
    # ---

    signal_analysis = get_signal_analysis(market_state, responses)
    logging.info(f"\t📊 Signal Analysis: {signal_analysis}")

    # ---
    # --- Lot Management ---
    # ---

    any_lots_sold = sell_lots(market_state["current_price"], signal_analysis)
    any_lots_bought = buy_lots(market_state["current_price"], signal_analysis)
    if not any_lots_sold and not any_lots_bought:
        logging.info("\t⚖️ No trading operation today.")

    # ---
    # --- Logging State ---
    # ---

    state["states"].append({
        "timestamp": time.time(),
        "price": market_state["current_price"],
        "liquidity": get_current_liquidity(),
        "investment": get_current_investment(),
        "market_state": market_state,
        "responses": responses,
        "quantity": get_balance_for_symbol(config["INVESTED_SYMBOL"]),
        "paid_for_investment": state["paid_for_investment"],
        "lot_count": len(state["lots"]),
        "signal_analysis": signal_analysis,
    })

# =======================================================
# Main Execution
# =======================================================

def load_state():
    if os.path.exists(TRADING_STATE_FILE):
        with open(TRADING_STATE_FILE, "r") as f:
            loaded_state = json.load(f)
            state.update(loaded_state)
    if not state["initialized"]:
        state["initialized"] = True
        state["last_price"] = get_price_for_symbol(config["TRADING_SYMBOL"])
        state["start_balance"] = get_current_balance()
        state["start_time"] = time.time()
        state["start_price"] = state["last_price"]

def save_state():
    with open(TRADING_STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} minutes"
    else:
        return f"{seconds / 3600:.1f} hours"

if __name__ == "__main__":
    try:
        load_state()
        while True:
            load_api_keys_config()
            load_trader_config()
            update_trades()

            logging.info(f"🕒 Next trade update in {format_duration(config['TRADING_INTERVAL_SECONDS'])} ...")
            state["last_price"] = get_price_for_symbol(config["TRADING_SYMBOL"])
            save_state()

            time.sleep(config["TRADING_INTERVAL_SECONDS"])

    except KeyboardInterrupt:
        logging.info("👋 Bot stopped manually. Cleaning up...")
        save_state()
import json
import os

LOGGING_FILE = "log.txt"
TRADING_STATE_FILE = "state.json"
API_KEYS_FILE = "config/api_keys.json"
TRADER_FILE = "config/trader.json"
SERVER_FILE = "config/server.json"

def load_api_keys_config():
    global api_keys
    with open(API_KEYS_FILE, 'r') as f:
        api_keys = json.load(f)

def load_trader_config():
    global config
    with open(TRADER_FILE, 'r') as f:
        config = json.load(f)
        config["TRADING_SYMBOL"] = f"{config['INVESTED_SYMBOL']}{config['LIQUIDITY_SYMBOL']}"

def load_server_config():
    global server_config
    try:
        with open(SERVER_FILE, 'r') as f:
            server_config = json.load(f)
    except FileNotFoundError:
        print(f"Server configuration file {SERVER_FILE} not found.")
        server_config = {}

load_api_keys_config()
load_trader_config()
load_server_config()
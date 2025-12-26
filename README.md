# 🤖 Crypto Trading Bot

An automated cryptocurrency trading bot that uses technical analysis, market sentiment, and AI-powered insights to execute intelligent trading decisions on Bybit.

## 📋 Features

- **Automated Trading**: Continuously monitors market conditions and executes buy/sell orders based on configurable strategies
- **Multi-Signal Analysis**: Combines multiple indicators for informed trading decisions:
  - Moving averages and trend analysis
  - Fear & Greed Index
  - Google Trends sentiment analysis
  - RSI (Relative Strength Index)
  - TradingView technical analysis
  - AI-powered market insights via Google Gemini
- **Intelligent Position Management**:
  - Lot-based position tracking
  - Dynamic trailing stop-loss
  - Adaptive take-profit levels
  - Risk management with configurable thresholds
- **Real-Time Dashboard**: Streamlit-based web interface for monitoring:
  - Portfolio performance metrics
  - Live trading signals and analysis
  - Order history and active positions
  - Price charts and balance history
  - Configuration management
- **Remote Monitoring**: Download trading state and logs from remote servers via SFTP

## 🏗️ Architecture

```
├── src/
│   ├── trader.py              # Main trading bot logic
│   ├── trading_api.py         # Bybit API integration & market data
│   ├── trading_signal.py      # Signal generation and analysis
│   ├── chatbot_api.py         # Google Gemini AI integration
│   ├── dashboard.py           # Streamlit web dashboard
│   ├── server_download.py     # Remote file download utilities
│   └── config.py              # Configuration loader
├── config/
│   ├── api_keys.json          # API credentials (not in repo)
│   ├── trader.json            # Trading parameters
│   └── server.json            # Remote server settings
├── state.json                 # Bot state persistence
├── log.txt                    # Trading activity logs
└── requirements.txt           # Python dependencies
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Bybit account (testnet or mainnet)
- Google Gemini API key

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd crypto_bot_test
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API keys in `config/api_keys.json`:
```json
{
  "BYBIT_API_KEY": "your_bybit_api_key",
  "BYBIT_API_SECRET": "your_bybit_api_secret",
  "GEMINI_API_KEY": "your_gemini_api_key"
}
```

4. Configure trading parameters in `config/trader.json`:
```json
{
  "TRADING_SYMBOL": "BTCUSDT",
  "INVESTED_SYMBOL": "BTC",
  "LIQUIDITY_SYMBOL": "USDT",
  "MIN_TRADE_QUANTITY_LIQUID": 10,
  "TRADING_INTERVAL_SECONDS": 300,
  "TRAILING_STOP_LOSS_PCT": 0.05,
  "TAKE_PROFIT_PCT": 0.10,
  ...
}
```

### Running the Bot

Start the trading bot:
```bash
python src/trader.py
```

Launch the dashboard:
```bash
streamlit run src/dashboard.py
```

The dashboard will be available at `http://localhost:8501`

## 📊 Trading Strategy

The bot employs a sophisticated multi-factor trading strategy:

### Buy Signals
- Price below moving average (potential correction)
- Extreme fear in Fear & Greed Index
- Increasing Google Trends interest
- Oversold RSI conditions
- Bullish TradingView signals
- AI-identified bullish patterns

### Sell Signals
- Trailing stop-loss triggered (default: 5% from peak)
- Take-profit target reached (default: 10% gain)
- Extreme greed conditions
- Overbought technical indicators
- AI-identified bearish patterns

### Position Management
- Lot-based position tracking for granular profit/loss management
- Individual trailing stops per lot
- Dynamic threshold adjustment based on market conditions
- Configurable minimum trade quantities

## 🎛️ Configuration

### Key Trading Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `TRADING_INTERVAL_SECONDS` | Time between trade evaluations | 300 |
| `TRAILING_STOP_LOSS_PCT` | Stop-loss percentage from peak | 0.05 |
| `TAKE_PROFIT_PCT` | Take-profit percentage | 0.10 |
| `MIN_TRADE_QUANTITY_LIQUID` | Minimum trade size (USDT) | 10 |
| `MA_LENGTH` | Moving average period | 20 |
| `RSI_PERIOD` | RSI calculation period | 14 |

### Signal Weights

Configure individual signal weights in `trader.json` under `SIGNAL_WEIGHTS`:
- `price_ma`: Moving average signals
- `fear_greed`: Fear & Greed Index
- `rsi`: RSI indicator
- `chatbot`: AI-powered analysis
- `tradingview`: TradingView technical analysis

## 📈 Dashboard Features

- **Status Tab**: Real-time portfolio metrics, balance, and performance
- **States Tab**: Historical state tracking with market conditions
- **Orders Tab**: Complete order history with execution details
- **Price & Signal Tab**: Live price chart and signal strength indicators
- **Active Lots Tab**: Current open positions with P&L tracking
- **Configuration Tabs**: Edit API keys and trading parameters on-the-fly

## 🛡️ Risk Management

- **Position Limits**: Configurable minimum trade quantities
- **Stop-Loss Protection**: Automatic trailing stop-loss per position
- **Take-Profit Targets**: Lock in profits at configurable levels
- **Signal Confirmation**: Multi-factor validation before trades
- **State Persistence**: Automatic state saving to prevent data loss

## 📝 Logging

All trading activity is logged to `log.txt` with:
- Trade executions and reasoning
- Market analysis and signal scores
- Position updates and P&L
- Errors and warnings

Enable verbose logging with `"VERBOSE_LOGGING": true` in `trader.json`

## 🔧 Advanced Features

### Remote Server Integration
Download state and logs from remote server:
```bash
python src/server_download.py
```

Configure server details in `config/server.json`:
```json
{
  "HOSTNAME": "your-server.com",
  "PORT": 22,
  "USERNAME": "your_username",
  "PASSWORD": "your_password"
}
```

### Custom Signal Development
Extend `trading_signal.py` to add custom indicators:
```python
def get_trading_signal(market_state, responses):
    # Add your custom signal logic
    apply_weight(
        name="custom_signal",
        value=your_indicator_value,
        buy_min=threshold_min,
        buy_max=threshold_max
    )
```

## ⚠️ Disclaimer

**USE AT YOUR OWN RISK**

This bot is for educational purposes. Cryptocurrency trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred while using this software.

- Always test in Bybit testnet environment first
- Never invest more than you can afford to lose
- Monitor the bot's performance regularly
- Understand the code before running in production

## 📦 Dependencies

- `pybit`: Bybit API integration
- `google-genai`: Google Gemini AI
- `streamlit`: Dashboard web interface
- `tradingview-ta`: TradingView technical analysis
- `yfinance`: Market data
- `pytrends`: Google Trends data
- `numpy`: Numerical computations
- `paramiko`: SFTP file transfers

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

This project is provided as-is for educational purposes.

## 🔮 Future Enhancements

See `todo.txt` for planned features including:
- HODL waves analysis
- Derivatives and funding rate signals
- Volume divergence detection
- MVRV and NVT ratio integration
- Macroeconomic indicators (DXY, Treasury yields)
- Multi-asset support

---

**Happy Trading! 📈🚀**

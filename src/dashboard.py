import streamlit as st
import json
import os
import time
import requests
import pandas as pd
from datetime import datetime
from config import *
from trading_api import *
import paramiko

# =======================================================
# Setup
# =======================================================

REFRESH_INTERVAL = 10  # seconds

# Auto-refresh logic should be at the very top before any UI rendering
if 'last_refresh' not in st.session_state:
    st.session_state['last_refresh'] = time.time()
else:
    if time.time() - st.session_state['last_refresh'] > REFRESH_INTERVAL:
        st.session_state['last_refresh'] = time.time()
        load_api_keys_config()
        load_trader_config()
        st.rerun()

def load_state():
    if os.path.exists(TRADING_STATE_FILE):
        with open(TRADING_STATE_FILE, "r") as f:
            return json.load(f)
    return None

def format_runtime(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

state = load_state()

st.set_page_config(page_title="Crypto Bot Dashboard", layout="wide")
st.markdown("""
# 📈 Crypto Bot Dashboard
---
""")

tabs = st.tabs(["Status", "States", "Orders", "Price & Signal", "Active Lots", "Edit API Keys", "Edit Config"])

# =======================================================
# Status tab
# =======================================================

with tabs[0]:  # Status
    st.markdown("<h2 style='text-align:left; font-size:1.6em;'>🚦 Status</h2>", unsafe_allow_html=True)
    if state:
        col1, col2 = st.columns([1, 2], gap="large")
        with col1:
            balance = get_current_balance()
            start_balance = state['start_balance']
            delta = (balance - start_balance) / start_balance * 100.0
            market_delta = (get_price_for_symbol(config["TRADING_SYMBOL"]) - state['start_price']) / state['start_price'] * 100.0
            liquidity = get_current_liquidity()
            investment = get_current_investment()
            invested_qty = get_balance_for_symbol(config["INVESTED_SYMBOL"])
            runtime_str = format_runtime(time.time() - state["start_time"])

            # Markdown table for aligned values
            st.markdown(f'''
<table style="font-size:1.1em;">
<tr><td><b>Balance ({config['LIQUIDITY_SYMBOL']})</b></td><td style="text-align:right;color:#1976d2;"><b>${balance:.2f}</b></td></tr>
<tr><td><b>Start Balance ({config['LIQUIDITY_SYMBOL']})</b></td><td style="text-align:right;color:#1976d2;">${start_balance:.2f}</td></tr>
<tr><td><b>Performance</b></td><td style="text-align:right;color:{'green' if delta >= 0 else 'red'};">{delta:+.2f}%</td></tr>
<tr><td><b>Market Delta</b></td><td style="text-align:right;color:{'green' if market_delta >= 0 else 'red'};">{market_delta:+.2f}%</td></tr>
<tr><td><b>Liquidity ({config['LIQUIDITY_SYMBOL']})</b></td><td style="text-align:right;color:#1976d2;">${liquidity:.2f}</td></tr>
<tr><td><b>Invested ({config['LIQUIDITY_SYMBOL']})</b></td><td style="text-align:right;color:#1976d2;">${investment:.2f}</td></tr>
<tr><td><b>Invested ({config['INVESTED_SYMBOL']})</b></td><td style="text-align:right;color:#1976d2;">{invested_qty:.6f}</td></tr>
<tr><td><b>Runtime</b></td><td style="text-align:right;color:#1976d2;">{runtime_str}</td></tr>
</table>
''', unsafe_allow_html=True)
        with col2:
            st.markdown("<h4 style='margin-bottom:0.2em;'>📉 All-Time Balance History</h4>", unsafe_allow_html=True)
            if state.get("states"):
                states_list = state["states"]
                balance_data = [
                    {
                        "Time": datetime.fromtimestamp(s["timestamp"]),
                        "Balance": s.get("liquidity", 0) + s.get("investment", 0)
                    }
                    for s in states_list
                ]
                df_balance = pd.DataFrame(balance_data)
                df_balance = df_balance.set_index("Time")

                # Overlay buy/sell order vertical lines using Altair
                import altair as alt
                chart = alt.Chart(df_balance.reset_index()).mark_line(color='#1976d2').encode(
                    x=alt.X('Time:T', title='Time'),
                    y=alt.Y('Balance:Q', title='Balance')
                )

                # Prepare order vertical lines
                if state.get("orders"):
                    orders = state["orders"]
                    order_lines = []
                    for o in orders:
                        color = '#43a047' if o["type"] == "buy" else '#e53935'
                        order_lines.append({
                            "Time": datetime.fromtimestamp(o["timestamp"]),
                            "Type": o["type"],
                            "Color": color
                        })
                    df_orders = pd.DataFrame(order_lines)
                    if not df_orders.empty:
                        vline = alt.Chart(df_orders).mark_rule().encode(
                            x='Time:T',
                            color=alt.Color('Color:N', scale=None, legend=None)
                        )
                        chart = alt.layer(chart, vline)

                st.altair_chart(chart.properties(width=900, height=400), use_container_width=True)
                st.caption("<span style='color:#1976d2;'>■</span> <b>Total balance</b> = liquidity + investment. <span style='color:#43a047;'>|</span> <b>Buy</b> <span style='color:#e53935;'>|</span> <b>Sell</b> vertical lines: buy/sell orders.", unsafe_allow_html=True)
            else:
                st.info("No state history to plot.")
    else:
        st.warning("No state file found.")

# =======================================================
# States tab
# =======================================================

with tabs[1]:  # States
    st.markdown("## State History")
    if state and state.get("states"):
        states_list = state["states"]
        st.dataframe([
            {
                "Time": datetime.fromtimestamp(s["timestamp"]).strftime('%Y-%m-%d %H:%M:%S'),
                "Price": s.get("price", "-"),
                "Liquidity": s.get("liquidity", "-"),
                "Investment": s.get("investment", "-"),
                "Market State": s.get("market_state", {}),
                "Responses": s.get("responses", {}),
                "Quantity": s.get("quantity", "-"),
                "Signal Analysis": s.get("signal_analysis", "-"),
                "Paid for Investment": s.get("paid_for_investment", "-"),
                "Lot Count": s.get("lot_count", "-"),
            }
            for s in states_list[::-1]
        ], use_container_width=True)
    else:
        st.info("No trading states yet.")

# =======================================================
# Orders Tab
# =======================================================

with tabs[2]:  # Orders
    st.markdown("## Order History")
    if state and state.get("orders"):
        trades = state["orders"]
        st.dataframe([
            {
                "Type": t["type"].capitalize(),
                "Time": datetime.fromtimestamp(t["timestamp"]).strftime('%Y-%m-%d %H:%M:%S'),
                "Price": f"${t.get('price', 0):.2f}",
                "Quantity": t.get("quantity", "-"),
                "Value": f"${t.get('value', 0):.2f}" if 'value' in t else "-",
                "Info": t.get("info", "-"),
            }
            for t in trades[::-1]
        ], use_container_width=True)
    else:
        st.info("No trading orders yet.")

# =======================================================
# Price & Signal tab
# =======================================================

with tabs[3]:  # Price & Signal
    st.markdown(f"<h2 style='text-align:left; font-size:1.6em;'>💹 {config['INVESTED_SYMBOL']} Price & Trading Signal History</h2>", unsafe_allow_html=True)
    if state and state.get("states"):
        states_list = state["states"]
        buy_threshold = config.get("BUY_SIGNAL_THRESHOLD", 0.6)
        sell_threshold = config.get("SELL_SIGNAL_THRESHOLD", -0.5)

        data = [
            {
                "Time": datetime.fromtimestamp(s["timestamp"]),
                "Price": s.get("price", 0),
                "Signal": s.get("signal_analysis", 0).get("signal", 0)
            }
            for s in states_list
        ]
        df = pd.DataFrame(data)
        import altair as alt
        base = alt.Chart(df).encode(x=alt.X('Time:T', title='Time'))
        price_line = base.mark_line(color='#1976d2').encode(
            y=alt.Y('Price:Q', title=f'{config["INVESTED_SYMBOL"]} Price', axis=alt.Axis(titleColor='#1976d2'))
        )
        # Signal and thresholds share the same axis
        signal_axis = alt.Y('Signal:Q', scale=alt.Scale(domain=[-1, 1]), title='Signal', axis=alt.Axis(titleColor='#ffd600'))
        signal_line = base.mark_line(color='#ffd600').encode(y=signal_axis)
        # Horizontal threshold lines as mark_line
        buy_df = pd.DataFrame({'Time': df['Time'], 'y': [buy_threshold]*len(df)})
        sell_df = pd.DataFrame({'Time': df['Time'], 'y': [sell_threshold]*len(df)})
        buy_rule = alt.Chart(buy_df).mark_line(color='#43a047', strokeDash=[4,2]).encode(x='Time:T', y=alt.Y('y:Q', scale=alt.Scale(domain=[-1, 1])))
        sell_rule = alt.Chart(sell_df).mark_line(color='#e53935', strokeDash=[4,2]).encode(x='Time:T', y=alt.Y('y:Q', scale=alt.Scale(domain=[-1, 1])))
        chart = alt.layer(
            price_line,
            signal_line,
            buy_rule,
            sell_rule
        ).resolve_scale(
            y = 'independent'
        ).properties(width=900, height=400)
        st.altair_chart(chart, use_container_width=True)
        st.caption(f"<span style='color:#1976d2;'>■</span> <b>Price</b>, <span style='color:#ffd600;'>■</span> <b>Signal</b> (-1 to 1) over time. <span style='color:#43a047;'>▭</span> <b>Buy</b> / <span style='color:#e53935;'>▭</span> <b>Sell</b> signal thresholds.", unsafe_allow_html=True)

        neutral_zone_width = (buy_threshold - sell_threshold)
        buy_zone_width = 1.0 - buy_threshold
        sell_zone_width = 1.0 - abs(sell_threshold)
        buy_sell_ratio = buy_zone_width / sell_zone_width

        try:
            risk_ratio = abs(buy_threshold) / abs(sell_threshold) if sell_threshold != 0 else float('inf')
        except Exception:
            risk_ratio = float('nan')
        # Styled markdown for signal zones (aligned in a table)
        st.markdown(f'''
<table style="font-size:1.1em;">
<tr><td><b>Neutral Signal Zone Width</b></td><td style="text-align:right;color:#ffd600;">{abs(neutral_zone_width * 0.5):.2%}</td></tr>
<tr><td><b>Buy Signal Zone Width</b></td><td style="text-align:right;color:#43a047;">{abs(buy_zone_width * 0.5):.2%}</td></tr>
<tr><td><b>Sell Signal Zone Width</b></td><td style="text-align:right;color:#e53935;">{abs(sell_zone_width * 0.5):.2%}</td></tr>
<tr><td><b>Buy/Sell Signal Zone Ratio</b></td><td style="text-align:right;color:#ffffff;">{buy_sell_ratio:.2%}</td></tr>
</table>
''', unsafe_allow_html=True)

    else:
        st.info("No trading states yet.")

with tabs[4]:  # Active Lots
    st.markdown("<h2 style='text-align:left; font-size:1.6em;'>📦 Active Lots</h2>", unsafe_allow_html=True)
    if state and state.get("lots"):
        lots_list = state["lots"]
        st.dataframe([
            {
                "Quantity": lot.get("quantity", "-"),
                "Price": lot.get("price", "-"),
                "Value": lot.get("value", "-"),
                "Trailing High": lot.get("trailing_high", "-")
            }
            for lot in lots_list
        ], use_container_width=True)
    else:
        st.info("No active lots.")

with tabs[5]:  # Edit API Keys
    st.markdown("## Edit API Keys")
    api_keys_data = {}
    if os.path.exists(API_KEYS_FILE):
        with open(API_KEYS_FILE, 'r') as f:
            api_keys_data = json.load(f)
    if api_keys_data:
        api_keys_form = st.form("api_keys_form")
        api_keys_inputs = {}
        for k, v in api_keys_data.items():
            api_keys_inputs[k] = api_keys_form.text_input(f"{k}", value=str(v))
        submitted = api_keys_form.form_submit_button("Save API Keys")
        if submitted:
            for k in api_keys_data:
                api_keys_data[k] = api_keys_inputs[k]
            with open(API_KEYS_FILE, 'w') as f:
                json.dump(api_keys_data, f, indent=4)
            st.success("API Keys updated.")
            load_api_keys_config()
            st.experimental_rerun()
    else:
        st.info("No API keys found.")

# =======================================================
# Config Tab
# =======================================================

with tabs[6]:  # Edit Config
    st.markdown("## Edit Config")
    config_data = {}
    if os.path.exists(TRADER_FILE):
        with open(TRADER_FILE, 'r') as f:
            config_data = json.load(f)
    if config_data:
        config_form = st.form("config_form")
        config_inputs = {}
        signal_weights_sum = 0.0
        for k, v in config_data.items():
            if k == "SIGNAL_WEIGHTS" and isinstance(v, dict):
                config_form.markdown("#### SIGNAL_WEIGHTS (individual fields)")
                config_inputs[k] = {}
                for w_key, w_val in v.items():
                    input_val = config_form.text_input(f"SIGNAL_WEIGHTS: {w_key}", value=str(w_val))
                    try:
                        float_val = float(input_val)
                    except Exception:
                        float_val = 0.0
                    config_inputs[k][w_key] = float_val
                    signal_weights_sum += float_val
                config_form.markdown(f"**Total SIGNAL_WEIGHTS sum:** {signal_weights_sum:.4f}")
            elif isinstance(v, bool):
                config_inputs[k] = config_form.checkbox(f"{k}", value=v)
            elif isinstance(v, (int, float)):
                config_inputs[k] = config_form.text_input(f"{k}", value=str(v))
            elif isinstance(v, dict):
                config_inputs[k] = config_form.text_area(f"{k} (JSON)", value=json.dumps(v, indent=2))
            else:
                config_inputs[k] = config_form.text_input(f"{k}", value=str(v))
        submitted = config_form.form_submit_button("Save Config")
        if submitted:
            for k in config_data:
                if k == "SIGNAL_WEIGHTS" and isinstance(config_data[k], dict):
                    config_data[k] = config_inputs[k]
                elif isinstance(config_data[k], bool):
                    config_data[k] = config_inputs[k]
                elif isinstance(config_data[k], (int, float)):
                    try:
                        config_data[k] = type(config_data[k])(config_inputs[k])
                    except Exception:
                        config_data[k] = config_inputs[k]
                elif isinstance(config_data[k], dict):
                    try:
                        config_data[k] = json.loads(config_inputs[k])
                    except Exception:
                        pass
                else:
                    config_data[k] = config_inputs[k]
            with open(TRADER_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
            st.success("Config updated.")
            load_trader_config()
            st.experimental_rerun()
    else:
        st.info("No config found.")
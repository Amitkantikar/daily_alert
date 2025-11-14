import yfinance as yf
import requests
from datetime import datetime
import pandas as pd
import config
import os
import time

# ==============================================================
# TELEGRAM CONFIG
# ==============================================================
TELEGRAM_BOT_TOKEN = config.BOT_TOKEN
TELEGRAM_CHAT_ID = config.CHAT_ID

# Path for storing log data
LOG_FILE = "ath_alert_log.csv"

# Alert threshold (percent distance from ATH). Set to 2.0 for 2%.
THRESHOLD_PCT = 2.0

# Minimum number of candles since the most recent ATH (require ATH to be older than this)
MIN_CANDLES_SINCE_ATH = 10


def send_telegram_alert(message: str):
    """Send alert message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload, timeout=15)
        if response.status_code == 200:
            print("✅ Telegram alert sent successfully!")
            return True
        else:
            print(f"❌ Failed to send alert: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")
        return False


def append_to_csv(file_path, data_dict):
    """Append a single record (dictionary) to CSV file."""
    df = pd.DataFrame([data_dict])
    file_exists = os.path.isfile(file_path)
    if not file_exists:
        df.to_csv(file_path, index=False)
    else:
        df.to_csv(file_path, mode="a", header=False, index=False)


# ==============================================================
# STOCK CHECK (returns tuple: (symbol, is_alert_sent, log_record))
# ==============================================================
def check_all_time_high_once(symbol: str, threshold_pct: float = THRESHOLD_PCT, min_candles_since_ath: int = MIN_CANDLES_SINCE_ATH):
    """
    Fetch historical data once, compute ATH and whether current price is within threshold_pct of ATH.
    Only send alert if:
      - current_price < ATH (strictly less)
      - diff_percent <= threshold_pct
      - the most recent ATH occurred more than min_candles_since_ath candles ago
    Returns: (symbol, alert_sent: bool, log_data: dict)
    """
    try:
        data = yf.download(symbol, period="max", interval="1d", auto_adjust=True, progress=False)
        if data.empty:
            print(f"⚠️ No data found for {symbol}")
            return symbol, False, None

        # Handle possible multi-index columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        current_price = float(data["Close"].iloc[-1])
        all_time_high = float(data["High"].max())

        # percent below ATH (0 if at or above ATH)
        if current_price >= all_time_high:
            diff_percent = 0.0
        else:
            diff_percent = ((all_time_high - current_price) / all_time_high) * 100

        # Find most recent index (position) where High == ATH
        ath_positions = data.index[data["High"] == all_time_high]
        if len(ath_positions) == 0:
            # unexpected but handle
            candles_since_ath = None
        else:
            # most recent ATH occurrence
            last_ath_index = ath_positions[-1]
            # integer position of that index in the dataframe
            last_ath_pos = data.index.get_loc(last_ath_index)
            # candles since ATH: number of rows after last_ath_pos until the latest row
            candles_since_ath = (len(data) - 1) - last_ath_pos

        print(f"{symbol} | Current: {current_price:.2f} | ATH: {all_time_high:.2f} | Diff: {diff_percent:.2f}% | Candles since ATH: {candles_since_ath}")

        alert_sent = False

        # Conditions:
        # 1) current price strictly less than ATH
        # 2) within threshold percent of ATH (diff_percent <= threshold_pct)
        # 3) most recent ATH occurred more than min_candles_since_ath candles ago
        condition_price_below_ath = current_price < all_time_high
        condition_within_pct = diff_percent <= threshold_pct
        condition_candles = (candles_since_ath is not None) and (candles_since_ath > min_candles_since_ath)

        should_alert = condition_price_below_ath and condition_within_pct and condition_candles

        if should_alert:
            message = (
                f"🚨 {symbol} is within {threshold_pct:.2f}% of its All-Time High (but below ATH)!\n"
                f"Current Price: {current_price:.2f}\n"
                f"ATH: {all_time_high:.2f}\n"
                f"Difference from ATH: {diff_percent:.2f}%\n"
                f"Candles since last ATH: {candles_since_ath}\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            alert_sent = send_telegram_alert(message)
        else:
            # for debugging/logging, print which condition failed
            fail_reasons = []
            if not condition_price_below_ath:
                fail_reasons.append("current >= ATH")
            if not condition_within_pct:
                fail_reasons.append(f"diff_pct > {threshold_pct}")
            if not condition_candles:
                if candles_since_ath is None:
                    fail_reasons.append("no ATH position found")
                else:
                    fail_reasons.append(f"candles_since_ath <= {min_candles_since_ath}")
            print(f"→ No alert for {symbol}. Reasons: {', '.join(fail_reasons)}")

        log_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "current_price": current_price,
            "ath": all_time_high,
            "diff_percent": diff_percent,
            "candles_since_ath": candles_since_ath,
            "alert_sent": alert_sent
        }

        append_to_csv(LOG_FILE, log_data)
        return symbol, alert_sent, log_data

    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")
        return symbol, False, None


# ==============================================================
# MAIN
# ==============================================================
if __name__ == "__main__":
    stock_list = config.NIFTY50_STOCKS  # e.g., ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    alerted_symbols = []
    processed = 0

    print(f"\n📈 Checking All-Time Highs — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("======================================================\n")

    for i, stock in enumerate(stock_list, 1):
        print(f"[{i}/{len(stock_list)}] Scanning {stock}...")
        symbol, alert_sent, log = check_all_time_high_once(stock, threshold_pct=THRESHOLD_PCT, min_candles_since_ath=MIN_CANDLES_SINCE_ATH)
        processed += 1
        if alert_sent:
            alerted_symbols.append(stock)

        # sleep 1s to avoid hitting rate limits
        time.sleep(1)

    # Summary message
    summary_msg = (
        f"✅ ATH Alert Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"Total Stocks Checked: {processed}\n"
        f"Alerts Sent: {len(alerted_symbols)}\n"
        f"Stocks Alerted: {', '.join(alerted_symbols) if alerted_symbols else 'None'}"
    )
    send_telegram_alert(summary_msg)

    print("\n✅ All stocks processed — results saved to:", LOG_FILE)

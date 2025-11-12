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
# STOCK CHECK (returns tuple: (symbol, is_near_ath, log_record))
# ==============================================================  
def check_all_time_high_once(symbol: str, threshold_pct: float = THRESHOLD_PCT):
    """
    Fetch historical data once, compute ATH and whether current price is within threshold_pct of ATH.
    Returns: (symbol, is_near_ath: bool, log_data: dict)
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

        print(f"{symbol} | Current: {current_price:.2f} | ATH: {all_time_high:.2f} | Diff: {diff_percent:.2f}%")

        alert_sent = False
        is_near = diff_percent <= threshold_pct

        if is_near:
            message = (
                f"🚨 {symbol} is within {threshold_pct:.2f}% of its All-Time High!\n"
                f"Current Price: {current_price:.2f}\n"
                f"ATH: {all_time_high:.2f}\n"
                f"Difference from ATH: {diff_percent:.2f}%\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            alert_sent = send_telegram_alert(message)

        log_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "current_price": current_price,
            "ath": all_time_high,
            "diff_percent": diff_percent,
            "alert_sent": alert_sent
        }

        append_to_csv(LOG_FILE, log_data)
        return symbol, is_near, log_data

    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")
        return symbol, False, None


# ==============================================================  
# MAIN  
# ==============================================================  
if __name__ == "__main__":
    stock_list = config.NIFTY50_STOCKS  # e.g., ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    near_ath_symbols = []
    processed = 0

    print(f"\n📈 Checking All-Time Highs — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("======================================================\n")

    for i, stock in enumerate(stock_list, 1):
        print(f"[{i}/{len(stock_list)}] Scanning {stock}...")
        symbol, is_near, log = check_all_time_high_once(stock, threshold_pct=THRESHOLD_PCT)
        processed += 1
        if is_near:
            near_ath_symbols.append(stock)

        # sleep 1s to avoid hitting rate limits
        time.sleep(1)

    # Summary message
    summary_msg = (
        f"✅ ATH Alert Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"Total Stocks Checked: {processed}\n"
        f"Near ATH (≤{THRESHOLD_PCT:.2f}%): {len(near_ath_symbols)}\n"
        f"Stocks: {', '.join(near_ath_symbols) if near_ath_symbols else 'None'}"
    )
    send_telegram_alert(summary_msg)

    print("\n✅ All stocks processed — results saved to:", LOG_FILE)

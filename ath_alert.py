import yfinance as yf
import requests
from datetime import datetime
import pandas as pd
import config
import os

# ==============================================================
# TELEGRAM CONFIG
# ==============================================================
TELEGRAM_BOT_TOKEN = config.BOT_TOKEN
TELEGRAM_CHAT_ID = config.CHAT_ID

# Path for storing log data
LOG_FILE = "ath_alert_log.csv"


def send_telegram_alert(message: str):
    """Send alert message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("✅ Telegram alert sent successfully!")
        else:
            print(f"❌ Failed to send alert: {response.text}")
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")


# ==============================================================
# STOCK ANALYSIS LOGIC
# ==============================================================
def check_all_time_high(symbol: str):
    """
    Fetch max available historical data for the symbol,
    check if the current price is within 0.5% of all-time high,
    log result to CSV, and send Telegram alert if yes.
    """
    try:
        # Fetch historical data (max available)
        data = yf.download(symbol, period="max", interval="1d", auto_adjust=True, progress=False)

        if data.empty:
            print(f"⚠️ No data found for {symbol}")
            return

        # Handle possible multi-index columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Extract current price & all-time high as floats
        current_price = float(data["Close"].iloc[-1])
        all_time_high = float(data["High"].max())
        diff_percent = ((all_time_high - current_price) / all_time_high) * 100

        # Log output
        print(f"{symbol} | Current: {current_price:.2f} | ATH: {all_time_high:.2f} | Diff: {diff_percent:.2f}%")

        alert_sent = False

        # Check alert condition
        if diff_percent <= 0.5:
            message = (
                f"🚨 {symbol} is near All-Time High!\n"
                f"Current Price: {current_price:.2f}\n"
                f"ATH: {all_time_high:.2f}\n"
                f"Difference: {diff_percent:.2f}%\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram_alert(message)
            alert_sent = True
        else:
            print("No alert — price not near ATH.")

        # Save to log file
        log_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "current_price": current_price,
            "ath": all_time_high,
            "diff_percent": diff_percent,
            "alert_sent": alert_sent
        }

        append_to_csv(LOG_FILE, log_data)

    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")


# ==============================================================
# CSV LOGGING FUNCTION
# ==============================================================
def append_to_csv(file_path, data_dict):
    """Append a single record (dictionary) to CSV file."""
    df = pd.DataFrame([data_dict])
    file_exists = os.path.isfile(file_path)

    if not file_exists:
        df.to_csv(file_path, index=False)
    else:
        df.to_csv(file_path, mode='a', header=False, index=False)


# ==============================================================
# MAIN SCRIPT EXECUTION
# ==============================================================
if __name__ == "__main__":
    stock_list = config.NIFTY50_STOCKS
    near_ath = []

    print(f"\n📈 Checking All-Time Highs — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("======================================================\n")

    for stock in stock_list:
        try:
            data = yf.download(stock, period="max", interval="1d", auto_adjust=True, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            current_price = float(data["Close"].iloc[-1])
            all_time_high = float(data["High"].max())
            diff_percent = ((all_time_high - current_price) / all_time_high) * 100

            if diff_percent <= 0.5:
                near_ath.append(stock)

        except Exception as e:
            print(f"⚠️ Error fetching {stock}: {e}")

    summary_msg = (
        f"✅ ATH Alert Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"Total Stocks Checked: {len(stock_list)}\n"
        f"Near ATH (≤0.5%): {len(near_ath)}\n"
        f"Stocks: {', '.join(near_ath) if near_ath else 'None'}"
    )
    send_telegram_alert(summary_msg)

    print("\n✅ All stocks processed — results saved to:", LOG_FILE)

    for stock in stock_list:
        check_all_time_high(stock)

    print("\n✅ All stocks processed — results saved to:", LOG_FILE)


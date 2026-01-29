import os
import re
import sys
import time
import imaplib
import email
import datetime
from email.header import decode_header

try:
    from huckleberry_api import HuckleberryAPI
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "huckleberry-api"])
    from huckleberry_api import HuckleberryAPI

# ==========================================
# 🔐 CREDENTIALS
# ==========================================
HUCKLE_EMAIL = os.environ["HUCKLE_EMAIL"]
HUCKLE_PASS = os.environ["HUCKLE_PASS"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASS"]
TIMEZONE = "America/Toronto"

# ==========================================
# 🔧 THE TIME MACHINE
# ==========================================
class TimeMachine:
    current_dt = datetime.datetime.now()
    @staticmethod
    def set_time(date_str, time_str):
        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M%p")
        TimeMachine.current_dt = dt

class FakeDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None): return TimeMachine.current_dt
    @classmethod
    def utcnow(cls): return TimeMachine.current_dt

def apply_patches():
    for name, module in list(sys.modules.items()):
        if "huckleberry" in name:
            if hasattr(module, 'datetime'): setattr(module, 'datetime', FakeDatetime)
            if hasattr(module, 'time'):
                class FakeTimeModule:
                    @staticmethod
                    def time(): return TimeMachine.current_dt.timestamp()
                    @staticmethod
                    def sleep(s): time.sleep(s)
                setattr(module, 'time', FakeTimeModule)

# ==========================================
# 📧 FUTURE-PROOF GMAIL FETCHER
# ==========================================
def fetch_unread_report():
    print(f"📧 Connecting to Gmail ({GMAIL_USER})...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        # 1. Select 'All Mail'
        try:
            mail.select('"[Gmail]/All Mail"')
        except:
            print("⚠️ Could not find 'All Mail'. Checking Inbox.")
            mail.select("inbox")
        
        # 2. BROAD SEARCH: Find ANY Unread email

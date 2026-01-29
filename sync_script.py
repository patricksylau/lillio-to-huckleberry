import os
import re
import sys
import time
import imaplib
import email
import datetime
from email.header import decode_header

# Install library automatically if missing (Simulates pip install)
try:
    from huckleberry_api import HuckleberryAPI
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "huckleberry-api"])
    from huckleberry_api import HuckleberryAPI

# ==========================================
# 🔐 CREDENTIALS (Loaded from GitHub Secrets)
# ==========================================
HUCKLE_EMAIL = os.environ["HUCKLE_EMAIL"]
HUCKLE_PASS = os.environ["HUCKLE_PASS"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASS"]

# CONFIGURATION
TIMEZONE = "America/Toronto"
SEARCH_SUBJECT = "Saanvi's Report"

# ==========================================
# 🔧 THE TIME MACHINE (Search & Destroy)
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
# 📧 DEBUG GMAIL FETCHER
# ==========================================
def fetch_unread_report():
    print(f"📧 Connecting to Gmail ({GMAIL_USER})...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        # 1. Try to select 'All Mail'. If it fails, fallback to Inbox.
        try:
            mail.select('"[Gmail]/All Mail"')
            print("📂 Selected '[Gmail]/All Mail'")
        except:
            print("⚠️ Could not find 'All Mail'. Falling back to 'Inbox'.")
            mail.select("inbox")
        
        # 2. BROAD SEARCH: Just look for "Saanvi" (Avoids apostrophe issues)
        # We also look for UNSEEN (Unread).
        print(f"🔍 Searching for UNREAD emails with 'Saanvi' in subject...")
        status, messages = mail.search(None, '(UNSEEN SUBJECT "Saanvi")')
        
        if not messages[0]:
            print("❌ No unread 'Saanvi' emails found.")
            print("   (Double check: Is the email actually marked Unread?)")
            
            # DEBUG: Let's see if we can find it even if it IS Read, just to prove it exists.
            print("🕵️ DEBUG SEARCH: Looking for READ emails...")
            status, debug_msgs = mail.search(None, '(SUBJECT "Saanvi")')
            if debug_msgs[0]:
                print(f"   💡 Found {len(debug_msgs[0].split())} READ emails. The robot only looks for UNREAD ones.")
            else:
                print("   ❌ Zero emails found. The subject might be different.")
            return None, None
            
        # 3. PROCESS THE LATEST ONE
        latest_id = messages[0].split()[-1]
        status, msg_data = mail.fetch(latest_id, "(RFC822)")
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                print(f"✅ Found Email: '{subject}'")
                
                # Extract Body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()
                
                return body, subject
                
    except Exception as e:
        print(f"❌ Gmail Error: {e}")
        return None, None
        
# ==========================================
# 🚀 MAIN PROCESS
# ==========================================
def process_log():
    raw_content, subject = fetch_latest_report()
    if not raw_content: return

    # Extract Date
    match = re.search(r"Report - \w+, (\w+ \d+)", raw_content)
    if match:
        date_part = match.group(1)
        current_year = datetime.datetime.now().year
        FIXED_DATE = datetime.datetime.strptime(f"{current_year} {date_part}", "%Y %b %d").strftime("%Y-%m-%d")
        print(f"📅 Report Date Detected: {FIXED_DATE}")
    else:
        print("⚠️ Could not detect date. Using Today.")
        FIXED_DATE = datetime.datetime.now().strftime("%Y-%m-%d")

    print(f"🚀 Starting Sync for {FIXED_DATE}...")
    
    # Patch & Login
    apply_patches()
    try:
        client = HuckleberryAPI(email=HUCKLE_EMAIL, password=HUCKLE_PASS, timezone=TIMEZONE)
        children = client.get_children()
        if not children: return
        child_id = children[0]['uid']
        print(f"✅ Connected for: {children[0].get('name', 'Baby')}")
    except Exception as e:
        print(f"❌ Login Failed: {e}")
        return

    # A. NAPS
    naps = re.findall(r'(\d{1,2}:\d{2}[ap]m)\s*-\s*(\d{1,2}:\d{2}[ap]m)', raw_content)
    for start_str, end_str in naps:
        print(f"   💤 Nap: {start_str} - {end_str}...", end=" ")
        try:
            TimeMachine.set_time(FIXED_DATE, start_str)
            client.start_sleep(child_id)
            time.sleep(1)
            TimeMachine.set_time(FIXED_DATE, end_str)
            client.complete_sleep(child_id)
            print("✅")
        except Exception as e: print(f"⚠️ {e}")

    # B. DIAPERS
    diaper_lines = re.findall(r'(\d{1,2}:\d{2}[ap]m) - Diaper - (.*)', raw_content)
    for time_str, details in diaper_lines:
        if "Bowel movement" in details: dtype = "poo"
        elif "Wet" in details: dtype = "pee"
        else: dtype = "dry"
        print(f"   🧷 Diaper ({dtype}): {time_str}...", end=" ")
        try:
            TimeMachine.set_time(FIXED_DATE, time_str)
            client.log_diaper(child_id, dtype)
            print("✅")
        except Exception as e: print(f"⚠️ {e}")

    # C. BOTTLE REMINDER (Prints to logs only)
    print("\n📝 MANUAL BOTTLES REMINDER:")
    milk_lines = re.findall(r'(\d{1,2}:\d{2}[ap]m) - (\d+)\s*oz', raw_content)
    for time_str, amount in milk_lines:
        print(f"   [ ] {amount} oz Milk at {time_str}")

if __name__ == "__main__":
    process_log()

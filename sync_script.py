import os
import re
import sys
import time
import imaplib
import email
import datetime
import email.utils
from email.header import decode_header

# Install library automatically
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
# 📧 GMAIL FETCHER (Robust Date & Sender)
# ==========================================
def fetch_unread_report():
    print(f"📧 Connecting to Gmail ({GMAIL_USER})...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        # 1. Select Folder
        try:
            mail.select('"[Gmail]/All Mail"')
        except Exception:
            print("⚠️ Could not find 'All Mail'. Checking Inbox.")
            mail.select("inbox")
        
        # 2. BROAD SEARCH
        print(f"🔍 Searching for UNREAD emails with 'Saanvi' in subject...")
        status, messages = mail.search(None, '(UNSEEN SUBJECT "Saanvi")')
        
        if not messages or not messages[0]:
            print("❌ No unread 'Saanvi' emails found.")
            return None, None, None
            
        # 3. FILTER LOOP
        email_ids = messages[0].split()
        
        for e_id in reversed(email_ids):
            # Fetch Header
            _, msg_header = mail.fetch(e_id, '(RFC822.HEADER)')
            header_msg = email.message_from_bytes(msg_header[0][1])
            sender = header_msg.get("From", "").lower()
            
            print(f"   🔎 Checking sender: {sender}")
            
            if "himama.com" in sender or "lillio.com" in sender:
                print("   ✅ Valid Sender Found!")
                
                # Fetch Body
                _, msg_data = mail.fetch(e_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Extract Date from Email Header (The Truth)
                email_date_str = msg.get("Date")
                parsed_date = email.utils.parsedate_to_datetime(email_date_str)
                # Convert to YYYY-MM-DD string
                clean_date = parsed_date.strftime("%Y-%m-%d")
                print(f"   📅 Email Timestamp: {clean_date}")
                
                # Decode Subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                # Extract Text
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()
                
                return body, subject, clean_date
            else:
                print("   ⚠️ Skipping (Sender not allowed)")
        
        print("❌ No emails found from valid senders.")
        return None, None, None

    except Exception as e:
        print(f"❌ Gmail Error: {e}")
        return None, None, None

# ==========================================
# 🚀 MAIN PROCESS
# ==========================================
def process_log():
    # Now getting Date directly from the email metadata
    raw_content, subject, email_date = fetch_unread_report()
    if not raw_content: return

    # Use the email's date as the Source of Truth
    FIXED_DATE = email_date
    print(f"🚀 Starting Sync for {FIXED_DATE}...")
    
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

if __name__ == "__main__":
    process_log()

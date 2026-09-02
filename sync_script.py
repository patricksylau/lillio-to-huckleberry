import asyncio
import os
import re
import sys
import imaplib
import email
import datetime
import email.utils
from email.header import decode_header
from zoneinfo import ZoneInfo

try:
    import aiohttp
    from huckleberry_api import HuckleberryAPI
    from huckleberry_api.firebase_types import FirebaseSleepDetails
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "huckleberry-api"])
    import aiohttp
    from huckleberry_api import HuckleberryAPI
    from huckleberry_api.firebase_types import FirebaseSleepDetails

# ==========================================
# 🔐 CREDENTIALS
# ==========================================
HUCKLE_EMAIL = os.environ["HUCKLE_EMAIL"]
HUCKLE_PASS = os.environ["HUCKLE_PASS"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASS"]
TIMEZONE = "America/Toronto"

# ==========================================
# 📧 GMAIL FETCHER (Sender-First Search)
# ==========================================
def fetch_unread_report():
    print(f"📧 Connecting to Gmail ({GMAIL_USER})...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        # 1. Select 'All Mail'
        try:
            mail.select('"[Gmail]/All Mail"')
        except Exception:
            print("⚠️ Could not find 'All Mail'. Checking Inbox.")
            mail.select("inbox")
        
        # 2. SEARCH STRATEGY: Look for Sender directly
        # We try HiMama first, then Lillio.
        targets = ['(UNSEEN FROM "himama.com")', '(UNSEEN FROM "lillio.com")']
        found_id = None
        
        for query in targets:
            print(f"🔍 Searching: {query}...")
            status, messages = mail.search(None, query)
            if messages and messages[0]:
                # Found one! Take the latest.
                found_id = messages[0].split()[-1]
                print("   ✅ Found matching email!")
                break
        
        if not found_id:
            print("❌ No unread emails found from himama.com or lillio.com")
            return None, None, None

        # 3. FETCH & PROCESS
        status, msg_data = mail.fetch(found_id, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Extract Date (The Truth)
                email_date_str = msg.get("Date")
                parsed_date = email.utils.parsedate_to_datetime(email_date_str)
                clean_date = parsed_date.strftime("%Y-%m-%d")
                print(f"   📅 Email Date: {clean_date}")
                
                # Decode Subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                # Extract Body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()
                
                return body, subject, clean_date

    except Exception as e:
        print(f"❌ Gmail Error: {e}")
        return None, None, None

# ==========================================
# 🚀 MAIN PROCESS
# ==========================================
def event_datetime(date_str, time_str):
    return datetime.datetime.strptime(
        f"{date_str} {time_str}", "%Y-%m-%d %I:%M%p"
    ).replace(tzinfo=ZoneInfo(TIMEZONE))


async def process_log():
    raw_content, subject, email_date = fetch_unread_report()
    if not raw_content:
        return

    fixed_date = email_date
    print(f"🚀 Starting Sync for {fixed_date}...")

    try:
        async with aiohttp.ClientSession() as websession:
            client = HuckleberryAPI(
                email=HUCKLE_EMAIL,
                password=HUCKLE_PASS,
                timezone=TIMEZONE,
                websession=websession,
            )
            await client.authenticate()
            user = await client.get_user()
            if not user or not user.childList:
                print("❌ No children found in the Huckleberry account")
                return

            child_id = user.childList[0].cid
            print(f"✅ Connected for child ID: {child_id}")

            await sync_events(client, child_id, raw_content, fixed_date)
    except Exception as e:
        print(f"❌ Login Failed: {e}")


async def sync_events(client, child_id, raw_content, fixed_date):

    # A. NAPS
    naps = re.findall(r'(\d{1,2}:\d{2}[ap]m)\s*-\s*(\d{1,2}:\d{2}[ap]m)', raw_content)
    for start_str, end_str in naps:
        print(f"   💤 Nap: {start_str} - {end_str}...", end=" ")
        try:
            await client.log_sleep(
                child_id,
                start_time=event_datetime(fixed_date, start_str),
                end_time=event_datetime(fixed_date, end_str),
                details=FirebaseSleepDetails(notes="[Daycare]"),
            )
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
            await client.log_diaper(
                child_id,
                start_time=event_datetime(fixed_date, time_str),
                mode=dtype,
                notes="[Daycare]",
            )
            print("✅")
        except Exception as e: print(f"⚠️ {e}")

    # C. BOTTLES
    bottle_lines = re.findall(
        r"(\d{1,2}:\d{2}[ap]m)\s*-\s*(\d+(?:\.\d+)?)\s*(ml|oz)\s*-\s*([^\r\n]+)",
        raw_content,
        flags=re.IGNORECASE,
    )
    for time_str, amount, units, details in bottle_lines:
        bottle_type = details.strip(" -:") or "Formula"
        print(f"   🍼 Bottle ({amount} {units} {bottle_type}): {time_str}...", end=" ")
        try:
            await client.log_bottle(
                child_id,
                start_time=event_datetime(fixed_date, time_str),
                amount=float(amount),
                bottle_type=bottle_type,
                units=units.lower(),
            )
            print("✅")
        except Exception as e: print(f"⚠️ {e}")

if __name__ == "__main__":
    asyncio.run(process_log())

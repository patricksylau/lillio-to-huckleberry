# 🍼 Lillio (HiMama) to Huckleberry Auto-Sync

**Automate your baby tracking.** This tool listens for daily report emails from **Lillio (formerly HiMama)** and automatically logs Naps and Diapers into the **Huckleberry** app.

It runs entirely in the cloud using **GitHub Actions**, so you don't need to keep your computer on.

## ✨ Features
* **Zero-Touch Automation:** Runs automatically every evening.
* **Smart Syncing:** Only processes **Unread** emails to prevent duplicate entries.
* **Timezone Aware:** Correctly handles dates even if the server is in a different timezone.
* **Zero Inbox Support:** Works even if you auto-archive your emails to a label (searches "All Mail").
* **Secure:** Uses GitHub Secrets so your passwords are never visible in the code.

## 🚀 Setup Instructions

### 1. Fork or Copy this Repo
Click the **Fork** button at the top right to create your own copy of this repository, or create a new private repository and copy the files manually.

### 2. Configure Gmail
To allow the script to read your emails securely, you need an **App Password**:
1.  Go to your [Google Account Security](https://myaccount.google.com/security).
2.  Enable **2-Step Verification** (if not already on).
3.  Search for **"App Passwords"** and create one named "Huckleberry Script".
4.  **Copy the 16-character code.** You will need this in the next step.

### 3. Add GitHub Secrets
Go to your repository **Settings** > **Secrets and variables** > **Actions**. Click **New repository secret** and add these four:

| Secret Name | Value |
| :--- | :--- |
| `GMAIL_USER` | Your Gmail address (e.g., `parent@gmail.com`) |
| `GMAIL_APP_PASS` | The 16-character App Password you just generated |
| `HUCKLE_EMAIL` | Your Huckleberry login email |
| `HUCKLE_PASS` | Your Huckleberry password |

## 🕒 Adjusting Time Zones

You need to adjust two files to match your local time. The default is set for **Eastern Time (Toronto/New York)**.

### 1. Adjust the Script Timezone
This ensures the log entries in Huckleberry appear at the correct local time.
1.  Open `sync_script.py`.
2.  Find this line near the top:
    ```python
    TIMEZONE = "America/Toronto"
    ```
3.  Change it to your timezone (e.g., `America/Los_Angeles`, `Europe/London`).

### 2. Adjust the "Evening Window" (The Schedule)
This determines when the robot wakes up to check your email. GitHub uses **UTC time**.

1.  Open `.github/workflows/daily_run.yml`.
2.  Find the `cron` line:
    ```yaml
    - cron: '*/30 21-23,0 * * *'
    ```
    * `*/30` means "Run every 30 minutes".
    * `21-23,0` are the hours in UTC.
3.  **Calculate your hours:**
    * **EST (Toronto/NY):** 4 PM = 21:00 UTC.
    * **PST (Los Angeles):** 4 PM = 00:00 UTC.
    * **GMT (London):** 4 PM = 16:00 UTC.
4.  Update the numbers to cover the 3-4 hours *after* you usually receive your report.

## 🛠️ How it Works
1.  **Trigger:** Every 30 minutes in the evening window, the script wakes up.
2.  **Fetch:** It checks your Gmail (specifically `[Gmail]/All Mail`) for any **UNREAD** email from `no-reply@himama.com` or `no-reply@lillio.com` containing "Saanvi" (or your child's name).
3.  **Parse:** It extracts the specific date, nap times, and diaper changes from the email body.
4.  **Log:** It logs in to Huckleberry and sends the data.
5.  **Finish:** It marks the email as **Read** to ensure it never logs the same day twice.

## ⚠️ Disclaimer
This is an unofficial tool and is not affiliated with Lillio (HiMama) or Huckleberry Labs. Use at your own risk.

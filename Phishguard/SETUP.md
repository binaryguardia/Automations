# PhishGuard India v3.0 — Setup & Run Guide

<img width="1910" height="913" alt="image" src="https://github.com/user-attachments/assets/f0a1c005-a50a-4695-9fb9-71f2a5751d40" />

## ONE LINE START
```
git clone https://github.com/binaryguardia/Automations.git
cd Automations/Phishguard
sudo bash start.sh
```
## QUICK START (3 steps)

### Step 1 — Install Python dependencies
```
pip install flask flask-cors selenium webdriver-manager requests beautifulsoup4 pandas openpyxl
```

### Step 2 — Start the backend server
```
python server.py
```
You will see:
```
PhishGuard India — Backend Server v2.0
Starting server on: http://localhost:5000
```

### Step 3 — Open the dashboard
Open `index.html` in Chrome or Edge.
The green dot will appear confirming backend is connected.

---

## HOW APK DETECTION WORKS

When you click "Investigate" on a URL, the backend:

1. Launches a real headless Chrome browser
2. Opens the URL with a mobile User-Agent (Android/Pixel)
3. Waits for all JavaScript to execute (8 seconds)
4. Scrolls the page to trigger lazy-loaded content
5. Scans ALL page elements for .apk links in:
   - href, src, data-url, data-href, data-download attributes
   - onclick handlers and JavaScript code
   - Raw HTML text patterns
   - Network request logs (catches XHR/fetch downloads)
6. Clicks every element matching "download", "install", "get app" text
7. Intercepts any .apk URLs triggered by those clicks
8. Downloads the APK file with wget-style streaming
9. Saves SHA-256 hash for court evidence
10. Saves: page_source.html + screenshot.png + metadata.json + APK file

## Evidence Folder Structure
```
PhishGuard_Evidence/
  mamabets.co_20260410_143022/
    metadata.json              ← Full investigation data
    investigation_report.txt  ← Human-readable report
    page_source.html          ← Full JS-rendered page HTML
    screenshot.png            ← Page screenshot
    app_release.apk           ← Downloaded APK (if found)
    complaint_data.json       ← Original NCRP row data
  MASTER_REPORT.csv           ← Summary of all investigations
```

## For Betting Sites like mamabets.co
These sites serve APKs via JavaScript button clicks.
The Selenium crawler handles this by:
- Using Android mobile UA (triggers mobile download UI)
- Clicking the "Download App" button
- Capturing the triggered APK URL from network logs
- Downloading the file before the browser closes

## Requirements
- Python 3.8+
- Google Chrome installed
- ChromeDriver (auto-installed by webdriver-manager)
- Windows / Linux / macOS supported

#!/usr/bin/env python3
"""
PhishGuard India — Backend API Server (v2 UI compatible, v3 engine inside)
=======================================================================

This server keeps the same API shape used by your existing `index.html`
while upgrading the engine to v3:
- Sequential queue (1 job at a time to save resources)
- Passive recon (DNS/SSL/redirect chain)
- Full domain crawl (BFS internal links)
- APK forensics (SHA256/MD5, package best-effort)
- Optional external checks: VirusTotal + urlscan.io (API keys)
- Operator controls: cancel/resume
"""

import os
import re
import json
import time
import shutil
import hashlib
import logging
import threading
import traceback
import socket
import ssl
import csv
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests as req_lib
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
BASE_DIR = Path("PhishGuard_Evidence")
LOG_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"
CHROME_DL_DIR = str(Path.home() / "PhishGuard_Downloads")

PAGE_WAIT = 8
SCROLL_STEPS = 6
CLICK_WAIT = 4
MAX_APK_MB = 300

MAX_PAGES_PER_DOMAIN = 50
CRAWL_TIMEOUT = 300
MAX_LINK_DEPTH = 3

VT_API_KEY = os.environ.get("7ba314959045d28899abadd0797568935ca8a6d3485fa29380af01a2044998f2", "").strip()
URLSCAN_API_KEY = os.environ.get("019d867a-1fde-7209-8187-30222ff399c4", "").strip()

SAFE_DOMAIN_ALLOWLIST = {
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com",
    "google.com", "www.google.com",
    "youtube.com", "www.youtube.com",
    "whatsapp.com", "www.whatsapp.com",
    "microsoft.com", "www.microsoft.com",
    "apple.com", "www.apple.com",
    "play.google.com",
}

HIGH_RISK_TLDS = {
    ".xyz", ".top", ".click", ".tk", ".ml", ".ga", ".work", ".loan",
    ".icu", ".buzz", ".vip", ".live", ".online", ".site", ".website",
    ".space", ".fun", ".store", ".shop", ".club", ".info",
}

MALICIOUS_FILE_TYPES = [
    ".apk", ".ipa", ".exe", ".msi", ".bat", ".ps1", ".vbs", ".jar",
    ".dex", ".so", ".dll", ".cmd", ".scr", ".pif", ".com",
]

PHISHING_KEYWORDS_EN = [
    "kyc update", "kyc verification", "verify your account", "account suspended",
    "otp verification", "enter otp", "confirm otp", "claim reward", "free gift",
    "earn money", "work from home", "investment return", "guaranteed return",
    "upi id", "scan qr", "pay now", "instant loan", "loan approved",
    "bank details", "card number", "cvv", "reset password",
    "bet", "casino", "satta", "matka", "download apk", "install app", "get app",
]
PHISHING_KEYWORDS_HI = ["kyc", "otp", "खाता", "बैंक", "पुरस्कार", "जीत", "लोन", "डाउनलोड", "इनाम", "आधार", "पैन"]

CRYPTO_MINING_PATTERNS = [r"coinhive", r"cryptonight", r"monero", r"xmrig", r"stratum\+tcp", r"nicehash"]
DECEPTIVE_JS_PATTERNS = [r"eval\s*\(\s*unescape\s*\(", r"eval\s*\(\s*atob\s*\(", r"String\.fromCharCode", r"\\x[0-9a-f]{2}"]

USER_AGENTS = {
    "android": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36"
    )
}

for d in [BASE_DIR, LOG_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
Path(CHROME_DL_DIR).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / f"server_{datetime.now():%Y%m%d}.log"), logging.StreamHandler()],
)
log = logging.getLogger("PhishGuard")

app = Flask(__name__, static_folder=".")
CORS(app)

JOBS: dict = {}
job_lock = threading.Lock()

JOB_QUEUE: deque = deque()
QUEUE_LOCK = threading.Lock()
QUEUE_WORKER_RUNNING = False


class JobCancelled(Exception):
    pass


def is_cancelled(job_id: str) -> bool:
    with job_lock:
        return bool((JOBS.get(job_id) or {}).get("cancelled"))


def _raise_if_cancelled(job_id: str):
    if is_cancelled(job_id):
        raise JobCancelled("cancelled")


def make_driver(download_dir: str, headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--allow-running-insecure-content")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(f"--user-agent={USER_AGENTS['android']}")
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    opts.add_experimental_option("prefs", prefs)
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    driver.execute_cdp_cmd("Network.enable", {})
    return driver


def passive_recon(domain: str) -> dict:
    recon = {"ip": None, "ssl_valid": None, "ssl_issuer": None, "redirect_chain": [], "flags": []}
    try:
        recon["ip"] = socket.gethostbyname(domain)
    except Exception:
        recon["flags"].append("DNS_FAIL")
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.create_connection((domain, 443), timeout=8), server_hostname=domain) as s:
            cert = s.getpeercert()
            issuer_dict = dict(x[0] for x in cert.get("issuer", []))
            recon["ssl_issuer"] = issuer_dict.get("organizationName", "Unknown")
            recon["ssl_valid"] = True
    except ssl.SSLCertVerificationError:
        recon["ssl_valid"] = False
        recon["flags"].append("SSL_INVALID")
    except Exception:
        recon["ssl_valid"] = None
        recon["flags"].append("NO_HTTPS")
    try:
        sess = req_lib.Session()
        resp = sess.get(f"https://{domain}", timeout=10, verify=False, allow_redirects=True, headers={"User-Agent": USER_AGENTS["android"]})
        recon["redirect_chain"] = [r.url for r in resp.history] + [resp.url]
        if len(recon["redirect_chain"]) > 3:
            recon["flags"].append(f"LONG_REDIRECT_{len(recon['redirect_chain'])}_HOPS")
    except Exception:
        pass
    return recon


def external_reputation_checks(clean_url: str) -> dict:
    checks = {
        "virustotal": {"enabled": bool(VT_API_KEY), "submitted": False, "analysis_id": None, "stats": None, "error": None},
        "urlscan": {"enabled": bool(URLSCAN_API_KEY), "submitted": False, "uuid": None, "result_url": None, "verdicts": None, "error": None},
    }

    # VirusTotal submit + quick poll (best-effort)
    if VT_API_KEY:
        try:
            resp = req_lib.post("https://www.virustotal.com/api/v3/urls", headers={"x-apikey": VT_API_KEY}, data={"url": clean_url}, timeout=12)
            if resp.status_code in (200, 201):
                js = resp.json()
                checks["virustotal"]["analysis_id"] = (js.get("data") or {}).get("id")
                checks["virustotal"]["submitted"] = True
                aid = checks["virustotal"]["analysis_id"]
                if aid:
                    for _ in range(3):
                        time.sleep(2)
                        ar = req_lib.get(f"https://www.virustotal.com/api/v3/analyses/{aid}", headers={"x-apikey": VT_API_KEY}, timeout=12)
                        if ar.status_code == 200:
                            aj = ar.json()
                            stats = (((aj.get("data") or {}).get("attributes") or {}).get("stats")) or None
                            if stats:
                                checks["virustotal"]["stats"] = stats
                                break
            else:
                checks["virustotal"]["error"] = f"HTTP {resp.status_code}"
        except Exception as e:
            checks["virustotal"]["error"] = str(e)[:160]

    # urlscan submit + quick poll (best-effort)
    if URLSCAN_API_KEY:
        try:
            resp = req_lib.post(
                "https://urlscan.io/api/v1/scan/",
                headers={"API-Key": URLSCAN_API_KEY, "Content-Type": "application/json"},
                json={"url": clean_url, "visibility": "private"},
                timeout=12,
            )
            if resp.status_code in (200, 201):
                js = resp.json()
                checks["urlscan"]["uuid"] = js.get("uuid")
                checks["urlscan"]["result_url"] = js.get("result")
                checks["urlscan"]["submitted"] = True
                rurl = checks["urlscan"]["result_url"]
                if rurl:
                    for _ in range(4):
                        time.sleep(2)
                        rr = req_lib.get(rurl, timeout=12)
                        if rr.status_code == 200:
                            rj = rr.json()
                            verdicts = (rj.get("verdicts") or None)
                            checks["urlscan"]["verdicts"] = verdicts
                            break
            else:
                checks["urlscan"]["error"] = f"HTTP {resp.status_code}"
        except Exception as e:
            checks["urlscan"]["error"] = str(e)[:160]

    return checks


def _click_download_buttons(driver, page_url: str, apk_set: set, job_id: str):
    selectors = [
        "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download')]",
        "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download')]",
        "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'install')]",
        "//a[contains(@href,'.apk')]",
        "//a[contains(@href,'download')]",
    ]
    for sel in selectors:
        _raise_if_cancelled(job_id)
        try:
            elements = driver.find_elements(By.XPATH, sel)
            for el in elements[:2]:
                _raise_if_cancelled(job_id)
                try:
                    href = el.get_attribute("href") or ""
                    if href and re.search(r"\.apk($|\?|#|&)", href, re.I):
                        apk_set.add(urljoin(page_url, href))
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.2)
                    try:
                        el.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", el)
                    time.sleep(CLICK_WAIT)
                except Exception:
                    pass
        except Exception:
            pass


def analyze_page(url: str, driver, job_id: str) -> dict:
    _raise_if_cancelled(job_id)
    findings = {"apk_links": set(), "malicious_links": set(), "phishing_keywords": [], "crypto_mining": False, "obfuscated_js": False, "login_form": False}
    full_html = driver.page_source
    soup = BeautifulSoup(full_html, "html.parser")
    full_text = soup.get_text(" ").lower()
    lhtml = full_html.lower()

    for tag in soup.find_all(True):
        for attr in ["href", "src", "data-url", "data-href", "data-download", "data-file", "action", "formaction"]:
            val = tag.get(attr, "")
            if not val:
                continue
            for ext in MALICIOUS_FILE_TYPES:
                if re.search(re.escape(ext) + r"($|\?|#|&)", val, re.I):
                    abs_link = urljoin(url, val)
                    if ext == ".apk":
                        findings["apk_links"].add(abs_link)
                    else:
                        findings["malicious_links"].add(abs_link)

    for kw in PHISHING_KEYWORDS_EN + PHISHING_KEYWORDS_HI:
        if kw in full_text:
            findings["phishing_keywords"].append(kw)

    for pattern in CRYPTO_MINING_PATTERNS:
        if re.search(pattern, lhtml, re.I):
            findings["crypto_mining"] = True
            break
    for pattern in DECEPTIVE_JS_PATTERNS:
        if re.search(pattern, full_html, re.I):
            findings["obfuscated_js"] = True
            break

    for form in soup.find_all("form"):
        inputs = form.find_all("input")
        has_pw = any(i.get("type", "").lower() == "password" for i in inputs)
        has_txt = any(i.get("type", "").lower() in ["text", "email", "tel", "number"] for i in inputs)
        if has_pw and has_txt:
            findings["login_form"] = True
            break

    return findings


def crawl_domain(start_url: str, job_id: str, ev_folder: Path, push_log, set_progress) -> dict:
    clean_url = start_url if start_url.startswith("http") else "https://" + start_url
    base_domain = urlparse(clean_url).netloc
    aggregate = {
        "pages_crawled": 0,
        "all_apk_links": set(),
        "all_malicious_links": set(),
        "all_phishing_keywords": set(),
        "login_forms": [],
        "crypto_mining_pages": [],
        "obfuscated_js_pages": [],
        "crawl_log": [],
    }
    visited = set()
    to_visit = deque([(clean_url, 0)])
    dl_folder = Path(CHROME_DL_DIR) / ev_folder.name
    dl_folder.mkdir(parents=True, exist_ok=True)
    driver = None
    crawl_start = time.time()
    try:
        driver = make_driver(str(dl_folder))
        while to_visit and aggregate["pages_crawled"] < MAX_PAGES_PER_DOMAIN:
            _raise_if_cancelled(job_id)
            if time.time() - crawl_start > CRAWL_TIMEOUT:
                break
            current_url, depth = to_visit.popleft()
            if current_url in visited:
                continue
            visited.add(current_url)
            aggregate["pages_crawled"] += 1
            aggregate["crawl_log"].append(current_url)
            set_progress(15 + int(70 * min(aggregate["pages_crawled"] / MAX_PAGES_PER_DOMAIN, 1.0)), f"Crawling {current_url[:60]}")
            try:
                driver.get(current_url)
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                except TimeoutException:
                    pass
                for i in range(SCROLL_STEPS):
                    _raise_if_cancelled(job_id)
                    driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/SCROLL_STEPS});")
                    time.sleep(0.5)
                driver.execute_script("window.scrollTo(0,0);")
                time.sleep(min(PAGE_WAIT, 4))

                if depth <= 2:
                    _click_download_buttons(driver, current_url, aggregate["all_apk_links"], job_id)

                findings = analyze_page(current_url, driver, job_id)
                aggregate["all_apk_links"].update(findings["apk_links"])
                aggregate["all_malicious_links"].update(findings["malicious_links"])
                aggregate["all_phishing_keywords"].update(findings["phishing_keywords"])
                if findings["login_form"]:
                    aggregate["login_forms"].append(current_url)
                if findings["crypto_mining"]:
                    aggregate["crypto_mining_pages"].append(current_url)
                if findings["obfuscated_js"]:
                    aggregate["obfuscated_js_pages"].append(current_url)

                if depth < MAX_LINK_DEPTH:
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = (a["href"] or "").strip()
                        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                            continue
                        abs_href = urljoin(current_url, href)
                        if urlparse(abs_href).netloc == base_domain and abs_href not in visited:
                            to_visit.append((abs_href, depth + 1))
            except JobCancelled:
                raise
            except Exception:
                continue
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
    for k in ["all_apk_links", "all_malicious_links", "all_phishing_keywords"]:
        aggregate[k] = list(aggregate[k])
    return aggregate


def download_apk_file(session, apk_url: str, ev_folder: Path, job_id: str) -> dict:
    out = {"url": apk_url, "success": False, "filename": None, "filepath": None, "size_mb": 0, "sha256": None, "md5": None, "is_real_apk": False, "package_name": None, "error": None}
    try:
        resp = session.get(apk_url, stream=True, timeout=25, verify=False, allow_redirects=True)
        if resp.status_code != 200:
            out["error"] = f"HTTP {resp.status_code}"
            return out
        cd = resp.headers.get("content-disposition", "")
        m = re.search(r'filename[^;=\n]*=(["\']?)([^;\n"\']+)', cd)
        fname = m.group(2).strip().strip('"\'') if m else (urlparse(apk_url).path.split("/")[-1] or "app.apk")
        if not fname.lower().endswith(".apk"):
            fname += ".apk"
        fname = re.sub(r"[^\w.\-]", "_", fname)
        dest = ev_folder / fname
        sha = hashlib.sha256()
        md5 = hashlib.md5()
        total = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                _raise_if_cancelled(job_id)
                if not chunk:
                    continue
                f.write(chunk)
                sha.update(chunk)
                md5.update(chunk)
                total += len(chunk)
                if total > MAX_APK_MB * 1024 * 1024:
                    break
        sha256_hex = sha.hexdigest()
        md5_hex = md5.hexdigest()
        is_real_apk = False
        try:
            with open(dest, "rb") as f:
                is_real_apk = f.read(4) == b"PK\x03\x04"
        except Exception:
            pass
        out.update({"success": True, "filename": fname, "filepath": str(dest), "size_mb": round(total / 1024 / 1024, 2), "sha256": sha256_hex, "md5": md5_hex, "is_real_apk": is_real_apk})
    except JobCancelled:
        out["error"] = "cancelled"
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def compute_verdict_v3(result: dict) -> dict:
    domain = (result.get("domain") or "").lower()
    crawl = result.get("crawl_data") or {}
    recon = result.get("recon") or {}
    ext = result.get("external_checks") or {}

    # hard malware signals first
    apk_urls = len(crawl.get("all_apk_links", []) or [])
    mal_links = len(crawl.get("all_malicious_links", []) or [])
    downloaded = result.get("apk_downloaded") or []
    real_apk = any(a.get("is_real_apk") for a in downloaded if a.get("success"))

    score = 0
    reasons = []
    if apk_urls:
        score += 70
        reasons.append(f"🚨 APK URL(s) detected: {apk_urls}")
    if downloaded:
        score += 80 if real_apk else 55
        reasons.append(f"🚨 APK downloaded: {len(downloaded)} (real_apk={bool(real_apk)})")
    if mal_links:
        score += 40
        reasons.append(f"⚠ Other malicious file links: {mal_links}")
    if (crawl.get("crypto_mining_pages") or []):
        score += 35
        reasons.append("🚨 Cryptojacking patterns detected")
    if (crawl.get("login_forms") or []):
        score += 20
        reasons.append("⚠ Credential-harvesting login form detected")

    # domain/tld heuristics (lower impact)
    tld = "." + domain.split(".")[-1] if "." in domain else ""
    if tld in HIGH_RISK_TLDS:
        score += 15
        reasons.append(f"⚠ High-risk TLD: {tld}")
    if re.search(r"\d{3,}", domain):
        score += 10
        reasons.append("⚠ Numeric sequence in domain")

    kws = crawl.get("all_phishing_keywords", []) or []
    if kws:
        score += min(len(kws) * 3, 20)
        reasons.append(f"⚠ Phishing keywords detected ({len(kws)})")

    # External checks influence
    vt_stats = (ext.get("virustotal") or {}).get("stats") or None
    if vt_stats:
        mal = int(vt_stats.get("malicious", 0) or 0)
        susp = int(vt_stats.get("suspicious", 0) or 0)
        if mal + susp >= 3:
            score += 25
            reasons.append(f"🚨 VirusTotal detections: malicious={mal}, suspicious={susp}")
        elif mal + susp == 0:
            score -= 10
            reasons.append("ℹ VirusTotal: no detections (reducing risk)")

    urlscan_verdicts = (ext.get("urlscan") or {}).get("verdicts") or None
    if urlscan_verdicts:
        overall = ((urlscan_verdicts.get("overall") or {}).get("score"))
        if isinstance(overall, (int, float)) and overall >= 50:
            score += 15
            reasons.append(f"⚠ urlscan overall score: {overall}")
        elif isinstance(overall, (int, float)) and overall <= 10:
            score -= 8
            reasons.append("ℹ urlscan: low score (reducing risk)")

    # Safe allowlist guardrail to prevent false positives
    if domain in SAFE_DOMAIN_ALLOWLIST and score < 70 and not apk_urls and not mal_links and not downloaded:
        score = min(score, 10)
        reasons.insert(0, "✅ Allowlisted domain — lowering risk (false-positive guard)")

    score = max(0, min(int(score), 100))
    if score >= 70:
        verdict = "FRAUD"
    elif score >= 40:
        verdict = "SUSPICIOUS"
    elif score >= 20:
        verdict = "NEEDS_REVIEW"
    else:
        verdict = "LIKELY_LEGIT"
    return {"verdict": verdict, "threat_score": score, "reasons": reasons, "summary": reasons[0] if reasons else "No significant threats"}


def save_evidence(folder: Path, result: dict):
    (folder / "metadata.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    # CSV rollup (compatible + extended)
    csv_path = REPORTS_DIR / "master_report.csv"
    write_header = not csv_path.exists()
    crawl = result.get("crawl_data") or {}
    recon = result.get("recon") or {}
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "timestamp","url","domain","verdict","threat_score",
                "pages_crawled","apk_count","apk_files","ip","ssl_issuer",
                "reasons","evidence_folder"
            ])
        w.writerow([
            result.get("timestamp",""),
            result.get("url",""),
            result.get("domain",""),
            result.get("verdict",""),
            result.get("threat_score",0),
            crawl.get("pages_crawled",0),
            len([a for a in (result.get("apk_downloaded") or []) if a.get("success")]),
            "|".join((a.get("filename","") for a in (result.get("apk_downloaded") or []))),
            recon.get("ip",""),
            recon.get("ssl_issuer",""),
            "|".join((result.get("reasons") or [])[:5]),
            str(folder),
        ])


def investigate_url(url: str, job_id: str) -> dict:
    def push_log(msg: str, level: str = "info"):
        with job_lock:
            JOBS[job_id]["log"].append({"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "level": level})
        log.info(f"[{job_id[:8]}] {msg}")

    def set_progress(p: int, status: str = ""):
        with job_lock:
            JOBS[job_id]["progress"] = p
            if status:
                JOBS[job_id]["status_text"] = status

    clean_url = url if url.startswith("http") else "https://" + url
    domain = urlparse(clean_url).netloc
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w.-]", "_", domain)[:60]
    ev_folder = BASE_DIR / f"{safe_name}_{ts}"
    ev_folder.mkdir(parents=True, exist_ok=True)

    result = {
        "url": url,
        "domain": domain,
        "evidence_folder": str(ev_folder),
        "verdict": "PENDING",
        "threat_score": 0,
        "reasons": [],
        "summary": "",
        "apk_links": [],
        "apk_downloaded": [],
        "apk_count": 0,
        "recon": {},
        "crawl_data": {},
        "external_checks": {},
        "timestamp": datetime.now().isoformat(),
        "error": None,
    }

    try:
        _raise_if_cancelled(job_id)
        set_progress(5, "Passive recon...")
        push_log("🔬 Passive recon started", "info")
        result["recon"] = passive_recon(domain)

        _raise_if_cancelled(job_id)
        set_progress(10, "External reputation checks...")
        result["external_checks"] = external_reputation_checks(clean_url)

        _raise_if_cancelled(job_id)
        set_progress(15, "Full domain crawl...")
        push_log("🕷️ Full domain crawl started", "info")
        crawl = crawl_domain(clean_url, job_id, ev_folder, push_log, set_progress)
        result["crawl_data"] = crawl
        result["apk_links"] = crawl.get("all_apk_links", []) or []

        _raise_if_cancelled(job_id)
        set_progress(87, "Downloading APK files...")
        session = req_lib.Session()
        session.headers.update({"User-Agent": USER_AGENTS["android"]})
        session.verify = False
        for apk_url in result["apk_links"]:
            _raise_if_cancelled(job_id)
            result["apk_downloaded"].append(download_apk_file(session, apk_url, ev_folder, job_id))

        result["apk_count"] = len([a for a in result["apk_downloaded"] if a.get("success")])

        set_progress(95, "Computing verdict...")
        result.update(compute_verdict_v3(result))

        set_progress(98, "Saving evidence...")
        save_evidence(ev_folder, result)
        set_progress(100, "Complete")

    except JobCancelled:
        result["verdict"] = "CANCELLED"
        result["reasons"] = ["Job cancelled by operator"]
        result["threat_score"] = 0
        with job_lock:
            JOBS[job_id]["status_text"] = "Cancelled"
    except Exception as e:
        result["verdict"] = "ERROR"
        result["error"] = str(e)
        push_log(f"💥 Error: {e}", "danger")
        log.error(traceback.format_exc())

    return result


def queue_worker():
    global QUEUE_WORKER_RUNNING
    QUEUE_WORKER_RUNNING = True
    while True:
        with QUEUE_LOCK:
            if not JOB_QUEUE:
                QUEUE_WORKER_RUNNING = False
                return
            job_id = JOB_QUEUE.popleft()
        with job_lock:
            job = JOBS.get(job_id)
            if not job:
                continue
            if job.get("cancelled"):
                job["status"] = "cancelled"
                job["status_text"] = "Cancelled"
                continue
            job["status"] = "running"
            job["status_text"] = "Investigating..."
        try:
            res = investigate_url(job["url"], job_id)
            with job_lock:
                job = JOBS.get(job_id) or {}
                if job.get("cancelled"):
                    JOBS[job_id]["status"] = "cancelled"
                    JOBS[job_id]["status_text"] = "Cancelled"
                else:
                    JOBS[job_id]["status"] = "done"
                    JOBS[job_id]["status_text"] = "Done"
                JOBS[job_id]["result"] = res
        except Exception as e:
            with job_lock:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = str(e)


def enqueue_job(url: str) -> str:
    global QUEUE_WORKER_RUNNING
    jid = str(uuid.uuid4())
    with job_lock:
        JOBS[jid] = {
            "id": jid,
            "url": url,
            "status": "queued",
            "status_text": "Queued — sequential mode",
            "progress": 0,
            "log": [],
            "result": None,
            "error": None,
            "cancelled": False,
        }
    with QUEUE_LOCK:
        JOB_QUEUE.append(jid)
    if not QUEUE_WORKER_RUNNING:
        threading.Thread(target=queue_worker, daemon=True).start()
    return jid


# ─────────────────────────────────────────────
#  API
# ─────────────────────────────────────────────
@app.route("/api/investigate", methods=["POST"])
def api_investigate():
    data = request.get_json()
    url = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400
    jid = enqueue_job(url)
    return jsonify({"job_id": jid, "queued": True}), 202


@app.route("/api/scan_batch", methods=["POST"])
def api_scan_batch():
    data = request.get_json()
    urls = (data or {}).get("urls", [])
    if not urls:
        return jsonify({"error": "urls array required"}), 400
    job_ids = []
    for u in urls[:200]:
        u = (u or "").strip()
        if u:
            job_ids.append(enqueue_job(u))
    with QUEUE_LOCK:
        qlen = len(JOB_QUEUE)
    return jsonify({"job_ids": job_ids, "total": len(job_ids), "queue_length": qlen, "note": "Sequential scanning"}), 202


@app.route("/api/job/<job_id>", methods=["GET"])
def api_job_status(job_id):
    with job_lock:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/job/<job_id>/cancel", methods=["POST"])
def api_job_cancel(job_id):
    with job_lock:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        job["cancelled"] = True
        if job.get("status") == "queued":
            job["status"] = "cancelled"
            job["status_text"] = "Cancelled"
    with QUEUE_LOCK:
        try:
            if job_id in JOB_QUEUE:
                JOB_QUEUE.remove(job_id)
        except ValueError:
            pass
    return jsonify({"ok": True, "job_id": job_id, "status": "cancelled"})


@app.route("/api/job/<job_id>/resume", methods=["POST"])
def api_job_resume(job_id):
    with job_lock:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        if job.get("status") != "cancelled":
            return jsonify({"error": f"Cannot resume job in status {job.get('status')}"}), 400
        job["cancelled"] = False
        job["status"] = "queued"
        job["status_text"] = "Resumed — queued"
        job["progress"] = 0
        job["error"] = None
        job["result"] = None
        job["log"] = job.get("log") or []
        job["log"].append({"time": datetime.now().strftime("%H:%M:%S"), "msg": "▶ Job resumed by operator", "level": "info"})
    with QUEUE_LOCK:
        JOB_QUEUE.append(job_id)
    global QUEUE_WORKER_RUNNING
    if not QUEUE_WORKER_RUNNING:
        threading.Thread(target=queue_worker, daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id, "status": "queued"})


@app.route("/api/jobs", methods=["GET"])
def api_all_jobs():
    with job_lock:
        jobs = [{
            "id": j["id"],
            "url": j["url"],
            "status": j.get("status", ""),
            "status_text": j.get("status_text", ""),
            "progress": j.get("progress", 0),
            "verdict": (j.get("result") or {}).get("verdict", ""),
            "threat_score": (j.get("result") or {}).get("threat_score", 0),
            "apk_count": len(((j.get("result") or {}).get("apk_downloaded")) or []),
            "pages_crawled": (((j.get("result") or {}).get("crawl_data")) or {}).get("pages_crawled", 0),
        } for j in JOBS.values()]
    return jsonify(jobs)


@app.route("/api/report", methods=["GET"])
def api_report():
    csv_path = REPORTS_DIR / "master_report.csv"
    if not csv_path.exists():
        return jsonify({"rows": []})
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return jsonify({"rows": rows})


@app.route("/api/status", methods=["GET"])
def api_status():
    with QUEUE_LOCK:
        qlen = len(JOB_QUEUE)
    running = sum(1 for j in JOBS.values() if j.get("status") == "running")
    done = sum(1 for j in JOBS.values() if j.get("status") == "done")
    fraud = sum(1 for j in JOBS.values() if (j.get("result") or {}).get("verdict") == "FRAUD")
    return jsonify({
        "status": "online",
        "version": "3.0",
        "tool": "PhishGuard India",
        "evidence_dir": str(BASE_DIR.resolve()),
        "chrome_download_dir": CHROME_DL_DIR,
        "total_jobs": len(JOBS),
        "running": running,
        "done": done,
        "fraud": fraud,
        "queue_length": qlen,
        "worker_active": QUEUE_WORKER_RUNNING,
        "max_pages_per_domain": MAX_PAGES_PER_DOMAIN,
        "crawl_timeout_sec": CRAWL_TIMEOUT,
        "vt_enabled": bool(VT_API_KEY),
        "urlscan_enabled": bool(URLSCAN_API_KEY),
    })


@app.route("/api/vt_check", methods=["POST"])
def api_vt_check():
    """Check a SHA256 hash or URL against VirusTotal."""
    data = request.get_json()
    sha256 = (data or {}).get("sha256", "").strip()
    url_to_check = (data or {}).get("url", "").strip()
    if not VT_API_KEY:
        return jsonify({"error": "VT_API_KEY not set. Set environment variable VT_API_KEY=<your_key>"}), 400
    try:
        if sha256:
            r = req_lib.get(
                f"https://www.virustotal.com/api/v3/files/{sha256}",
                headers={"x-apikey": VT_API_KEY}, timeout=15
            )
            if r.status_code == 200:
                j = r.json()
                stats = ((j.get("data") or {}).get("attributes") or {}).get("last_analysis_stats") or {}
                return jsonify({"ok": True, "hash": sha256, "stats": stats,
                                "vt_url": f"https://www.virustotal.com/gui/file/{sha256}"})
            return jsonify({"error": f"VT HTTP {r.status_code}"}), r.status_code
        elif url_to_check:
            import base64
            url_id = base64.urlsafe_b64encode(url_to_check.encode()).decode().rstrip("=")
            r = req_lib.get(
                f"https://www.virustotal.com/api/v3/urls/{url_id}",
                headers={"x-apikey": VT_API_KEY}, timeout=15
            )
            if r.status_code == 200:
                j = r.json()
                stats = ((j.get("data") or {}).get("attributes") or {}).get("last_analysis_stats") or {}
                return jsonify({"ok": True, "url": url_to_check, "stats": stats,
                                "vt_url": f"https://www.virustotal.com/gui/url/{url_id}"})
            # Try submitting first
            r2 = req_lib.post(
                "https://www.virustotal.com/api/v3/urls",
                headers={"x-apikey": VT_API_KEY},
                data={"url": url_to_check}, timeout=15
            )
            if r2.status_code in (200, 201):
                return jsonify({"ok": True, "submitted": True, "url": url_to_check,
                                "note": "Submitted for analysis. Check back in 60 seconds."})
            return jsonify({"error": f"VT HTTP {r2.status_code}"}), r2.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/urlscan_check", methods=["POST"])
def api_urlscan_check():
    """Submit a URL to urlscan.io."""
    data = request.get_json()
    url_to_check = (data or {}).get("url", "").strip()
    if not url_to_check:
        return jsonify({"error": "url required"}), 400
    if not URLSCAN_API_KEY:
        return jsonify({"error": "URLSCAN_API_KEY not set"}), 400
    try:
        r = req_lib.post(
            "https://urlscan.io/api/v1/scan/",
            headers={"API-Key": URLSCAN_API_KEY, "Content-Type": "application/json"},
            json={"url": url_to_check, "visibility": "private"}, timeout=15
        )
        if r.status_code in (200, 201):
            j = r.json()
            return jsonify({"ok": True, "uuid": j.get("uuid"), "result_url": j.get("result"), "api": j.get("api")})
        return jsonify({"error": f"urlscan HTTP {r.status_code}: {r.text[:200]}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/heuristic_scan", methods=["POST"])
def api_heuristic_scan():
    """Fast heuristic-only scan — no Selenium, instant result."""
    data = request.get_json()
    url = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400

    clean_url = url if url.startswith("http") else "https://" + url
    domain = urlparse(clean_url).netloc

    HIGH_RISK_TLDS_SET = {".xyz",".top",".click",".tk",".ml",".ga",".work",".loan",
                          ".icu",".buzz",".vip",".live",".online",".site",".website",
                          ".space",".fun",".store",".shop",".club",".info"}
    tld = "." + domain.split(".")[-1] if "." in domain else ""
    score = 0
    reasons = []

    if re.search(r"\d{3,}", domain): score += 12; reasons.append("Numeric sequence in domain")
    if re.search(r"(bet|casino|lottery|win|prize|lucky|satta|matka)", domain, re.I): score += 20; reasons.append("Gambling keyword in domain")
    if re.search(r"(bank|pay|upi|verify|secure|kyc|otp|update|login)", domain, re.I): score += 18; reasons.append("Finance/banking keyword in domain")
    if tld in HIGH_RISK_TLDS_SET: score += 15; reasons.append(f"High-risk TLD: {tld}")
    if len(domain.split(".")) > 4: score += 10; reasons.append("Deep subdomain structure")
    if re.search(r"(apk|download|install|app-download)", clean_url, re.I): score += 25; reasons.append("APK/download keyword in URL")
    if len(domain) > 35: score += 8; reasons.append("Unusually long domain name")
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", domain): score += 30; reasons.append("IP address as hostname")
    if domain in SAFE_DOMAIN_ALLOWLIST: score = max(0, score - 40); reasons.insert(0, "Known safe domain")

    # Impersonation check
    for brand in ["google","facebook","instagram","sbi","hdfc","icici","paytm","amazon","flipkart","whatsapp"]:
        if brand in domain and domain not in SAFE_DOMAIN_ALLOWLIST:
            score += 25; reasons.append(f"Possible {brand} impersonation domain")
            break

    score = max(0, min(int(score), 100))
    verdict = "FRAUD" if score >= 60 else "SUSPICIOUS" if score >= 35 else "NEEDS_REVIEW" if score >= 20 else "LIKELY_LEGIT"
    return jsonify({
        "url": url, "domain": domain, "verdict": verdict, "threat_score": score,
        "reasons": reasons, "summary": reasons[0] if reasons else "No threats detected",
        "heuristic_only": True, "apk_count": 0, "apk_downloaded": [],
    })


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Aggregated statistics for the ops dashboard."""
    with job_lock:
        all_jobs = list(JOBS.values())
    with QUEUE_LOCK:
        qlen = len(JOB_QUEUE)
    verdicts = {}
    apk_total = 0
    for j in all_jobs:
        r = j.get("result") or {}
        v = r.get("verdict") or j.get("status", "queued")
        verdicts[v] = verdicts.get(v, 0) + 1
        apk_total += r.get("apk_count", 0)
    return jsonify({
        "total_jobs": len(all_jobs),
        "queue_length": qlen,
        "verdicts": verdicts,
        "total_apk_found": apk_total,
        "running": sum(1 for j in all_jobs if j.get("status") == "running"),
        "done": sum(1 for j in all_jobs if j.get("status") == "done"),
    })


@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(".", "index.html")


@app.route("/<path:path>", methods=["GET"])
def serve_static(path):
    return send_from_directory(".", path)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║      PhishGuard India — Backend Server v3.0             ║
║  Selenium + Flask | APK Crawler | VT + urlscan          ║
╠══════════════════════════════════════════════════════════╣
║  Evidence folder : ./PhishGuard_Evidence/               ║
║  APK downloads   : ~/PhishGuard_Downloads/              ║
║                                                          ║
║  Optional API keys (set as env vars):                   ║
║    VT_API_KEY       — VirusTotal API                    ║
║    URLSCAN_API_KEY  — urlscan.io API                    ║
║                                                          ║
║  Starting server on: http://localhost:5000              ║
║  Open index.html in your browser.                       ║
╚══════════════════════════════════════════════════════════╝
""")
    import urllib3
    urllib3.disable_warnings()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


# ─────────────────────────────────────────────
#  CORE INVESTIGATION ENGINE
# ─────────────────────────────────────────────
def investigate_url(url: str, job_id: str) -> dict:
    """Full investigation: visit page with real Chrome, find & download APK."""

    def push_log(msg: str, level: str = "info"):
        with job_lock:
            JOBS[job_id]["log"].append({"time": datetime.now().strftime("%H:%M:%S"),
                                         "msg": msg, "level": level})
        log.info(f"[{job_id[:8]}] {msg}")

    def set_progress(p: int, status: str = ""):
        with job_lock:
            JOBS[job_id]["progress"] = p
            if status:
                JOBS[job_id]["status_text"] = status

    clean_url  = url if url.startswith("http") else "https://" + url
    domain     = urlparse(clean_url).netloc
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name  = re.sub(r"[^\w.-]", "_", domain)[:60]
    ev_folder  = BASE_DIR / f"{safe_name}_{ts}"
    dl_folder  = Path(CHROME_DL_DIR) / f"{safe_name}_{ts}"
    ev_folder.mkdir(parents=True, exist_ok=True)
    dl_folder.mkdir(parents=True, exist_ok=True)

    result = {
        "url": url, "domain": domain, "evidence_folder": str(ev_folder),
        "verdict": "PENDING", "threat_score": 0, "reasons": [],
        "apk_links": [], "apk_downloaded": [], "apk_count": 0,
        "page_title": "", "screenshot": "", "html_saved": False,
        "play_store_links": [], "fake_play_store": False,
        "phishing_keywords": [], "error": None,
        "timestamp": datetime.now().isoformat()
    }

    driver = None
    try:
        push_log(f"🚀 Starting investigation: {clean_url}", "info")
        set_progress(5, "Launching Chrome browser...")

        driver = make_driver(str(dl_folder))
        push_log("✓ Chrome launched (headless, mobile UA, download bypass enabled)", "ok")
        set_progress(10, "Navigating to target URL...")

        # ── Step 1: Load the page ─────────────────────────
        push_log(f"🌐 Loading: {clean_url}", "info")
        driver.get(clean_url)

        # Wait for body to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            push_log("⚠ Page load timeout — continuing anyway", "warn")

        set_progress(20, "Page loaded — waiting for JavaScript...")
        push_log(f"✓ Page loaded: {driver.title}", "ok")
        result["page_title"] = driver.title

        # ── Step 2: Scroll to trigger lazy-loaded content ──
        push_log("📜 Scrolling page to load dynamic content...", "info")
        for i in range(SCROLL_STEPS):
            driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/SCROLL_STEPS});")
            time.sleep(0.8)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(PAGE_WAIT)  # Wait for JS to execute fully
        set_progress(35, "Analysing page content...")

        # ── Step 3: Capture full page source after JS ──────
        full_html = driver.page_source
        soup = BeautifulSoup(full_html, "html.parser")

        # Save HTML
        html_path = ev_folder / "page_source.html"
        html_path.write_text(full_html, encoding="utf-8", errors="replace")
        result["html_saved"] = True
        push_log(f"✓ HTML saved ({len(full_html):,} chars)", "ok")

        # ── Step 4: Screenshot ─────────────────────────────
        ss_path = ev_folder / "screenshot.png"
        driver.save_screenshot(str(ss_path))
        result["screenshot"] = str(ss_path)
        push_log("✓ Screenshot captured", "ok")
        set_progress(45, "Hunting for APK links...")

        # ── Step 5: Extract ALL APK / Download links ───────
        apk_links = set()

        # Pattern A: direct .apk in any href
        for tag in soup.find_all(True):
            for attr in ["href", "src", "data-url", "data-href",
                          "data-download", "data-link", "data-src",
                          "data-file", "data-apk", "action", "formaction"]:
                val = tag.get(attr, "")
                if val and re.search(r"\.apk($|\?|#|&)", val, re.I):
                    abs_link = urljoin(clean_url, val)
                    apk_links.add(abs_link)
                    push_log(f"🚨 APK link in {tag.name}[{attr}]: {abs_link[:90]}", "danger")

        # Pattern B: APK URL in raw JS / onclick strings
        js_apk = re.findall(
            r"""(?:href|url|src|link|download|file)\s*[=:]\s*['"]([^'"]*\.apk[^'"]*)['"]""",
            full_html, re.I
        )
        for link in js_apk:
            abs_link = urljoin(clean_url, link)
            apk_links.add(abs_link)
            push_log(f"🚨 APK URL in JS code: {abs_link[:90]}", "danger")

        # Pattern C: bare APK URLs anywhere in HTML
        bare = re.findall(r"https?://[^\s\"'<>]*\.apk[^\s\"'<>]*", full_html, re.I)
        for link in bare:
            apk_links.add(link)
            push_log(f"🚨 Raw APK URL: {link[:90]}", "danger")

        # Pattern D: network log (CDP) — catches XHR/fetch to .apk
        push_log("🔍 Scanning network logs for APK requests...", "info")
        try:
            perf_logs = driver.get_log("performance")
            for entry in perf_logs:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method") == "Network.requestWillBeSent":
                    req_url = msg.get("params", {}).get("request", {}).get("url", "")
                    if re.search(r"\.apk($|\?|#|&)", req_url, re.I):
                        apk_links.add(req_url)
                        push_log(f"🚨 APK in network log: {req_url[:90]}", "danger")
        except Exception:
            pass

        result["apk_links"] = list(apk_links)

        # ── Step 6: Detect & click Download buttons ────────
        set_progress(55, "Clicking download buttons...")
        push_log("🖱️ Looking for download / install app buttons...", "info")

        download_selectors = [
            # Text-based
            "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download')]",
            "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download')]",
            "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'install')]",
            "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'get app')]",
            "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download app')]",
            "//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'डाउनलोड')]",
            # Attribute-based
            "//a[contains(@href,'.apk')]",
            "//a[contains(@href,'download')]",
            "//img[contains(@src,'playstore') or contains(@src,'play-store') or contains(@alt,'play store')]/..",
            "//a[contains(@class,'download')]",
            "//a[contains(@id,'download')]",
            "//button[contains(@class,'download')]",
        ]

        clicked_count = 0
        pre_click_files = set(dl_folder.glob("*.apk"))

        for sel in download_selectors:
            try:
                elements = driver.find_elements(By.XPATH, sel)
                for el in elements[:3]:  # try up to 3 matching elements
                    try:
                        href = el.get_attribute("href") or ""
                        text = el.text.strip()[:50]
                        push_log(f"  🖱 Clicking: [{el.tag_name}] '{text}' → {href[:60]}", "info")

                        # Scroll into view
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.5)

                        # Try to capture href before click
                        if href and re.search(r"\.apk($|\?|#|&)", href, re.I):
                            apk_links.add(urljoin(clean_url, href))

                        # Click
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)

                        clicked_count += 1
                        time.sleep(CLICK_WAIT)

                        # Check if new APK appeared in network logs
                        try:
                            new_logs = driver.get_log("performance")
                            for entry in new_logs:
                                msg = json.loads(entry["message"])["message"]
                                if msg.get("method") == "Network.requestWillBeSent":
                                    ru = msg.get("params", {}).get("request", {}).get("url", "")
                                    if re.search(r"\.apk($|\?|#|&)", ru, re.I):
                                        apk_links.add(ru)
                                        push_log(f"  🚨 APK triggered by click: {ru[:80]}", "danger")
                        except Exception:
                            pass

                        # Check download folder for new files
                        post_click = set(dl_folder.glob("*.apk"))
                        new_files = post_click - pre_click_files
                        if new_files:
                            for nf in new_files:
                                push_log(f"  ✓ APK auto-downloaded by Chrome: {nf.name}", "ok")
                            pre_click_files = post_click

                    except Exception as e:
                        push_log(f"  ⚠ Click failed: {str(e)[:60]}", "warn")
            except Exception:
                pass

        push_log(f"Clicked {clicked_count} download button(s)", "info")
        result["apk_links"] = list(apk_links)
        set_progress(65, "Checking Play Store links...")

        # ── Step 7: Play Store analysis ────────────────────
        play_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "play.google.com/store/apps" in href:
                play_links.append(href)
            elif "apps.apple.com" in href:
                play_links.append(href)

        result["play_store_links"] = play_links

        # Fake play store = shows play badge but also serves APK
        lhtml = full_html.lower()
        has_badge = ("google-play" in lhtml or "play_store" in lhtml or
                     "playstore" in lhtml or "play store" in lhtml or
                     "get it on" in lhtml)
        result["fake_play_store"] = has_badge and bool(apk_links) and not play_links
        if result["fake_play_store"]:
            push_log("🚨 FAKE PLAY STORE: Shows Play badge but serves APK directly!", "danger")

        # Phishing keywords
        full_text = soup.get_text(" ").lower()
        kws = ["kyc", "verify account", "upi fraud", "claim reward", "lucky winner",
               "win prize", "otp", "account suspended", "loan approved", "earn money",
               "investment return", "withdraw", "bonus", "refer and earn", "bet", "casino"]
        result["phishing_keywords"] = [k for k in kws if k in full_text]

        set_progress(75, "Downloading APK files...")

        # ── Step 8: Download APK files ─────────────────────
        push_log(f"\n📦 APK URLs to download: {len(apk_links)}", "info")

        session = req_lib.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36"
        })

        for i, apk_url in enumerate(apk_links, 1):
            push_log(f"  ⬇ Downloading APK [{i}/{len(apk_links)}]: {apk_url[:80]}", "info")
            apk_result = download_apk_file(session, apk_url, ev_folder, push_log, i)
            result["apk_downloaded"].append(apk_result)
            if apk_result["success"]:
                push_log(
                    f"  ✅ SAVED: {apk_result['filename']} "
                    f"({apk_result['size_mb']:.2f}MB) SHA256: {apk_result['sha256'][:20]}...",
                    "ok"
                )
            else:
                push_log(f"  ✗ Download failed: {apk_result['error']}", "warn")

        # Also check if Chrome already downloaded any APKs automatically
        time.sleep(3)
        chrome_apks = list(Path(CHROME_DL_DIR).glob("*.apk")) + list(dl_folder.glob("*.apk"))
        for capk in chrome_apks:
            if not any(d.get("filepath") == str(capk) for d in result["apk_downloaded"]):
                # Copy to evidence folder
                dest = ev_folder / capk.name
                shutil.copy2(capk, dest)
                sha = hashlib.sha256(capk.read_bytes()).hexdigest()
                size = capk.stat().st_size
                push_log(f"  ✅ Chrome-downloaded APK found: {capk.name} ({size//1024}KB)", "ok")
                result["apk_downloaded"].append({
                    "url": "auto-downloaded", "filename": capk.name,
                    "filepath": str(dest), "size_bytes": size,
                    "size_mb": round(size/1024/1024, 2),
                    "sha256": sha, "success": True, "source": "chrome_auto"
                })

        result["apk_count"] = len(result["apk_downloaded"])
        set_progress(88, "Computing verdict...")

        # ── Step 9: Verdict ────────────────────────────────
        verdict_data = compute_verdict(result)
        result.update(verdict_data)
        push_log(
            f"\n{'='*50}\n"
            f"  VERDICT : {result['verdict']}\n"
            f"  SCORE   : {result['threat_score']}%\n"
            f"  APKs    : {result['apk_count']}\n"
            f"{'='*50}", "info"
        )

        set_progress(94, "Saving reports...")

        # ── Step 10: Save evidence ─────────────────────────
        save_evidence(ev_folder, result)
        push_log(f"✓ Evidence folder: {ev_folder}", "ok")
        set_progress(100, "Complete")

    except Exception as e:
        tb = traceback.format_exc()
        push_log(f"💥 Critical error: {e}", "danger")
        log.error(tb)
        result["error"] = str(e)
        result["verdict"] = "ERROR"
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return result


# ─────────────────────────────────────────────
#  APK DOWNLOADER
# ─────────────────────────────────────────────
def download_apk_file(session, apk_url: str, ev_folder: Path,
                      push_log, num: int = 1) -> dict:
    out = {"url": apk_url, "success": False, "filename": None,
           "filepath": None, "size_bytes": 0, "size_mb": 0,
           "sha256": None, "error": None}
    try:
        resp = session.get(apk_url, stream=True, timeout=30, verify=False,
                           allow_redirects=True)
        if resp.status_code != 200:
            out["error"] = f"HTTP {resp.status_code}"
            return out

        # Filename from Content-Disposition or URL
        cd = resp.headers.get("content-disposition", "")
        m = re.search(r'filename[^;=\n]*=(["\']?)([^;\n"\']+)', cd)
        if m:
            fname = m.group(2).strip().strip('"\'')
        else:
            fname = urlparse(apk_url).path.split("/")[-1] or "app.apk"
        if not fname.lower().endswith(".apk"):
            fname += ".apk"

        # Sanitise filename
        fname = re.sub(r"[^\w.\-]", "_", fname)
        dest = ev_folder / fname
        sha  = hashlib.sha256()
        total = 0

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    sha.update(chunk)
                    total += len(chunk)
                    if total > MAX_APK_MB * 1024 * 1024:
                        push_log("  ⚠ APK size limit reached, stopping", "warn")
                        break

        out.update({
            "success": True, "filename": fname,
            "filepath": str(dest), "size_bytes": total,
            "size_mb": round(total / 1024 / 1024, 2),
            "sha256": sha.hexdigest()
        })
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


# ─────────────────────────────────────────────
#  VERDICT ENGINE
# ─────────────────────────────────────────────
def compute_verdict(r: dict) -> dict:
    score = 0
    reasons = []

    if r["apk_count"] > 0:
        score += 70
        reasons.append(f"APK file(s) found and downloaded: {r['apk_count']}")
    if r["apk_links"]:
        score += 20
        reasons.append(f"APK download URL(s) detected on page: {len(r['apk_links'])}")
    if r["fake_play_store"]:
        score += 30
        reasons.append("Fake Play Store badge — serves APK instead of redirecting")

    domain = r["domain"].lower()
    suspicious_patterns = [
        (r"(bet|casino|gambling|lottery|win|prize|lucky)", "Gambling/prize keyword in domain"),
        (r"(bank|pay|upi|wallet|secure|verify|login)", "Finance/security keyword in domain"),
        (r"\d{3,}", "Numeric sequence in domain"),
        (r"\.co$", "Suspicious .co TLD (common fraud domain)"),
        (r"\.(xyz|top|click|tk|ml|ga|work|loan)$", "High-risk TLD"),
    ]
    for pattern, reason in suspicious_patterns:
        if re.search(pattern, domain):
            score += 12
            reasons.append(reason)

    kws = r.get("phishing_keywords", [])
    if kws:
        score += min(len(kws) * 5, 25)
        reasons.append(f"Phishing keywords: {', '.join(kws[:4])}")

    score = min(score, 100)
    verdict = "FRAUD" if score >= 55 else "SUSPICIOUS" if score >= 30 else "LEGIT"

    return {
        "verdict": verdict,
        "threat_score": score,
        "reasons": reasons,
        "summary": reasons[0] if reasons else "No significant threats"
    }


# ─────────────────────────────────────────────
#  EVIDENCE SAVER
# ─────────────────────────────────────────────
def save_evidence(folder: Path, r: dict):
    # metadata.json
    with open(folder / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=str)

    # investigation_report.txt
    apk_section = ""
    for i, a in enumerate(r["apk_downloaded"], 1):
        apk_section += (
            f"\n  APK #{i}:\n"
            f"    Filename : {a.get('filename','N/A')}\n"
            f"    Size     : {a.get('size_mb',0):.2f} MB\n"
            f"    SHA-256  : {a.get('sha256','N/A')}\n"
            f"    Path     : {a.get('filepath','N/A')}\n"
            f"    Status   : {'DOWNLOADED ✓' if a.get('success') else 'FAILED: '+str(a.get('error',''))}\n"
        )

    report = f"""
╔══════════════════════════════════════════════════════╗
║   PHISHGUARD INDIA — INVESTIGATION REPORT           ║
╚══════════════════════════════════════════════════════╝

Date    : {datetime.now():%d %B %Y, %H:%M:%S}
URL     : {r['url']}
Domain  : {r['domain']}
Title   : {r['page_title']}

VERDICT      : *** {r['verdict']} ***
THREAT SCORE : {r['threat_score']}%
APKs FOUND   : {r['apk_count']}

THREAT INDICATORS:
{chr(10).join('  [!] '+x for x in r['reasons']) or '  None'}

APK DOWNLOADS:
{apk_section or '  None found'}

PLAY STORE LINKS:
{chr(10).join('  '+x for x in r['play_store_links']) or '  None'}

PHISHING KEYWORDS:
  {', '.join(r['phishing_keywords']) or 'None'}

EVIDENCE FILES:
  metadata.json        — Full JSON data
  page_source.html     — Complete JS-rendered page
  screenshot.png       — Page screenshot
  *.apk                — Downloaded APK files

SUBMIT APKs TO:
  VirusTotal : https://www.virustotal.com
  CERT-In    : https://www.cert-in.org.in
  MHA I4C    : https://www.cybercrime.gov.in
══════════════════════════════════════════════════════
"""
    (folder / "investigation_report.txt").write_text(report, encoding="utf-8")

    # CSV summary row
    csv_path = REPORTS_DIR / "master_report.csv"
    write_header = not csv_path.exists()
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        import csv
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp","url","domain","verdict","threat_score",
                         "apk_count","apk_files","reasons","evidence_folder"])
        w.writerow([
            r["timestamp"], r["url"], r["domain"], r["verdict"],
            r["threat_score"], r["apk_count"],
            "|".join(a.get("filename","") for a in r["apk_downloaded"]),
            "|".join(r["reasons"][:3]),
            str(folder)
        ])


# ─────────────────────────────────────────────
#  BACKGROUND JOB RUNNER
# ─────────────────────────────────────────────
def run_job(job_id: str, url: str):
    with job_lock:
        JOBS[job_id]["status"] = "running"
    try:
        result = investigate_url(url, job_id)
        with job_lock:
            JOBS[job_id]["status"]  = "done"
            JOBS[job_id]["result"] = result
    except Exception as e:
        with job_lock:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"]  = str(e)


# ─────────────────────────────────────────────
#  API ROUTES
# ─────────────────────────────────────────────
@app.route("/api/investigate", methods=["POST"])
def api_investigate():
    data = request.get_json()
    url  = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400

    import uuid
    job_id = str(uuid.uuid4())
    with job_lock:
        JOBS[job_id] = {
            "id": job_id, "url": url,
            "status": "queued", "status_text": "Queued",
            "progress": 0, "log": [], "result": None, "error": None
        }

    t = threading.Thread(target=run_job, args=(job_id, url), daemon=True)
    t.start()
    return jsonify({"job_id": job_id}), 202


@app.route("/api/job/<job_id>", methods=["GET"])
def api_job_status(job_id):
    with job_lock:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/jobs", methods=["GET"])
def api_all_jobs():
    with job_lock:
        jobs = [{"id": j["id"], "url": j["url"], "status": j["status"],
                  "progress": j["progress"],
                  "verdict": (j.get("result") or {}).get("verdict", ""),
                  "apk_count": (j.get("result") or {}).get("apk_count", 0)}
                 for j in JOBS.values()]
    return jsonify(jobs)


@app.route("/api/scan_batch", methods=["POST"])
def api_scan_batch():
    data = request.get_json()
    urls = (data or {}).get("urls", [])
    if not urls:
        return jsonify({"error": "urls array required"}), 400

    import uuid
    job_ids = []
    for url in urls[:100]:  # max 100 at a time
        url = url.strip()
        if not url:
            continue
        job_id = str(uuid.uuid4())
        with job_lock:
            JOBS[job_id] = {
                "id": job_id, "url": url,
                "status": "queued", "status_text": "Queued",
                "progress": 0, "log": [], "result": None, "error": None
            }
        t = threading.Thread(target=run_job, args=(job_id, url), daemon=True)
        t.start()
        job_ids.append(job_id)
        time.sleep(0.5)  # stagger launches

    return jsonify({"job_ids": job_ids, "total": len(job_ids)}), 202


@app.route("/api/report", methods=["GET"])
def api_report():
    csv_path = REPORTS_DIR / "master_report.csv"
    if not csv_path.exists():
        return jsonify({"rows": []})
    import csv
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return jsonify({"rows": rows})


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "status": "online",
        "version": "2.0",
        "tool": "PhishGuard India",
        "evidence_dir": str(BASE_DIR.resolve()),
        "total_jobs": len(JOBS),
        "chrome_download_dir": CHROME_DL_DIR
    })


@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(".", "index.html")


@app.route("/<path:path>", methods=["GET"])
def serve_static(path):
    return send_from_directory(".", path)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║       PhishGuard India — Backend Server v2.0        ║
║   Selenium + Flask | APK Crawler + Evidence Store   ║
╚══════════════════════════════════════════════════════╝

 Evidence folder : ./PhishGuard_Evidence/
 APK downloads   : ~/PhishGuard_Downloads/

 Starting server on: http://localhost:5000
 Open index.html in your browser — it will connect automatically.

 Press Ctrl+C to stop.
""")
    import urllib3
    urllib3.disable_warnings()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

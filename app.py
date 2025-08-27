import streamlit as st
import requests
import pandas as pd
import time
import urllib.parse
from typing import Dict, Any, List

st.set_page_config(page_title="Bulk PageSpeed Tester", layout="wide")
st.title("🚀 Bulk Website Speed Tester (Google PageSpeed API)")

api_key = st.text_input("🔑 Google PageSpeed API key", type="password")
uploaded_file = st.file_uploader("📂 Upload a .txt file with URLs (one per line)", type=["txt"])

colA, colB, colC = st.columns(3)
with colA:
    devices = st.multiselect("📱 Devices", ["mobile", "desktop"], default=["mobile", "desktop"])
with colB:
    delay = st.number_input("⏱ Delay between requests (sec)", min_value=0.0, value=1.0, step=0.5)
with colC:
    max_retries = st.number_input("🔁 Retries on 429/5xx", min_value=0, value=2, step=1)

def is_valid_url(u: str) -> bool:
    try:
        p = urllib.parse.urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def call_pagespeed(url: str, device: str, key: str) -> Dict[str, Any]:
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    r = requests.get(endpoint, params={"url": url, "strategy": device, "key": key}, timeout=60)
    r.raise_for_status()
    return r.json()

def run_with_backoff(url: str, device: str, key: str, retries: int) -> Dict[str, Any]:
    attempt, wait = 0, 1.5
    while True:
        try:
            data = call_pagespeed(url, device, key)
            lh = data.get("lighthouseResult", {}) or {}
            cats = lh.get("categories", {}) or {}
            audits = lh.get("audits", {}) or {}
            perf = cats.get("performance", {}).get("score")
            perf = round(perf * 100) if perf is not None else None
            return {
                "URL": url, "Device": device, "Performance Score": perf,
                "FCP": audits.get("first-contentful-paint", {}).get("displayValue", ""),
                "LCP": audits.get("largest-contentful-paint", {}).get("displayValue", ""),
                "TBT": audits.get("total-blocking-time", {}).get("displayValue", ""),
                "CLS": audits.get("cumulative-layout-shift", {}).get("displayValue", ""),
            }
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            if code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(wait); wait *= 2; attempt += 1; continue
            return {"URL": url, "Device": device, "Performance Score": "Error",
                    "FCP": f"HTTP {code}: {e}", "LCP": "", "TBT": "", "CLS": ""}
        except Exception as e:
            return {"URL": url, "Device": device, "Performance Score": "Error",
                    "FCP": f"Request failed: {e}", "LCP": "", "TBT": "", "CLS": ""}

if uploaded_file and api_key:
    raw = uploaded_file.read().decode("utf-8").splitlines()
    urls = [u.strip() for u in raw if u.strip()]
    urls = [u if u.startswith(("http://","https://")) else "https://" + u for u in urls]
    urls = list(dict.fromkeys(urls))            # de-dupe keep order
    urls = [u for u in urls if is_valid_url(u)]

    st.success(f"✅ {len(urls)} unique, valid URLs loaded")

    if st.button("▶ Run Test"):
        rows, progress, status = [], st.progress(0), st.empty()
        for i, url in enumerate(urls):
            status.write(f"Testing: {url}")
            for d in devices:
                rows.append(run_with_backoff(url, d, api_key, retries=int(max_retries)))
                if delay > 0: time.sleep(delay)
            progress.progress((i + 1) / len(urls))

        df = pd.DataFrame(rows)
        st.subheader("📊 Results"); st.dataframe(df, use_container_width=True)
        st.download_button("💾 Download CSV",
                           df.to_csv(index=False).encode("utf-8"),
                           "pagespeed_results.csv","text/csv")
elif uploaded_file and not api_key:
    st.warning("Please enter your API key to run.")
else:
    st.info("Upload a URLs file and enter your API key to begin.")

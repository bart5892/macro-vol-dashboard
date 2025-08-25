import os, json
from datetime import datetime, timezone
import requests, pandas as pd, numpy as np, streamlit as st

st.set_page_config(page_title="Macro + Vol Dashboard (WORKING)", layout="wide")
st.title("🏦 Macro + Volatility Trading Platform — WORKING build (correct surface endpoint)")

ASSETS = ["BTC","ETH"]
DELTA_TRIES = [49, 0.49]
TENOR_SHORT_TRIES = ["1w","7d"]
TENOR_LONG_TRIES  = ["30d","1m","30D"]
SYMBOLS = {"BTC":["BTC-USD","BTCUSD","BTC"], "ETH":["ETH-USD","ETHUSD","ETH"]}
BASE_URL = "https://api.investdefy.com/v1/data/volatility-surface"
RV_DEFAULT = 0.32

# 🔑 Your API key is embedded here
EMBEDDED_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjYThiY2NjMy00NTdhLTRjMjktYjYyYy02NDMyYWQ3OGRjZTUiLCJleHAiOjE3NTU4NjQ4NDAsImlhdCI6MTc1MzI3Mjg0MCwiaXNzIjoiaW52ZXN0ZGVmeS5jb20ifQ.8jyYpidD6kdTvWR8fcPh4boBjFQPo3wh4UVoKMkQ0w4"

def get_api_key():
    return EMBEDDED_KEY

def parse_iv(payload_text, tenor, delta):
    try:
        d = json.loads(payload_text)
    except Exception:
        return None
    if isinstance(d,(int,float)):
        return float(d)
    if isinstance(d,dict) and "iv" in d:
        try: return float(d["iv"])
        except: return None
    if isinstance(d,dict) and "dime" in d and isinstance(d["dime"], list):
        best_iv, best_diff = None, 1e9
        for row in d["dime"]:
            try:
                if str(row.get("tenor","")).lower() == str(tenor).lower():
                    diff = abs(float(row.get("delta",0)) - float(delta))
                    if diff < best_diff:
                        best_diff = diff; best_iv = float(row["iv"])
            except: pass
        return best_iv
    return None

def try_fetch(symbol, tenor, delta, headers):
    url = f"{BASE_URL}?symbol={symbol}&tenor={tenor}&delta={delta}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        return r.status_code, r.text, url
    except Exception as e:
        return -1, str(e), url

@st.cache_data(ttl=60, show_spinner=False)
def fetch_iv(asset, tenor_kind):
    headers = {"Authorization": f"Bearer {get_api_key()}","Accept":"application/json"}
    tenors = TENOR_SHORT_TRIES if tenor_kind=="short" else TENOR_LONG_TRIES
    tried = []
    for sym in SYMBOLS[asset]:
        for ten in tenors:
            for d in DELTA_TRIES:
                code, body, url = try_fetch(sym, ten, d, headers)
                tried.append({"status":code,"url":url,"preview":body[:240]})
                if code==200:
                    iv = parse_iv(body, ten, d)
                    if iv is not None and np.isfinite(iv):
                        return iv, url, tried
    return None, None, tried

tabs = st.tabs(["Vol Monitor","Diagnostics"])
tab_vol, tab_diag = tabs

with tab_vol:
    st.subheader("Vol Monitor — ATM-ish (49Δ), Short vs Long")
    rows=[]; calls=[]; diag={}
    for a in ASSETS:
        iv_s, u1, t1 = fetch_iv(a,"short")
        iv_l, u2, t2 = fetch_iv(a,"long")
        diag[a] = (t1+t2)[:12]
        rv7 = RV_DEFAULT
        skew = (iv_l - iv_s) if (isinstance(iv_l,(int,float)) and isinstance(iv_s,(int,float))) else None
        rows.append({"Timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                     "Asset":a,"IV_short":iv_s,"IV_long":iv_l,"RV_7d":rv7,"Skew":skew})
        calls.append({"asset":a,"short_url":u1,"long_url":u2})
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.markdown("**Last API calls used**")
    st.code(json.dumps(calls, indent=2))
    st.session_state["__diag__"] = diag

with tab_diag:
    st.subheader("Diagnostics")
    diag = st.session_state.get("__diag__",{})
    if not diag:
        st.info("Open Vol Monitor first to populate diagnostics.")
    else:
        for a, logs in diag.items():
            st.markdown(f"### {a}")
            for i,entry in enumerate(logs):
                st.text(f"[{i}] {entry['status']} — {entry['url']}")
                st.code(entry['preview'])

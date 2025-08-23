# app.py
# Streamlit: tạo tên sản phẩm từ specsheet Excel dạng 2 cột (Key | Value)
# Yêu cầu: streamlit, pandas, openpyxl, xlsxwriter

import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Product Name Builder", page_icon="🧩")

# =========================
# Config & Helpers
# =========================
RESOLUTION_MAP = {
    "1366x768": "HD",
    "1920x1080": "FHD",
    "1920x1200": "WUXGA",
    "2560x1440": "QHD",
    "2560x1600": "WQXGA",
    "3840x2160": "4K",
}

def _to_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none", "null") else s

def _norm_key(s: str) -> str:
    s = _to_str(s).lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("&", "and")
    return s

def _kv_map_from_specsheet(df: pd.DataFrame) -> dict:
    """
    Nhận DataFrame specsheet 2 cột (Key|Value), trả về dict {key_norm: value}
    - Nếu có >2 cột: dùng 2 cột đầu.
    - Nếu chỉ 1 cột dạng "Key: Value" thì cố gắng tách.
    """
    if df.shape[1] < 2:
        df2 = df.copy()
        df2["__key__"] = df2.iloc[:, 0].apply(lambda x: str(x).split(":", 1)[0] if pd.notna(x) else "")
        df2["__val__"] = df2.iloc[:, 0].apply(lambda x: str(x).split(":", 1)[1] if (pd.notna(x) and ":" in str(x)) else "")
        key_col, val_col = "__key__", "__val__"
    else:
        key_col, val_col = df.columns[0], df.columns[1]

    kv = {}
    for _, row in df.iterrows():
        k = _norm_key(row.get(key_col, ""))
        v = _to_str(row.get(val_col, ""))
        if k:
            kv[k] = v
    return kv

def _get(kv: dict, *keys) -> str:
    """Lấy value theo danh sách khóa ứng viên (đã normalize)."""
    for k in keys:
        v = kv.get(_norm_key(k), "")
        if v:
            return v
    return ""

def _normalize_resolution(res: str) -> str:
    raw = _to_str(res)
    if not raw:
        return ""
    s = raw.upper().replace(" ", "")
    # nếu đã là mã (FHD/WUXGA/...) thì giữ
    if s in {v.upper() for v in RESOLUTION_MAP.values()}:
        return s
    # map theo số 1920x1080 -> FHD, ...
    mapped = RESOLUTION_MAP.get(s.lower(), "")
    return mapped if mapped else raw

def _wifi_code(wireless: str) -> str:
    t = _to_str(wireless).upper()
    if not t:
        return ""
    if "6E" in t or "WI-FI 6E" in t or "WIFI 6E" in t:
        return "WF6E"
    if re.search(r"\b6\b", t) or "WI-FI 6" in t or "WIFI 6" in t:
        return "WF6"
    if re.search(r"\b5\b", t) or "WI-FI 5" in t or "WIFI 5" in t:
        return "WF5"
    if "WIFI" in t or "WI-FI" in t:
        return "WF"
    return ""

def _has_bt(wireless: str) -> bool:
    t = _to_str(wireless).upper()
    return "BT" in t or "BLUETOOTH" in t

def _touch_code(val: str) -> str:
    t = _to_str(val).lower()
    return "T" if any(x in t for x in ["yes", "touch", "capacitive", "multi-touch", "multi touch"]) else ""

def _bool_by_presence(val: str) -> bool:
    t = _to_str(val).lower()
    return bool(t) and t not in ("no", "không", "none", "n/a")

def _kbm_code(kb_mouse: str, included_box: str) -> str:
    src = f"{_to_str(kb_mouse)} {_to_str(included_box)}".lower()
    if not src.strip():
        return ""
    tags = []
    # keyboard
    if "wireless keyboard" in src:
        tags.append("WL_KB")
    elif "keyboard" in src:
        tags.append("KB")
    # mouse
    if "wireless mouse" in src:
        tags.append("WL_M")
    elif "mouse" in src:
        tags.append("M")
    return "&".join(tags) if tags else ""

def _os_code(os_text: str) -> str:
    t = _to_str(os_text).lower()
    if "windows 11 pro" in t:
        return "W11P"
    if "windows 11 home" in t:
        return "W11H"
    return "NOS"  # bắt buộc có, thiếu => NOS

def _warranty_code(w_text: str) -> str:
    t = _to_str(w_text).lower()
    if not t:
        return ""
    m = re.search(r"(\d+)\s*(year|years|y)\b", t)
    year = f"{m.group(1)}Y" if m else ""
    wtype = ""
    if "on site" in t or "onsite" in t or "on-site" in t:
        wtype = "OSS"
    elif "pur" in t:
        wtype = "PUR"
    return f"{year}-{wtype}" if (year and wtype) else ""

# =========================
# Core build logic
# =========================
def build_name_from_kv(kv: dict) -> str:
    """
    Thứ tự cố định:
    Model + CPU + RAM + SSD + HDD(if) + TPM + Display + T(if) + CAM(if) + MIC(if) + WF(if) + BT(if)
    + KB&M(if) + Windows(mandatory, NOS if missing) + Warranty(if) + Color(if) + (Sales Model or Sales Model Name)
    """
    parts = []

    # 1) Model — phần trước dấu '-' của "Sales Model Name" (bắt buộc)
    smn = _get(kv, "Sales Model Name")
    if not smn:
        raise ValueError("Thiếu 'Sales Model Name' trong specsheet.")
    model = smn.split("-", 1)[0].strip() if "-" in smn else smn.strip()
    parts.append(model)

    # 2) CPU
    cpu = _get(kv, "CPU", "Processor")
    if cpu:
        parts.append(cpu)

    # 3) RAM (Memory)
    ram = _get(kv, "Memory", "RAM")
    if ram:
        parts.append(ram)

    # 4) SSD
    ssd = _get(kv, "SSD")
    if ssd:
        parts.append(f"{ssd}-SSD")

    # 5) HDD (nếu có)
    hdd = _get(kv, "HDD")
    if hdd:
        parts.append(f"{hdd}-HDD")

    # 6) TPM (luôn có)
    p

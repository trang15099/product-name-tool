import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Product Name Builder", page_icon="🧩")

# ---------- Helpers ----------
RESOLUTION_MAP = {
    "1366x768": "HD",
    "1920x1080": "FHD",
    "1920x1200": "WUXGA",
    "2560x1440": "QHD",
    "2560x1600": "WQXGA",
    "3840x2160": "4K",
}

def to_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none", "null") else s

def normalize_key(s):
    s = to_str(s).lower()
    # chuẩn hóa tối giản để bắt key linh hoạt
    s = re.sub(r"\s+", " ", s)
    s = s.replace("&", "and")
    return s

def build_kv_map(df):
    """
    Nhận specsheet 2 cột (Key|Value). Trả về dict {key_norm: value_str}
    - Nếu có >2 cột, lấy 2 cột đầu.
    - Bỏ các dòng key trống.
    """
    if df.shape[1] < 2:
        # cố gắng sửa: nếu file có 1 cột, tách theo dấu ':' nếu có
        df2 = df.copy()
        df2["__key__"] = df2.iloc[:,0].apply(lambda x: str(x).split(":",1)[0] if pd.notna(x) else "")
        df2["__val__"] = df2.iloc[:,0].apply(lambda x: str(x).split(":",1)[1] if (pd.notna(x) and ":" in str(x)) else "")
        key_col, val_col = "__key__", "__val__"
    else:
        key_col, val_col = df.columns[0], df.columns[1]

    kv = {}
    for _, row in df.iterrows():
        k = normalize_key(row.get(key_col, ""))
        v = to_str(row.get(val_col, ""))
        if k:
            kv[k] = v
    return kv

def get_value(kv, *candidates):
    """
    Tìm giá trị theo danh sách key ứng viên (đã normalize).
    Ví dụ: get_value(kv, "sales model name", "sales-model-name")
    """
    for c in candidates:
        val = kv.get(normalize_key(c), "")
        if val:
            return val
    return ""

def normalize_resolution(res):
    res_raw = to_str(res)
    if not res_raw:
        return ""
    s = res_raw.upper().replace(" ", "")
    # nếu đã là mã (FHD, WUXGA, ...) thì trả thẳng
    if s in set(v.upper() for v in RESOLUTION_MAP.values()):
        return s
    # map từ dạng 1920x1080

import pandas as pd
import re

# ==== CONFIG: mapping độ phân giải ====
RESOLUTION_MAP = {
    "1366x768": "HD",
    "1920x1080": "FHD",
    "1920x1200": "WUXGA",
    "2560x1440": "QHD",
    "2560x1600": "WQXGA",
    "3840x2160": "4K",
}

# ==== Helpers ====
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
    """Nhận DataFrame specsheet 2 cột (Key|Value), trả về dict {key_norm: value}"""
    if df.shape[1] < 2:
        # fallback: nếu file chỉ 1 cột dạng "Key: Value"
        df2 = df.copy()
        df2["__key__"] = df2.iloc[:,0].apply(lambda x: str(x).split(":",1)[0] if pd.notna(x) else "")
        df2["__val__"] = df2.iloc[:,0].apply(lambda x: str(x).split(":",1)[1] if (pd.notna(x) and ":" in str(x)) else "")
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
    # map theo số
    mapped = RESOLUTION_MAP.get(s.lower(), "")
    return mapped if mapped else raw

def _wifi_code(wireless: str) -> str:
    t = _to_str(wireless).upper()
    if not t: return ""
    if "6E" in t or "WI-FI 6E" in t or "WIFI 6E" in t: return "WF6E"
    if re.search(r"\b6\b", t) or "WI-FI 6" in t or "WIFI 6" in t: return "WF6"
    if re.search(r"\b5\b", t) or "WI-FI 5" in t or "WIFI 5" in t: return "WF5"
    if "WIFI" in t or "WI-FI" in t: return "WF"
    return ""

def _has_bt(wireless: str) -> bool:
    t = _to_str(wireless).upper()
    return "BT" in t or "BLUETOOTH" in t

def _touch_code(val: str) -> str:
    t = _to_str(val).lower()
    return "T" if any(x in t for x in ["yes","touch","capacitive","multi-touch","multi touch"]) else ""

def _bool_by_presence(val: str) -> bool:
    t = _to_str(val).lower()
    return bool(t) and t not in ("no", "không", "none", "n/a")

def _kbm_code(kb_mouse: str, included_box: str) -> str:
    src = f"{_to_str(kb_mouse)} {_to_str(included_box)}".lower()
    if not src.strip(): return ""
    tags = []
    # keyboard
    if "wireless keyboard" in src: tags.append("WL_KB")
    elif "keyboard" in src:       tags.append("KB")
    # mouse
    if "wireless mouse" in src:   tags.append("WL_M")
    elif "mouse" in src:          tags.append("M")
    return "&".join(tags) if tags else ""

def _os_code(os_text: str) -> str:
    t = _to_str(os_text).lower()
    if "windows 11 pro" in t:  return "W11P"
    if "windows 11 home" in t: return "W11H"
    return "NOS"  # bắt buộc có, thiếu => NOS

def _warranty_code(w_text: str) -> str:
    t = _to_str(w_text).lower()
    if not t: return ""
    m = re.search(r"(\d+)\s*(year|years|y)\b", t)
    year = f"{m.group(1)}Y" if m else ""
    wtype = ""
    if "on site" in t or "onsite" in t or "on-site" in t: wtype = "OSS"
    elif "pur" in t:                                     wtype = "PUR"
    return f"{year}-{wtype}" if (year and wtype) else ""

# ==== Core ====
def build_name_from_kv(kv: dict) -> str:
    parts = []

    # 1) Model: phần trước dấu '-' của "Sales Model Name" (bắt buộc)
    smn = _get(kv, "Sales Model Name")
    if not smn:
        raise ValueError("Thiếu 'Sales Model Name' trong specsheet.")
    model = smn.split("-", 1)[0].strip() if "-" in smn else smn.strip()
    parts.append(model)

    # 2) CPU
    cpu = _get(kv, "CPU", "Processor")
    if cpu: parts.append(cpu)

    # 3) RAM (Memory)
    ram = _get(kv, "Memory", "RAM")
    if ram: parts.append(ram)

    # 4) SSD
    ssd = _get(kv, "SSD")
    if ssd: parts.append(f"{ssd}-SSD")

    # 5) HDD (nếu có)
    hdd = _get(kv, "HDD")
    if hdd: parts.append(f"{hdd}-HDD")

    # 6) TPM (luôn có)
    parts.append("TPM")

    # 7) Display = Panel Size + Resolution (logic N/A nếu thiếu 1 nửa; nếu cả 2 thiếu thì bỏ)
    panel = _get(kv, "Panel Size")
    res   = _get(kv, "Resolution")
    res_norm = _normalize_resolution(res) if res else ""
    if panel or res_norm:
        if panel and res_norm:
            parts.append(f"{panel}{res_norm}")
        elif panel and not res_norm:
            parts.append(f"{panel}N/A")
        elif not panel and res_norm:
            parts.append(f"N/A{res_norm}")

    # 8) Touch (nếu có)
    touch = _touch_code(_get(kv, "Touch Panel", "Touchscreen", "Touch"))
    if touch: parts.append(touch)

    # 9) CAM (nếu có thông tin camera -> coi là có)
    cam = _get(kv, "Camera")
    if _bool_by_presence(cam): parts.append("CAM")

    # 10) MIC (nếu có)
    mic = _get(kv, "Microphone", "Mic")
    if _bool_by_presence(mic): parts.append("MIC")

    # 11) WF (nếu có)
    wireless = _get(kv, "Wireless", "Connectivity", "LAN/WLAN")
    wf = _wifi_code(wireless)
    if wf: parts.append(wf)

    # 12) BT (nếu có)
    if _has_bt(wireless): parts.append("BT")

    # 13) KB&M (từ "Keyboard & Mouse" hoặc "Included in the box")
    kbm = _kbm_code(_get(kv, "Keyboard & Mouse"), _get(kv, "Included in the box"))
    if kbm: parts.append(kbm)

    # 14) Windows (bắt buộc: nếu trống => NOS)
    parts.append(_os_code(_get(kv, "Operating System")))

    # 15) Warranty
    warr = _warranty_code(_get(kv, "Warranty", "Service"))
    if warr: parts.append(warr)

    # 16) Color
    color = _get(kv, "Color", "Colour")
    if color: parts.append(color)

    # 17) Sales Model (trong ngoặc): ưu tiên "Sales Model", nếu không có dùng "Sales Model Name"
    sales_model = _get(kv, "Sales Model")
    end_token = sales_model if sales_model else smn
    parts.append(f"({end_token})")

    return "/".join(parts)

def build_name_from_excel(path_xlsx: str) -> str:
    """Đọc file specsheet 2 cột và trả về tên sản phẩm theo rule."""
    df = pd.read_excel(path_xlsx, header=None)  # không dùng header vì file dạng Key|Value
    kv = _kv_map_from_specsheet(df)
    return build_name_from_kv(kv)

# --- Demo sử dụng ---
if __name__ == "__main__":
    # Ví dụ:
    # print(build_name_from_excel("V470VAT-BPF023W_90PT03W3-M02300_specsheet.xlsx"))
    pass

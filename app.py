# app.py
# Streamlit tool: Upload specsheet Excel (2 cột Key | Value) -> build tên sản phẩm theo rule
# Yêu cầu: streamlit, pandas, openpyxl, xlsxwriter
import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Product Name", page_icon="🧩")

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

#Color ID -> map sang tiếng Việt IN HOA có dấu
_ALLOWED_COLOR_MAP = {
    "BLACK": "ĐEN",
    "WHITE": "TRẮNG",
    "SILVER": "BẠC",
    "GRAY": "XÁM", "GREY": "XÁM", "GRAPHITE": "XÁM", "SPACE GRAY": "XÁM",
}

# từ “trang trí/marketing” để bỏ
_COLOR_ADJ = [
    "STAR", "STARRY", "STARLIGHT", "QUIET", "MOONLIGHT", "MATTE", "GLOSSY",
    "DARK", "LIGHT", "MIDNIGHT", "SPACE", "OCEAN", "FOREST", "MINT", "ICE",
    "SKY", "DEEP", "PURE", "SNOW",
]

def _group_prefix(group: str) -> str:
    g = (group or "").upper()
    mapping = {
        "NB":     "MÁY TÍNH XÁCH TAY (NB) ASUS",
        "PC":     "MÁY TÍNH ĐỂ BÀN (PC) ASUS",
        "AIO":    "MÁY TÍNH ĐỂ BÀN (PC) ASUS AIO",
        "SERVER": "MÁY CHỦ (SERVER) ASUS",
        "ACCY":   "(ACCY) ASUS",
    }
    return mapping.get(g, "")

import re

def simplify_battery(text: str, group: str) -> tuple[str, list]:
    """
    Battery (NB):
    - Cells: chỉ lấy từ "N-cell" (chấp nhận: 3-cell / 3 cell / 3cell / 3 cells / 3 cell(s))
    - WHr: chấp nhận WHr/WHrs/Wh/WH...
    """
    errors = []
    if not text:
        if group == "NB":
            errors.append("Thiếu Battery cho NB")
            return "N/A_Battery", errors
        return "", errors

    t = _to_str(text)

    # Cells: linh hoạt hơn
    m_cell = re.search(r"\b(\d+)\s*-?\s*cell(?:s|\(s\))?\b", t, flags=re.IGNORECASE)
    cells = m_cell.group(1) if m_cell else ""

    # WHr: linh hoạt hơn + chuẩn hoá
    m_wh = re.search(r"\b(\d{2,4})\s*W\s*H(?:\s*R)?(?:s)?\b", t, flags=re.IGNORECASE)
    wh = f"{int(m_wh.group(1))}WHr" if m_wh else ""

    if cells and wh:
        return f"{cells}C{wh}", errors
    if wh:
        return f"?C{wh}", errors
    if cells:
        return f"{cells}C??WHr", errors

    if group == "NB":
        errors.append("Không nhận dạng được Battery cho NB")
        return "N/A_Battery", errors
    return "", errors




def _extract_base_color_token(text: str) -> str:
    """
    Trả về token màu gốc đầu tiên (BLACK/WHITE/SILVER/GRAY/BLUE/RED/...)
    - Bỏ tính từ marketing
    - Tách theo / , + ; & 'and'
    """
    t = _to_str(text).upper()
    if not t:
        return ""

    # gom nhiều key 'color/colour' → tách thành mảnh để giữ thứ tự
    chunks = re.split(r"[\/,+;&]|\band\b", t)
    for raw in chunks:
        s = raw.strip()
        if not s:
            continue
        for adj in _COLOR_ADJ:
            s = re.sub(rf"\b{re.escape(adj)}\b", " ", s)
        s = re.sub(r"\s+", " ", s).strip()

        # ưu tiên cụm 2 từ như SPACE GRAY trước
        for k in sorted(_ALLOWED_COLOR_MAP.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(k)}\b", s):
                return k

        # nếu không rơi vào allowed, vẫn cố gắng nhận BLUE/GREEN/... để ghi N/A_<COLORID>
        m = re.search(r"\b(BLACK|WHITE|SILVER|GRAY|GREY|GRAPHITE|BLUE|GREEN|RED|ORANGE|PURPLE|VIOLET|PINK|ROSE|GOLD|BROWN)\b", s)
        if m:
            return m.group(1)

    return ""

def simplify_color_from_kv(kv: dict) -> str:
    """
    - Tìm value từ mọi key chứa 'color' hoặc 'colour'
    - Lấy màu đầu tiên
    - Nếu thuộc 4 nhóm hợp lệ -> trả VI (ĐEN/TRẮNG/BẠC/XÁM)
    - Nếu ra màu khác -> trả 'N/A_<COLORID>' (vd N/A_BLUE)
    - Nếu không thấy -> trả ""
    """
    values = []
    for k_norm, v in kv.items():
        if "color" in k_norm or "colour" in k_norm:
            if _to_str(v):
                values.append(str(v))
    if not values:
        return ""

    token = _extract_base_color_token(" / ".join(values))
    if not token:
        return ""

    if token in _ALLOWED_COLOR_MAP:
        return _ALLOWED_COLOR_MAP[token]  # ĐEN/TRẮNG/BẠC/XÁM
    else:
        return token  # ví dụ: BLUE, GREEN, RED...


def _to_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none", "null", "-") else s

def _norm_key(s: str) -> str:
    s = _to_str(s).lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("&", "and")
    return s

def _kv_map_from_specsheet(df: pd.DataFrame) -> dict:
    """
    Nhận DataFrame specsheet 2 cột (Key|Value), trả về dict {key_norm: value}
    - Nếu >2 cột: dùng 2 cột đầu
    - Nếu chỉ 1 cột dạng "Key: Value" thì cố gắng tách
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
    # đã là mã (FHD/WUXGA/...) -> giữ
    if s in {v.upper() for v in RESOLUTION_MAP.values()}:
        return s
    # map theo số: 1920x1080 -> FHD ...
    mapped = RESOLUTION_MAP.get(s.lower(), "")
    return mapped if mapped else raw

def simplify_cpu(text: str) -> str:
    t = text.replace("®", "").replace("™", "").strip()

    # Rule 1: Core i3/i5/i7/i9
    m = re.search(r"(i[3579]-\d+[A-Za-z0-9]*)", t)
    if m:
        return m.group(1)

    # Rule 2: Core Ultra
    m2 = re.search(r"Ultra\s*(\d+)\s*([0-9]{3}[A-Za-z0-9]*)", t, re.I)
    if m2:
        return f"Ultra {m2.group(1)}-{m2.group(2)}"

    # Rule 3: Core (chỉ số thế hệ, không có i, không Ultra)
    m3 = re.search(r"Core\s+(\d+)\s*Processor\s*([0-9]{3}[A-Za-z0-9]*)", t, re.I)
    if m3:
        return f"Core {m3.group(1)}-{m3.group(2)}"

    # fallback: giữ nguyên
    return t

def simplify_ram(text: str) -> str:
    """
    Chuẩn hóa RAM: <Dung lượng><DDR>*<Số thanh nếu >1>
    - "16GB DDR5 5600MHz (2x8GB DIMM)" -> "16GD5*2"
    - "8GB DDR4" -> "8GD4"
    - "32GB LPDDR5X" -> "32GD5X"
    - "16GB DDR5 SO-DIMM" -> "16GD5"
    - "8GB DDR5 U-DIMM *2" -> "8GD5*2"
    """
    t = _to_str(text).upper()

    # dung lượng (GB)
    m_total = re.search(r"(\d+)\s*GB", t)
    size = f"{m_total.group(1)}G" if m_total else ""

    # loại DDR
    ddr = ""
    if "LPDDR5X" in t:
        ddr = "D5X"
    elif "DDR5" in t:
        ddr = "D5"
    elif "DDR4" in t:
        ddr = "D4"

    # số thanh (pattern 2x8GB, 4x…)
    m_stick = re.search(r"(\d+)X\d+\s*GB", t)
    qty = m_stick.group(1) if m_stick else ""

    # build kết quả
    result = size + ddr
    if qty and qty != "1":
        result += f"*{qty}"
    return result if result else t

#Chuẩn hóa cách đọc SSD - Storage
from collections import OrderedDict


def _ssd_parse_counts(text: str, assume_is_ssd: bool = False) -> OrderedDict:
    """
    Trả về OrderedDict { '512G': 2, '256G': 1, '1T': 1, ... } theo đúng thứ tự xuất hiện.
    - Chỉ lấy các cụm dung lượng SSD trong 'text'.
    - Nếu assume_is_ssd=True (ví dụ key là 'SSD'), coi toàn bộ text là SSD, không cần từ 'SSD'.
    - Không chuyển GB<->TB; chỉ đổi đuôi: GB->G, TB->T.
    """
    t = _to_str(text).upper()
    if not t:
        return OrderedDict()

    # nếu không assume và text không có 'SSD' -> bỏ
    if not assume_is_ssd and "SSD" not in t:
        return OrderedDict()

    # tách theo + / , ; & để giữ thứ tự xuất hiện từng mảnh
    chunks = re.split(r"[+,/;&]", t)

    counts = OrderedDict()
    def add(size_num: str, unit: str, qty: int):
        # unit = GB|TB -> G|T
        unit_short = "G" if unit == "GB" else "T"
        key = f"{size_num}{unit_short}"
        if key not in counts:
            counts[key] = 0
        counts[key] += qty

    for raw in chunks:
        c = raw.strip()
        if not c:
            continue
        if (not assume_is_ssd) and ("SSD" not in c):
            # với chunks từ 'Storage'… chỉ nhận mảnh có SSD
            continue

        # Pattern 1: 2x512GB | 3x1TB
        for m in re.finditer(r"(\d+)\s*[Xx]\s*(\d+)\s*(GB|TB)", c):
            qty = int(m.group(1))
            size = m.group(2)
            unit = m.group(3)
            add(size, unit, qty)

        # Pattern 2: 512GB*2 | 1TB * 3
        for m in re.finditer(r"(\d+)\s*(GB|TB)\s*\*\s*(\d+)", c):
            size = m.group(1)
            unit = m.group(2)
            qty  = int(m.group(3))
            add(size, unit, qty)

        # Pattern 3: đơn lẻ 512GB | 1TB (không có *n hay 2x…)
        # tránh đếm trùng những cái đã match ở trên nên ta remove tạm thời rồi quét nốt phần còn lại
        c_tmp = re.sub(r"(\d+\s*[Xx]\s*\d+\s*(GB|TB))", " ", c)
        c_tmp = re.sub(r"(\d+\s*(GB|TB)\s*\*\s*\d+)", " ", c_tmp)
        for m in re.finditer(r"(\d+)\s*(GB|TB)", c_tmp):
            size = m.group(1)
            unit = m.group(2)
            add(size, unit, 1)

    return counts

def _ssd_format_output(counts: OrderedDict) -> str:
    """
    Biến counts -> chuỗi theo rule:
    - Nếu chỉ 1 loại dung lượng: 512G-SSD hoặc 512G-SSD*2
    - Nếu nhiều loại: 512G+256G*2-SSD (nối bằng '+', mỗi loại có *qty nếu >1, '-SSD' ở cuối)
    """
    if not counts:
        return ""
    parts = []
    for size, qty in counts.items():
        if qty > 1:
            parts.append(f"{size}*{qty}")
        else:
            parts.append(size)
    return "+".join(parts) + "-SSD"


def simplify_display(panel: str, res: str, group: str) -> tuple[str, list]:
    """
    Chuẩn hóa Display theo rule:
    - Panel Size: chuẩn hóa xx.x (1 chữ số thập phân).
    - Resolution: giữ nguyên FHD/WUXGA/...; nếu chỉ số thì giữ nguyên dạng số.
    - Ghép thành <size><res>.
    - Nếu thiếu 1 phần -> thêm N/A.
    - Nếu thiếu cả 2 -> bỏ qua (trừ NB/AIO thì báo lỗi).
    """
    errors = []

    panel_val = ""
    res_val = ""

    # --- Panel Size ---
    if panel:
        m = re.search(r"(\d+[.,]?\d*)", str(panel))
        if m:
            try:
                panel_num = float(m.group(1).replace(",", "."))
                panel_val = f"{panel_num:.1f}"  # 1 số thập phân
            except:
                panel_val = "N/A"
        else:
            panel_val = "N/A"

    # --- Resolution ---
    if res:
        r = str(res).upper()
        # lấy các từ khoá gọn
        if any(short in r for short in ["FHD", "WUXGA", "WQXGA", "QHD", "4K"]):
            if "FHD" in r: res_val = "FHD"
            elif "WUXGA" in r: res_val = "WUXGA"
            elif "WQXGA" in r: res_val = "WQXGA"
            elif "QHD" in r: res_val = "QHD"
            elif "4K" in r: res_val = "4K"
        else:
            # nếu chỉ có dạng số (1920x1080 …) thì giữ nguyên
            m = re.search(r"\d{3,4}x\d{3,4}", r)
            if m:
                res_val = m.group(0)
            else:
                res_val = "N/A"

    # --- Build result ---
    if not panel_val and not res_val:
        # thiếu cả 2
        if group in {"NB", "AIO"}:
            errors.append(f"Thiếu Display (Panel Size/Resolution) cho nhóm {group}")
        return "", errors
    elif panel_val and res_val:
        return f"{panel_val}{res_val}", errors
    elif panel_val and not res_val:
        return f"{panel_val}N/A", errors
    elif not panel_val and res_val:
        return f"N/A{res_val}", errors


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

def simplify_psu(text: str) -> str:
    """
    Chuẩn hóa PSU: <Watt>*<qty>
    - "180W" -> "180W"
    - "2x180W" -> "180W*2"
    - "180W*3" -> "180W*3"
    """
    t = _to_str(text).upper()
    if not t:
        return ""

    # pattern 2x180W
    m = re.search(r"(\d+)[Xx]\s*(\d+)\s*W", t)
    if m:
        qty = m.group(1)
        watts = m.group(2)
        return f"{watts}W*{qty}"

    # pattern 180W*3
    m = re.search(r"(\d+)\s*W\s*\*\s*(\d+)", t)
    if m:
        watts = m.group(1)
        qty = m.group(2)
        return f"{watts}W*{qty}"

    # pattern đơn lẻ 180W
    m = re.search(r"(\d+)\s*W", t)
    if m:
        return f"{m.group(1)}W"

    return ""


def _truthy(val: str) -> bool:
    t = _to_str(val).lower()
    return bool(t) and t not in ("no", "không", "none", "n/a", "na", "0")

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
    """
    Chuẩn hóa hệ điều hành:
    1. Có 'Windows 11 Home' -> W11H
    2. Có 'Windows 11 Pro' (mà không có Home) -> W11P
    3. Có 'Windows' nhưng không rõ Home/Pro -> WIN
    4. Nếu trống -> NOS
    """
    t = _to_str(os_text).upper()
    if not t:
        return "NOS"

    if "WINDOWS 11 HOME" in t:
        return "W11H"
    if "WINDOWS 11 PRO" in t:
        return "W11P"
    if "WINDOWS" in t:
        return "WIN"

    return "NOS"

def _warranty_code_from_text(txt: str) -> str:
    """
    Format: ?Y-Type
    Type:
      - Onsite / On-site / On site / on_site / OSS  -> OSS
      - PUR / Pick up and return                    -> PUR
    """
    if not txt:
        return "Warranty_input"

    
    t = _to_str(txt)  # giữ nguyên, dùng re.I để không phân biệt hoa/thường

    # years: '3Y', '3 Y', '3y'...
    m_year = re.search(r"(\d+)\s*Y\b", t, flags=re.I)
    years = m_year.group(1) if m_year else "?"

    is_onsite = bool(
        re.search(r"\bon[\s\-_]*site\b", t, flags=re.I) or
        re.search(r"\boss\b", t, flags=re.I)
    )
    is_pur = bool(
        re.search(r"\bPUR\b", t, flags=re.I) or
        re.search(r"\bpick[\s\-_]*up[\s\-_]*and[\s\-_]*return\b", t, flags=re.I)
    )

    if is_onsite:
        return f"{years}Y-OSS"
    if is_pur:
        return f"{years}Y-PUR"
    return "Warranty_input"

def _warranty_code_from_kv(kv: dict) -> str:
    # Ưu tiên 'Base Warranty', nếu không có thì lấy dòng đầu tiên có chữ 'warranty' trong key.
    val = _get(kv, "Base Warranty")
    if not val:
        for k_norm, v in kv.items():
            if "warranty" in k_norm:
                val = v
                break
    return _warranty_code_from_text(val)



# =========================
# Core build logic
# =========================
def build_name_from_kv(kv: dict, group: str):
    errors = []
    
    """
    Note: chưa hoàn thiện logic HDD, wireless KB&M,GPU warranty
    """
    parts = []

    # 1) Model — phần trước '-' của "Sales Model Name" (bắt buộc)
    smn = _get(kv, "Sales Model Name")
    if not smn:
        raise ValueError("Thiếu 'Sales Model Name' trong specsheet.")
    model = smn.split("-", 1)[0].strip() if "-" in smn else smn.strip()
    parts.append(model)

    # 2) CPU
    cpu_raw = ""
    for k, v in kv.items():
        if "processor" in k:   # match bất kỳ key chứa chữ processor
            cpu_raw = v
            break
    if cpu_raw:
        parts.append(simplify_cpu(cpu_raw))


    # 3) RAM
    ram_raw = _get(kv, "Memory", "RAM", "System Memory", "Installed Memory", "DIMM Memory")
    if ram_raw:
        parts.append(simplify_ram(ram_raw))

    # 4) SSD — dedupe nguồn + parse theo rule
    ssd_counts = OrderedDict()
    seen_values = set()

    SSD_KEYS = {"SSD", "Solid State Drive"}
    STO_KEYS = {"Storage", "Primary Storage", "Storage 1", "Storage 2", "Drive Capacity"}

    for kname in list(SSD_KEYS) + list(STO_KEYS):
        val = _get(kv, kname)
        val_norm = _to_str(val)
        if not val_norm:
            continue
        # ❗ tránh đếm 2 lần cùng một chuỗi (ví dụ cả ở SSD và Storage)
        if val_norm in seen_values:
            continue
        seen_values.add(val_norm)

        cdict = _ssd_parse_counts(val_norm, assume_is_ssd=(kname in SSD_KEYS))
        for k, v in cdict.items():
            ssd_counts[k] = ssd_counts.get(k, 0) + v

    ssd_out = _ssd_format_output(ssd_counts)
    if ssd_out:
        parts.append(ssd_out)


    # 5) HDD (nếu có)
    hdd = _get(kv, "HDD")
    if hdd: parts.append(f"{hdd}-HDD")

    # 6) TPM (luôn có)
    parts.append("TPM")

    # 7) Display = Panel Size + Resolution (chuẩn hóa; thiếu 1 nửa -> N/A; thiếu cả 2 -> bỏ)
    panel = _get(kv, "Panel Size")
    res   = _get(kv, "Resolution")
    display, errs = simplify_display(panel, res, group)
    if display:
        parts.append(display)
    errors.extend(errs)


    # 8) Touch — chỉ với nhóm NB/AIO, value "Touch screen"
    if group in {"NB", "AIO"}:
        touch_val = _get(kv, "Touch Panel")
        if touch_val:
            tv = str(touch_val).strip().lower()
        # chặn các phủ định trước
            negatives = ["non-touch", "non touch", "without touch", "no touch"]
            is_negative = any(n in tv for n in negatives)
        # chỉ chấp nhận đúng "touch screen" (không dính phủ định)
            is_touch = (not is_negative) and bool(re.search(r"\btouch\s*screen\b", tv, flags=re.I))
            if is_touch:
                parts.append("T")
    # PC/Server/ACCY: bỏ qua Touch

    # 9) CAM & MIC — auto cho AIO
    if group == "AIO":
        parts.append("CAM")
        parts.append("MIC")

    # 10) Power Supply — bắt buộc cho PC/Server
    psu_raw = _get(kv, "Power Supply")
    psu = simplify_psu(psu_raw)

    if psu:
        parts.append(psu)
    else:
        if group in {"PC", "Server"}:
            parts.append("PSU_N/A")
            errors.append(f"Thiếu Power Supply cho nhóm {group}")

    # 10) Battery - bắt buộc cho NB
    battery, berrs = simplify_battery(_get(kv, "Battery"), group)
    if battery:
        parts.append(battery)
    errors.extend(berrs)


    # 11) WF + 12) BT (từ dòng Wireless)
    wireless = _get(kv, "Wireless", "Connectivity", "LAN/WLAN")
    wf = _wifi_code(wireless)
    if wf: parts.append(wf)
    if _has_bt(wireless): parts.append("BT")

    # 13) KB&M (Keyboard & Mouse hoặc Included in the box)
    kbm = _kbm_code(_get(kv, "Keyboard & Mouse", "Keyboard and Mouse"),
                    _get(kv, "Included in the box"))
    if kbm: parts.append(kbm)

    # 14) Windows (bắt buộc -> nếu trống => NOS)
    parts.append(_os_code(_get(kv, "Operating System")))

    # 15) Warranty
    warr = _warranty_code_from_kv(kv)
    if warr:
        parts.append(warr)


    # 16) Color

    # Color — key nào có COLOR/COLOUR đều lấy; chỉ chấp nhận 4 màu, còn lại -> N/A_<COLORID>
    color_token = simplify_color_from_kv(kv)
    if color_token:
        parts.append(color_token)
    else:
        parts.append("N/A_Color")
        errors.append("Thiếu Color")


    # 17) Sales Model (trong ngoặc) — ưu tiên "Sales Model", nếu không có thì dùng "Sales Model Name"
    sales_model = _get(kv, "Sales Model")
    end_token = sales_model if sales_model else smn
    parts.append(f"({end_token})")

    final_name = "/".join(parts)

    prefix = _group_prefix(group)
    if prefix:
        final_name = f"{prefix} {final_name}"

    return final_name, errors

# =========================
# Streamlit UI (Upload file)
# =========================
st.title("🧩 Product Name Builder")

# 🔽 Chọn nhóm sản phẩm (không chọn thì không chạy)
group = st.selectbox(
    "Chọn nhóm sản phẩm",
    options=["NB", "PC", "AIO", "Server", "ACCY"],
    index=None,  # không mặc định
    placeholder="Chọn nhóm…"
)


# ⛔️ Yêu cầu: phải có file + đã chọn nhóm
#if uploaded is None or group is None:
if group is None:
    if group is None:
        st.info("🔽⬆️ Chọn nhóm sản phẩm")
    
    st.stop()

# 📤 Upload file
uploaded = st.file_uploader("Upload specsheet (.xlsx)", type=["xlsx"])

if uploaded is None:
    if uploaded is None:
        st.info("🔼 Upload file Excel specsheet")
    st.stop()

# ✅ Đủ điều kiện -> xử lý
raw_df = pd.read_excel(uploaded, header=None)
kv = _kv_map_from_specsheet(raw_df)

name, errors = build_name_from_kv(kv, group=group)  # nhớ sửa chữ ký hàm nhận group và trả (name, errors)

st.subheader("✅ Result")
st.code(name, language="text")
if errors:
    st.warning("⚠️ " + " | ".join(errors))

with st.expander("👀 Xem nhanh file input"):
    st.dataframe(raw_df)
with st.expander("🛠 Keys đã đọc (debug)"):
    st.write(kv)






























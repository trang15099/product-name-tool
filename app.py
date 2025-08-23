import pandas as pd

# Mapping độ phân giải sang code
RESOLUTION_MAP = {
    "1366x768": "HD",
    "1920x1080": "FHD",
    "1920x1200": "WUXGA",
    "2560x1440": "QHD",
    "2560x1600": "WQXGA",
    "3840x2160": "4K"
}

def normalize_resolution(res):
    if pd.isna(res):
        return None
    res = str(res).upper().replace(" ", "")
    for k, v in RESOLUTION_MAP.items():
        if k in res or v in res:
            return v
    return "N/A"

def build_name(row):
    parts = []

    # 1. Model
    if not pd.isna(row.get("Model")):
        parts.append(str(row["Model"]).strip())

    # 2. CPU
    if not pd.isna(row.get("CPU")):
        parts.append(str(row["CPU"]).strip())

    # 3. RAM
    if not pd.isna(row.get("Memory")):
        parts.append(str(row["Memory"]).strip())

    # 4. SSD
    if not pd.isna(row.get("SSD")):
        parts.append(f"{row['SSD']}-SSD")

    # 5. HDD
    if not pd.isna(row.get("HDD")):
        parts.append(f"{row['HDD']}-HDD")

    # 6. TPM (luôn có)
    parts.append("TPM")

    # 7. Display
    panel = row.get("Panel Size")
    res = row.get("Resolution")
    res_norm = normalize_resolution(res)

    if pd.isna(panel) and pd.isna(res):
        pass
    elif pd.isna(panel):
        parts.append(f"N/A{res_norm}")
    elif pd.isna(res):
        parts.append(f"{panel}N/A")
    else:
        parts.append(f"{panel}{res_norm}")

    # 8. Touch
    if not pd.isna(row.get("Touch Panel")):
        parts.append("T")

    # 9. Camera
    if not pd.isna(row.get("Camera")):
        parts.append("CAM")

    # 10. Mic
    if not pd.isna(row.get("Microphone")):
        parts.append("MIC")

    # 11-12. Wireless & BT
    wireless = str(row.get("Wireless", "")).upper()
    if "WIFI" in wireless or "WI-FI" in wireless:
        if "6E" in wireless:
            parts.append("WF6E")
        elif "6" in wireless:
            parts.append("WF6")
        elif "5" in wireless:
            parts.append("WF5")
    if "BT" in wireless or "BLUETOOTH" in wireless:
        parts.append("BT")

    # 13. Keyboard & Mouse
    kbm = str(row.get("Keyboard & Mouse") or row.get("Included in the box") or "").upper()
    kb_parts = []
    if "WIRELESS KEYBOARD" in kbm:
        kb_parts.append("WL_KB")
    elif "KEYBOARD" in kbm:
        kb_parts.append("KB")
    if "WIRELESS MOUSE" in kbm:
        kb_parts.append("WL_M")
    elif "MOUSE" in kbm:
        kb_parts.append("M")
    if kb_parts:
        parts.append("&".join(kb_parts))

    # 14. Windows
    osys = str(row.get("Operating System") or "").upper()
    if "WINDOWS 11 HOME" in osys:
        parts.append("W11H")
    elif "WINDOWS 11 PRO" in osys:
        parts.append("W11P")
    else:
        parts.append("NOS")

    # 15. Warranty
    warranty = str(row.get("Warranty") or "").upper()
    if "3" in warranty:
        year = "3Y"
    elif "2" in warranty:
        year = "2Y"
    elif "1" in warranty:
        year = "1Y"
    else:
        year = ""
    if "ON SITE" in warranty:
        parts.append(f"{year}-OSS")
    elif "PUR" in warranty:
        parts.append(f"{year}-PUR")

    # 16. Color
    if not pd.isna(row.get("Color")):
        parts.append(str(row["Color"]).strip())

    # 17. Sales Model
    if not pd.isna(row.get("Sales Model")):
        parts.append(f"({row['Sales Model']})")

    return "/".join(parts)

def process_excel(file_path, output_path="output.csv"):
    df = pd.read_excel(file_path)
    df["GeneratedName"] = df.apply(build_name, axis=1)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"✅ Done! Kết quả được lưu vào {output_path}")

if __name__ == "__main__":
    # Chạy thử với file test.xlsx
    process_excel("test.xlsx")

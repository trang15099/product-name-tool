import streamlit as st
import pandas as pd

# ----------------
# RULES XỬ LÝ TÊN
# ----------------
def build_name(row):
    parts = []

    # 1. Model
    if "Model" in row and pd.notna(row["Model"]):
        parts.append(str(row["Model"]).strip())

    # 2. CPU
    if "CPU" in row and pd.notna(row["CPU"]):
        parts.append(str(row["CPU"]).strip())

    # 3. RAM
    if "RAM" in row and pd.notna(row["RAM"]):
        parts.append(str(row["RAM"]).strip())

    # 4. SSD
    if "SSD" in row and pd.notna(row["SSD"]):
        parts.append(str(row["SSD"]).strip())

    # 5. HDD
    if "HDD" in row and pd.notna(row["HDD"]):
        parts.append(str(row["HDD"]).strip())

    # 6. TPM (luôn có)
    if "TPM" in row and pd.notna(row["TPM"]):
        parts.append(str(row["TPM"]).strip())

    # 7. Display = Panel Size + Resolution
    panel = str(row.get("Panel Size", "")).strip()
    res = str(row.get("Resolution", "")).strip()

    if panel and res:
        if res.upper() in ["FHD", "WUXGA", "WQXGA"]:
            parts.append(f"{panel}{res.upper()}")
        else:
            parts.append(f"{panel}{res}")  
    elif panel and not res:
        parts.append(f"{panel}N/A")
    elif res and not panel:
        parts.append(f"N/A{res}")

    # 8. Touch
    if "Touch panel" in row and pd.notna(row["Touch panel"]):
        if str(row["Touch panel"]).lower() == "yes":
            parts.append("T")

    # 9. CAM
    if "Camera" in row and pd.notna(row["Camera"]):
        parts.append("CAM")

    # 10. MIC
    if "Microphone" in row and pd.notna(row["Microphone"]):
        parts.append("MIC")

    # 11. Wireless (WF + BT)
    if "Wireless" in row and pd.notna(row["Wireless"]):
        wireless_val = str(row["Wireless"]).upper()
        if "WF" in wireless_val:
            parts.append("WF6E")
        if "BT" in wireless_val:
            parts.append("BT")

    # 12. Keyboard & Mouse
    kb_mouse = str(row.get("Keyboard & Mouse", row.get("Included in the box", ""))).lower()
    kb_parts = []
    if "wireless keyboard" in kb_mouse:
        kb_parts.append("WL_KB")
    elif "keyboard" in kb_mouse:
        kb_parts.append("KB")

    if "wireless mouse" in kb_mouse:
        kb_parts.append("WL_M")
    elif "mouse" in kb_mouse:
        kb_parts.append("M")

    if kb_parts:
        parts.append("&".join(kb_parts))

    # 13. Windows
    os_val = str(row.get("Operating System", "")).strip()
    if "windows 11 home" in os_val.lower():
        parts.append("W11H")
    elif "windows 11 pro" in os_val.lower():
        parts.append("W11P")
    elif os_val == "" or os_val.lower() == "nan":
        parts.append("NOS")

    # 14. Warranty
    warranty_val = str(row.get("Warranty", "")).strip().lower()
    if warranty_val:
        year = ""
        wtype = ""
        for token in warranty_val.split():
            if "year" in token:
                year = token.replace("year", "").replace("years", "").strip() + "Y"
            if "oss" in token or "on site" in token:
                wtype = "OSS"
            if "pur" in token:
                wtype = "PUR"
        if year and wtype:
            parts.append(f"{year}-{wtype}")

    # 15. Color
    if "Color" in row and pd.notna(row["Color"]):
        parts.append(str(row["Color"]).strip())

    # 16. Sales Model (luôn nằm cuối, trong ngoặc)
    if "Sales Model" in row and pd.notna(row["Sales Model"]):
        parts.append(f"({str(row['Sales Model']).strip()})")

    return "/".join(parts)


# ----------------
# STREAMLIT APP
# ----------------
st.title("📦 Product Name Builder")

uploaded_file = st.file_uploader("Upload file Excel", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.success("✅ File uploaded successfully!")
        st.dataframe(df.head())  

        # Build tên sản phẩm
        df["Generated Name"] = df.apply(build_name, axis=1)

        st.subheader("📋 Generated Product Names")
        st.dataframe(df[["Generated Name"]])

        # Download kết quả
        output_file = "generated_names.xlsx"
        df.to_excel(output_file, index=False)

        with open(output_file, "rb") as f:
            st.download_button(
                label="💾 Download Excel",
                data=f,
                file_name="generated_names.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Lỗi khi xử lý file: {e}")
else:
    st.info("⬆️ Vui lòng upload file Excel để bắt đầu.")

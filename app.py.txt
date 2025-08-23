import streamlit as st
import pandas as pd

# Hàm build tên sản phẩm theo format
def build_product_name(row):
    return (
        f"MÁY TÍNH ĐỂ BÀN (PC) ASUS AIO {row['Model']} "
        f"Core{row['CPU']}/{row['RAM']}D5/{row['SSD']}-SSD/TPM/"
        f"{row['Display']}/T/CAM/MIC/WF6E/BT/KB&M/W11H/3Y-OSS/"
        f"{row['Color']}({row['Sales Model']})"
    )

st.title("ASUS Product Name Generator")

uploaded_file = st.file_uploader("Upload specsheet Excel", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    st.write("📑 Dữ liệu gốc:")
    st.dataframe(df)

    # Tạo cột mới Product Name
    df["Product Name"] = df.apply(build_product_name, axis=1)

    st.write("✅ Kết quả sinh Product Name:")
    st.dataframe(df[["Product Name"]])

    # Xuất ra file Excel
    output_file = "output_with_product_name.xlsx"
    df.to_excel(output_file, index=False)

    with open(output_file, "rb") as f:
        st.download_button("⬇️ Tải về file kết quả", f, file_name="ProductName.xlsx")

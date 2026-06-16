import os
import base64
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import qrcode
import streamlit as st


st.set_page_config(
    page_title="Student Registry QR",
    page_icon="🆔",
    layout="centered"
)

CREATED_CSV = os.path.join(os.path.expanduser("~"), "created_csv.csv")


def bkk_now():
    return datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")


def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()

    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file, dtype=str).fillna("")
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file, dtype=str).fillna("")
    else:
        st.error("รองรับเฉพาะ CSV หรือ Excel")
        st.stop()


def load_created_csv():
    cols = ["first_name", "last_name", "citizen_ID", "student_ID", "timestamp_BKK"]

    if os.path.exists(CREATED_CSV):
        return pd.read_csv(CREATED_CSV, dtype=str).fillna("")

    return pd.DataFrame(columns=cols)


def append_created_csv(row):
    df_old = load_created_csv()

    if row["student_ID"] in df_old["student_ID"].astype(str).values:
        st.error("student_ID นี้ถูกลงทะเบียนแล้ว")
        st.stop()

    if row["citizen_ID"] in df_old["citizen_ID"].astype(str).values:
        st.error("citizen_ID นี้ถูกลงทะเบียนแล้ว")
        st.stop()

    df_new = pd.concat([df_old, pd.DataFrame([row])], ignore_index=True)
    df_new.to_csv(CREATED_CSV, index=False, encoding="utf-8-sig")
    return df_new


def make_qr_png(student_id):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(student_id)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def print_a4(first_name, last_name, student_id, qr_img, timestamp):
    qr_base64 = base64.b64encode(qr_img.getvalue()).decode()

    html = f"""
    <html>
    <body style="
        font-family: Arial, sans-serif;
        text-align: center;
        padding: 40px;
    ">
        <h1>Student Physical Exam 2026</h1>
        <h2>{first_name} {last_name}</h2>
        <h2>Student ID: {student_id}</h2>

        <img src="data:image/png;base64,{qr_base64}" width="360">

        <h2 style="margin-top:30px;">
            กรุณาถือ QR Code นี้ติดตัวไปตลอดการตรวจทุกสถานี
        </h2>

        <p>Generated: {timestamp} BKK</p>

        <script>
            window.print();
        </script>
    </body>
    </html>
    """

    st.components.v1.html(html, height=750)


st.title("🆔 Student Registry & QR Code: KU KPS Infirmary")
st.caption("Upload รายชื่อ → Search → ลงทะเบียน → สร้าง QR → บันทึก created_csv.csv")

st.warning(
    "ไฟล์ที่ Upload จะไม่ถูกแก้ไข โปรแกรมจะสร้าง/append เฉพาะไฟล์ created_csv.csv "
    "ใน home folder ของเครื่องหรือ container เท่านั้น"
)

uploaded_file = st.file_uploader(
    "Upload registered_students.csv หรือ Excel ที่มี first_name และ last_name",
    type=["csv", "xlsx", "xls"]
)

if uploaded_file:
    df = read_uploaded_file(uploaded_file)

    required_cols = ["first_name", "last_name"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(f"ไฟล์ขาด column: {missing}")
        st.stop()

    df["first_name"] = df["first_name"].astype(str).fillna("")
    df["last_name"] = df["last_name"].astype(str).fillna("")
    df["display_name"] = df["first_name"] + " " + df["last_name"]

    st.success(f"โหลดรายชื่อแล้ว {len(df)} ราย")
    st.dataframe(df[["first_name", "last_name"]], use_container_width=True)

    st.divider()

    keyword = st.text_input("ค้นหา first_name หรือ last_name")

    selected_first = ""
    selected_last = ""

    if keyword:
        mask = (
            df["first_name"].str.contains(keyword, case=False, na=False) |
            df["last_name"].str.contains(keyword, case=False, na=False) |
            df["display_name"].str.contains(keyword, case=False, na=False)
        )

        result = df[mask].copy()

        if not result.empty:
            st.success(f"พบ {len(result)} ราย")

            selected_display = st.selectbox(
                "เลือกนักศึกษา",
                result["display_name"].tolist()
            )

            selected_row = result[result["display_name"] == selected_display].iloc[0]
            selected_first = selected_row["first_name"]
            selected_last = selected_row["last_name"]

        else:
            st.error("ไม่พบรายชื่อ สามารถกรอกใหม่เพื่อ append เข้า created_csv.csv ได้")
            selected_first = st.text_input("first_name ใหม่")
            selected_last = st.text_input("last_name ใหม่")

    st.divider()

    st.subheader("ลงทะเบียน")

    first_name = st.text_input("first_name", value=selected_first)
    last_name = st.text_input("last_name", value=selected_last)
    citizen_id = st.text_input("citizen_ID", type="password")
    student_id = st.text_input("student_ID")

    confirm = st.checkbox("ยืนยันว่าข้อมูลถูกต้องแล้ว")

    if st.button("บันทึกและสร้าง QR Code"):
        if not first_name or not last_name or not citizen_id or not student_id:
            st.error("กรุณากรอกข้อมูลให้ครบ")
            st.stop()

        if not confirm:
            st.error("กรุณาติ๊กยืนยันก่อน")
            st.stop()

        timestamp = bkk_now()

        row = {
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "citizen_ID": citizen_id.strip(),
            "student_ID": student_id.strip(),
            "timestamp_BKK": timestamp
        }

        created_df = append_created_csv(row)

        st.success(f"บันทึกลง created_csv.csv แล้ว: {CREATED_CSV}")

        qr_img = make_qr_png(student_id.strip())

        st.subheader("QR Code")
        st.image(qr_img, width=320)

        print_a4(
            first_name=row["first_name"],
            last_name=row["last_name"],
            student_id=row["student_ID"],
            qr_img=qr_img,
            timestamp=timestamp
        )

        st.download_button(
            "ดาวน์โหลด QR Code PNG",
            data=qr_img,
            file_name=f"QR_{student_id}.png",
            mime="image/png"
        )

        st.download_button(
            "ดาวน์โหลด created_csv.csv",
            data=created_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="created_csv.csv",
            mime="text/csv"
        )

st.divider()

st.subheader("ดู created_csv.csv ปัจจุบัน")

created_now = load_created_csv()
st.dataframe(created_now, use_container_width=True)

if not created_now.empty:
    st.download_button(
        "ดาวน์โหลด created_csv.csv ล่าสุด",
        data=created_now.to_csv(index=False, encoding="utf-8-sig"),
        file_name="created_csv.csv",
        mime="text/csv"
    )

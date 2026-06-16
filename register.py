import base64
import hmac
import hashlib
import os
from io import BytesIO
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import qrcode
import streamlit as st
import streamlit.components.v1 as components

# Optional for local testing. Streamlit Cloud will use st.secrets if available.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

st.set_page_config(
    page_title="Student Registry QR",
    page_icon="🆔",
    layout="wide",
)

# ---------------- CONFIG ----------------
APP_DIR = Path(__file__).resolve().parent
REGISTERED_CSV = APP_DIR / "registed_students.csv"  # spelling follows user's request

QR_SECRET = st.secrets.get("QR_SECRET", os.getenv("QR_SECRET", "change_this_secret"))
CHECKLIST_BASE_URL = st.secrets.get(
    "CHECKLIST_BASE_URL",
    os.getenv("CHECKLIST_BASE_URL", "https://your-streamlit-cloud-app.streamlit.app"),
)

REQUIRED_COLUMNS = ["first_name", "last_name"]
SAVE_COLUMNS = [
    "first_name",
    "last_name",
    "citizen_ID",
    "student_ID",
    "email",
    "timestamp_BKK",
]

# ---------------- FUNCTIONS ----------------
def bkk_now() -> str:
    return datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")


def clean_text(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, dtype=str).fillna("")
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file, dtype=str).fillna("")
    else:
        raise ValueError("รองรับเฉพาะไฟล์ .csv, .xlsx, .xls")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def normalize_name_df(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"ไฟล์ต้องมี columns: first_name และ last_name แต่ขาด {missing}")

    out = df.copy()
    out["first_name"] = out["first_name"].apply(clean_text)
    out["last_name"] = out["last_name"].apply(clean_text)
    out["full_name"] = (out["first_name"] + " " + out["last_name"]).str.strip()
    return out


def make_token(student_id: str) -> str:
    return hmac.new(
        QR_SECRET.encode("utf-8"),
        str(student_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]


def make_qr_url(student_id: str) -> str:
    student_id = str(student_id).strip()
    token = make_token(student_id)
    return f"{CHECKLIST_BASE_URL}/?student_ID={student_id}&token={token}"


def make_qr_png(qr_text: str) -> BytesIO:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def load_registered_csv() -> pd.DataFrame:
    if REGISTERED_CSV.exists():
        df = pd.read_csv(REGISTERED_CSV, dtype=str).fillna("")
        for c in SAVE_COLUMNS:
            if c not in df.columns:
                df[c] = ""
        return df[SAVE_COLUMNS]
    return pd.DataFrame(columns=SAVE_COLUMNS)


def append_registered(row: dict) -> pd.DataFrame:
    old_df = load_registered_csv()
    new_df = pd.concat([old_df, pd.DataFrame([row])], ignore_index=True)
    new_df.to_csv(REGISTERED_CSV, index=False, encoding="utf-8-sig")
    return new_df


def print_html(first_name: str, last_name: str, student_id: str, qr_img: BytesIO, timestamp: str) -> str:
    full_name = f"{first_name} {last_name}".strip()
    qr_base64 = base64.b64encode(qr_img.getvalue()).decode("utf-8")
    warning_text = "กรุณาถือ QR Code นี้ติดตัวไปตลอดการตรวจ และแสดงต่อเจ้าหน้าที่ทุกสถานี"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        @page {{ size: A4 portrait; margin: 18mm; }}
        body {{
          font-family: Arial, 'Tahoma', sans-serif;
          text-align: center;
          color: #111;
        }}
        .page {{
          width: 100%;
          min-height: 260mm;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
        }}
        h1 {{ font-size: 30px; margin: 0 0 10px 0; }}
        h2 {{ font-size: 24px; margin: 8px 0; }}
        .sid {{ font-size: 28px; margin: 18px 0; }}
        img {{ width: 360px; height: 360px; margin: 16px 0; }}
        .warning {{
          border: 3px solid #111;
          padding: 14px 20px;
          margin-top: 22px;
          font-size: 24px;
          font-weight: bold;
          max-width: 700px;
        }}
        .small {{ font-size: 16px; margin-top: 18px; }}
        .print-button {{
          margin-top: 24px;
          padding: 12px 22px;
          font-size: 18px;
          cursor: pointer;
        }}
        @media print {{ .print-button {{ display: none; }} }}
      </style>
    </head>
    <body>
      <div class="page">
        <h1>Student Physical Exam 2026</h1>
        <h2>{full_name}</h2>
        <div class="sid"><b>Student ID:</b> {student_id}</div>
        <img src="data:image/png;base64,{qr_base64}" />
        <div class="warning">{warning_text}</div>
        <div class="small">Generated: {timestamp} BKK</div>
        <button class="print-button" onclick="window.print()">พิมพ์กระดาษ A4</button>
      </div>
    </body>
    </html>
    """


# ---------------- UI ----------------
st.title("🆔 ระบบลงทะเบียนนักศึกษาและพิมพ์ QR Code")
st.caption("รองรับ Streamlit Cloud · Upload CSV/Excel · Search ชื่อ · บันทึก registed_students.csv · พิมพ์ A4")

st.warning(
    "หมายเหตุสำคัญ: ถ้า deploy บน Streamlit Cloud ไฟล์ registed_students.csv ที่ save ใน local ของ app "
    "อาจไม่ถาวรและอาจหายเมื่อ app restart/redeploy ควรกดดาวน์โหลด CSV เก็บไว้ทุกครั้งหลังใช้งาน หรือใช้เครื่อง local สำหรับข้อมูล citizen ID จริง"
)

with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    st.write("CHECKLIST_BASE_URL")
    st.code(CHECKLIST_BASE_URL)
    st.write("ไฟล์บันทึก")
    st.code(str(REGISTERED_CSV.name))

uploaded = st.file_uploader(
    "อัปโหลดไฟล์รายชื่อที่มี columns: first_name, last_name",
    type=["csv", "xlsx", "xls"],
)

if uploaded is None:
    st.info("กรุณา upload CSV หรือ Excel ก่อน")
    st.stop()

try:
    df = normalize_name_df(read_uploaded_file(uploaded))
except Exception as e:
    st.error(str(e))
    st.stop()

st.success(f"โหลดข้อมูลสำเร็จ {len(df):,} records")
st.dataframe(df[REQUIRED_COLUMNS].head(200), use_container_width=True, hide_index=True)

registered_df = load_registered_csv()
with st.expander("ดูข้อมูลที่บันทึกแล้วใน registed_students.csv", expanded=False):
    st.dataframe(registered_df, use_container_width=True, hide_index=True)
    st.download_button(
        "ดาวน์โหลด registed_students.csv",
        data=registered_df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="registed_students.csv",
        mime="text/csv",
    )

st.divider()

keyword = st.text_input("🔎 Search first_name หรือ last_name", placeholder="เช่น Somchai หรือ Jai")

selected_first = ""
selected_last = ""
search_found = False

if keyword.strip():
    kw = keyword.strip().lower()
    result = df[
        df["first_name"].str.lower().str.contains(kw, na=False)
        | df["last_name"].str.lower().str.contains(kw, na=False)
        | df["full_name"].str.lower().str.contains(kw, na=False)
    ].copy()

    if result.empty:
        st.error("ไม่พบชื่อนักศึกษา สามารถกรอกข้อมูลใหม่เพื่อ append เข้า registed_students.csv ได้")
    else:
        search_found = True
        st.write("### ผลการค้นหา")
        result["label"] = result["full_name"]
        selected_label = st.selectbox("เลือกนักศึกษา", result["label"].tolist())
        selected_row = result[result["label"] == selected_label].iloc[0]
        selected_first = selected_row["first_name"]
        selected_last = selected_row["last_name"]
        st.info(f"เลือก: {selected_first} {selected_last}")

st.write("### กรอกข้อมูลลงทะเบียน")
col1, col2 = st.columns(2)
with col1:
    first_name_input = st.text_input("first_name", value=selected_first)
with col2:
    last_name_input = st.text_input("last_name", value=selected_last)

col3, col4 = st.columns(2)
with col3:
    citizen_id = st.text_input("citizen ID", type="password")
with col4:
    student_id = st.text_input("student ID")

email = st.text_input("email", placeholder="optional@example.com")
confirm = st.checkbox("ยืนยันว่าตรวจสอบ first_name, last_name, citizen ID, student ID และ email ถูกต้องแล้ว")

if st.button("💾 Save + สร้าง QR Code + เตรียมพิมพ์ A4", type="primary"):
    first_name_input = clean_text(first_name_input)
    last_name_input = clean_text(last_name_input)
    citizen_id = clean_text(citizen_id)
    student_id = clean_text(student_id)
    email = clean_text(email)

    if not first_name_input or not last_name_input:
        st.error("กรุณากรอก first_name และ last_name")
        st.stop()
    if not citizen_id:
        st.error("กรุณากรอก citizen ID")
        st.stop()
    if not student_id:
        st.error("กรุณากรอก student ID")
        st.stop()
    if not confirm:
        st.error("กรุณาติ๊กยืนยันก่อนบันทึก")
        st.stop()

    timestamp = bkk_now()
    save_row = {
        "first_name": first_name_input,
        "last_name": last_name_input,
        "citizen_ID": citizen_id,
        "student_ID": student_id,
        "email": email,
        "timestamp_BKK": timestamp,
    }
    new_registered_df = append_registered(save_row)

    qr_url = make_qr_url(student_id)
    qr_img = make_qr_png(qr_url)

    st.success(f"บันทึกลง {REGISTERED_CSV.name} แล้ว: {first_name_input} {last_name_input}")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("QR Code")
        st.image(qr_img, caption=f"Student ID: {student_id}")
        st.code(qr_url)
    with right:
        st.subheader("Download")
        st.download_button(
            "ดาวน์โหลด QR PNG",
            data=qr_img.getvalue(),
            file_name=f"QR_{student_id}.png",
            mime="image/png",
        )
        st.download_button(
            "ดาวน์โหลด registed_students.csv ล่าสุด",
            data=new_registered_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="registed_students.csv",
            mime="text/csv",
        )

    st.subheader("แบบพิมพ์ A4")
    components.html(
        print_html(first_name_input, last_name_input, student_id, qr_img, timestamp),
        height=900,
        scrolling=True,
    )

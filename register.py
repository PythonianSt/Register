import base64
from io import BytesIO, StringIO
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import qrcode
import requests
import streamlit as st


# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Student Registry QR",
    page_icon="🆔",
    layout="centered"
)


# =========================
# GITHUB CONFIG FROM STREAMLIT SECRETS
# =========================
# In Streamlit Cloud > App settings > Secrets, add:
# GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxx"
# GITHUB_REPO = "username/repo"
# GITHUB_BRANCH = "main"
# GITHUB_FILE = "created_csv2026.csv"

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
    GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
    GITHUB_FILE = st.secrets.get("GITHUB_FILE", "created_csv2026.csv")
except Exception:
    st.error(
        "ยังไม่ได้ตั้งค่า Streamlit secrets: GITHUB_TOKEN, GITHUB_REPO, "
        "GITHUB_BRANCH, GITHUB_FILE"
    )
    st.stop()

CSV_COLS = [
    "first_name",
    "last_name",
    "email",
    "citizen_ID",
    "student_ID",
    "timestamp_BKK",
]


# =========================
# BASIC FUNCTIONS
# =========================
def bkk_now() -> str:
    return datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")


def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()

    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file, dtype=str).fillna("")

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file, dtype=str).fillna("")

    st.error("รองรับเฉพาะ CSV หรือ Excel")
    st.stop()


def github_url() -> str:
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"


def github_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def github_get_file():
    """Return CSV text and SHA. If file does not exist, return None, None."""
    params = {"ref": GITHUB_BRANCH}
    r = requests.get(github_url(), headers=github_headers(), params=params, timeout=20)

    if r.status_code == 404:
        return None, None

    if r.status_code == 401:
        st.error("GitHub token ไม่ถูกต้อง หรือหมดอายุ")
        st.stop()

    if r.status_code == 403:
        st.error("GitHub token ไม่มี permission สำหรับ repo นี้")
        st.stop()

    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8-sig")
    sha = data["sha"]
    return content, sha


def load_created_csv() -> pd.DataFrame:
    content, _ = github_get_file()

    if content:
        df = pd.read_csv(StringIO(content), dtype=str).fillna("")
        for col in CSV_COLS:
            if col not in df.columns:
                df[col] = ""
        return df[CSV_COLS]

    return pd.DataFrame(columns=CSV_COLS)


def github_save_csv(df: pd.DataFrame):
    _, sha = github_get_file()

    df = df[CSV_COLS].copy()
    csv_text = df.to_csv(index=False, encoding="utf-8-sig")
    encoded = base64.b64encode(csv_text.encode("utf-8-sig")).decode("utf-8")

    payload = {
        "message": f"Update {GITHUB_FILE} {bkk_now()} BKK",
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }

    if sha:
        payload["sha"] = sha

    r = requests.put(
        github_url(),
        headers=github_headers(),
        json=payload,
        timeout=20,
    )

    if r.status_code == 404:
        st.error("ไม่พบ repo หรือ path ใน GitHub: ตรวจ GITHUB_REPO / GITHUB_FILE")
        st.stop()

    if r.status_code == 409:
        st.error("GitHub file ถูกแก้ไขพร้อมกัน กรุณากดบันทึกอีกครั้ง")
        st.stop()

    r.raise_for_status()


def append_created_csv(row: dict) -> pd.DataFrame:
    df_old = load_created_csv()

    existing_student_ids = df_old["student_ID"].astype(str).str.strip().values
    existing_citizen_ids = df_old["citizen_ID"].astype(str).str.strip().values
    existing_emails = df_old["email"].astype(str).str.lower().str.strip().values

    student_id = row["student_ID"].strip()
    citizen_id = row["citizen_ID"].strip()
    email = row["email"].lower().strip()

    if student_id in existing_student_ids:
        st.error("student_ID นี้ถูกลงทะเบียนแล้ว")
        st.stop()

    if citizen_id in existing_citizen_ids:
        st.error("citizen_ID นี้ถูกลงทะเบียนแล้ว")
        st.stop()

    if email in existing_emails:
        st.error("Email นี้ถูกลงทะเบียนแล้ว")
        st.stop()

    df_new = pd.concat([df_old, pd.DataFrame([row])], ignore_index=True)
    github_save_csv(df_new)
    return df_new


def make_qr_png(student_id: str) -> BytesIO:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(student_id)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def print_a4(first_name: str, last_name: str, student_id: str, qr_img: BytesIO, timestamp: str):
    """Print A4 QR sheet. Email is intentionally not shown on paper."""
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


# =========================
# UI
# =========================
st.title("🆔 Student Registry & QR Code: KU KPS Infirmary")
st.caption("Upload รายชื่อ → Search → ลงทะเบียน → สร้าง QR → บันทึก GitHub created_csv2026.csv")

st.info(
    "ไฟล์รายชื่อที่ Upload จะไม่ถูกแก้ไข โปรแกรมจะบันทึกข้อมูลลง GitHub CSV: "
    f"{GITHUB_FILE}"
)

uploaded_file = st.file_uploader(
    "Upload registered_students.csv หรือ Excel ที่มี first_name และ last_name",
    type=["csv", "xlsx", "xls"],
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
    df["display_name"] = df["first_name"].str.strip() + " " + df["last_name"].str.strip()

    st.success(f"โหลดรายชื่อแล้ว {len(df)} ราย")
    st.dataframe(df[["first_name", "last_name"]], use_container_width=True)

    st.divider()

    keyword = st.text_input("ค้นหา first_name หรือ last_name")

    selected_first = ""
    selected_last = ""

    if keyword:
        keyword = keyword.strip()
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
                result["display_name"].tolist(),
            )

            selected_row = result[result["display_name"] == selected_display].iloc[0]
            selected_first = selected_row["first_name"]
            selected_last = selected_row["last_name"]

        else:
            st.error("ไม่พบรายชื่อ สามารถกรอกใหม่เพื่อ append เข้า GitHub CSV ได้")
            selected_first = st.text_input("first_name ใหม่")
            selected_last = st.text_input("last_name ใหม่")

    st.divider()
    st.subheader("ลงทะเบียน")

    first_name = st.text_input("first_name", value=selected_first)
    last_name = st.text_input("last_name", value=selected_last)
    email = st.text_input("Email", placeholder="student@ku.th")
    citizen_id = st.text_input("citizen_ID", type="password")
    student_id = st.text_input("student_ID")

    confirm = st.checkbox("ยืนยันว่าข้อมูลถูกต้องแล้ว")

    if st.button("บันทึกลง GitHub และสร้าง QR Code"):
        first_name = first_name.strip()
        last_name = last_name.strip()
        email = email.strip()
        citizen_id = citizen_id.strip()
        student_id = student_id.strip()

        if not first_name or not last_name or not email or not citizen_id or not student_id:
            st.error("กรุณากรอกข้อมูลให้ครบ")
            st.stop()

        if "@" not in email or "." not in email:
            st.error("Email ไม่ถูกต้อง")
            st.stop()

        if not confirm:
            st.error("กรุณาติ๊กยืนยันก่อน")
            st.stop()

        timestamp = bkk_now()

        row = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "citizen_ID": citizen_id,
            "student_ID": student_id,
            "timestamp_BKK": timestamp,
        }

        created_df = append_created_csv(row)

        st.success(f"บันทึกลง GitHub: {GITHUB_FILE} แล้ว")

        qr_img = make_qr_png(student_id)

        st.subheader("QR Code")
        st.image(qr_img, width=320)

        print_a4(
            first_name=first_name,
            last_name=last_name,
            student_id=student_id,
            qr_img=qr_img,
            timestamp=timestamp,
        )

        st.download_button(
            "ดาวน์โหลด QR Code PNG",
            data=qr_img,
            file_name=f"QR_{student_id}.png",
            mime="image/png",
        )

        st.download_button(
            "ดาวน์โหลด created_csv2026.csv",
            data=created_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="created_csv2026.csv",
            mime="text/csv",
        )

st.divider()

st.subheader("ดู created_csv2026.csv จาก GitHub ปัจจุบัน")

try:
    created_now = load_created_csv()
    st.dataframe(created_now, use_container_width=True)

    if not created_now.empty:
        st.download_button(
            "ดาวน์โหลด created_csv2026.csv ล่าสุด",
            data=created_now.to_csv(index=False, encoding="utf-8-sig"),
            file_name="created_csv2026.csv",
            mime="text/csv",
        )
except Exception as e:
    st.warning(f"ยังอ่าน GitHub CSV ไม่สำเร็จ: {e}")


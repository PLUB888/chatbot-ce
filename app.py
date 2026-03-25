import streamlit as st
import google.generativeai as genai
import pandas as pd
import PyPDF2
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import json
import uuid

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Chatbot CE", page_icon="✨", layout="wide")

# --- 2. ฐานข้อมูล ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local_chat.db")
engine = create_engine(DATABASE_URL)
Base = declarative_base()

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True)
    session_id = Column(String(50))
    role = Column(String(20))
    content = Column(Text)

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# --- 3. ตั้งค่า Gemini API ---
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 4. ฟังก์ชันจัดการประวัติ ---
def load_history(session_id):
    return db.query(ChatHistory).filter(ChatHistory.session_id == session_id).order_by(ChatHistory.id).all()

def save_message(session_id, role, content):
    msg = ChatHistory(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.commit()

def get_all_sessions():
    sessions = db.query(ChatHistory.session_id).distinct().all()
    session_list = []
    for s in sessions:
        sid = s[0]
        first_msg = db.query(ChatHistory).filter(ChatHistory.session_id == sid, ChatHistory.role == 'user').order_by(ChatHistory.id).first()
        title = first_msg.content[:25] + "..." if first_msg and len(first_msg.content) > 25 else (first_msg.content if first_msg else "แชทว่างเปล่า")
        session_list.append({"id": sid, "title": title})
    return session_list

def delete_session(session_id):
    db.query(ChatHistory).filter(ChatHistory.session_id == session_id).delete()
    db.commit()

# --- 5. จัดการ Session ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": h.role, "content": h.content} for h in load_history(st.session_state.session_id)]
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""
if "pdf_name" not in st.session_state:
    st.session_state.pdf_name = None

# --- 6. UI ด้านข้าง (Sidebar) ---
lang = st.sidebar.radio("🌐 Language", ["ไทย", "English"], horizontal=True)
ui = {
    "ไทย": {
        "title": "✨ Chatbot CE", 
        "upload": "📂 อัปโหลดไฟล์ PDF", 
        "chat_placeholder": "พิมพ์ข้อความ...", 
        "new_chat": "➕ สร้างแชทใหม่", 
        "history": "ประวัติการแชท",
        "tools": "เครื่องมือเสริม",
        "graph_mode": "เปิดโหมดสร้างกราฟ",
        "graph_hint": "โหมดนี้ทำงานอยู่: พิมพ์แค่ข้อมูลบอทจะวาดกราฟให้ทันที",
        "theme": "🎨 เลือกธีมสี"
    },
    "English": {
        "title": "✨ Chatbot CE", 
        "upload": "📂 Upload PDF File", 
        "chat_placeholder": "Type message...", 
        "new_chat": "➕ New Chat", 
        "history": "Chat History",
        "tools": "Additional Tools",
        "graph_mode": "Enable Graph Mode",
        "graph_hint": "Mode active: Type data like 'Jan=10' to draw a chart.",
        "theme": "🎨 Choose Theme"
    }
}

# --- ระบบเลือกธีมสี (Theme Selector) ---
st.sidebar.markdown(f"### {ui[lang]['theme']}")
# เอาอิโมจิออกจากชื่อธีมตรงนี้
theme_choice = st.sidebar.selectbox("", ["Sunset Glow", "Ocean Blue", "Neon Cyber"], label_visibility="collapsed")

# ตั้งค่าสีพื้นหลังและตัวอักษรตามธีมที่เลือก (แก้ชื่อ Key ให้ตรงกัน)
theme_configs = {
    "Sunset Glow": {
        "grad": "linear-gradient(90deg, #FF6B6B 0%, #FF8E53 100%)", 
        "graph": "#FF6B6B", 
        "bg": "#FFF7F0", 
        "sidebar": "#FFEBE0", 
        "text": "#2C1810"
    },
    "Ocean Blue": {
        "grad": "linear-gradient(90deg, #36D1DC 0%, #5B86E5 100%)", 
        "graph": "#5B86E5", 
        "bg": "#F0F8FF", 
        "sidebar": "#E0F0FF", 
        "text": "#0B1B3D"
    },
    "Neon Cyber": {
        "grad": "linear-gradient(90deg, #fc466b 0%, #3f5efb 100%)", 
        "graph": "#fc466b", 
        "bg": "#0B0514", 
        "sidebar": "#150A21", 
        "text": "#E8E0F8"
    }
}
t = theme_configs[theme_choice]

# ฝัง CSS เพื่อเปลี่ยนสีทั้งหน้าจอ
st.markdown(f"""
<style>
    /* เปลี่ยนสีพื้นหลังหน้าจอหลัก */
    [data-testid="stAppViewContainer"] {{
        background-color: {t['bg']};
    }}
    /* เปลี่ยนสีพื้นหลัง Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {t['sidebar']} !important;
        border-right: 1px solid {t['graph']}40;
    }}
    /* เปลี่ยนสีตัวอักษรหลักๆ ให้เข้ากับธีม */
    h1, h2, h3, h4, p, span, label, .stMarkdown, .stText {{
        color: {t['text']} !important;
    }}
    /* ตกแต่งปุ่ม */
    .stButton>button {{
        background: {t['grad']};
        color: white !important;
        border-radius: 10px;
        border: none;
        font-weight: bold;
        transition: all 0.3s ease;
        width: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    .stButton>button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
    }}
    /* ตกแต่งกล่องพับประวัติ */
    .streamlit-expanderHeader {{
        color: {t['text']} !important;
        background-color: transparent !important;
    }}
</style>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

if st.sidebar.button(ui[lang]["new_chat"]):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")

# โซนเครื่องมือเสริม (Tools) 
st.sidebar.markdown(f"### {ui[lang]['tools']}")
graph_mode = st.sidebar.toggle(ui[lang]['graph_mode'])
if graph_mode:
    st.sidebar.caption(f"_{ui[lang]['graph_hint']}_")

st.sidebar.markdown("---")

# โซนประวัติการแชท
with st.sidebar.expander(ui[lang]['history'], expanded=False):
    past_sessions = get_all_sessions()
    
    if past_sessions:
        with st.container(height=300, border=False):
            for sess in reversed(past_sessions):
                col1, col2 = st.columns([4, 1])
                if col1.button(sess["title"], key=f"btn_{sess['id']}"):
                    st.session_state.session_id = sess['id']
                    st.session_state.messages = [{"role": h.role, "content": h.content} for h in load_history(sess['id'])]
                    st.rerun()
                if col2.button("🗑️", key=f"del_{sess['id']}"):
                    delete_session(sess['id'])
                    if st.session_state.session_id == sess['id']:
                        st.session_state.session_id = str(uuid.uuid4())
                        st.session_state.messages = []
                    st.rerun()
    else:
        st.write("ยังไม่มีประวัติการแชท" if lang == "ไทย" else "No chat history yet")

st.sidebar.markdown("---")

# โซนอัปโหลด PDF
st.sidebar.markdown(f"### {ui[lang]['upload']}")
uploaded_file = st.sidebar.file_uploader("", type=["pdf"])

if uploaded_file is not None:
    if st.session_state.pdf_name != uploaded_file.name:
        with st.spinner("กำลังจดจำเนื้อหา PDF..."):
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages])
            st.session_state.pdf_text = text
            st.session_state.pdf_name = uploaded_file.name
        st.sidebar.success(f"✅ อ่านไฟล์ '{uploaded_file.name}' เรียบร้อย! พิมพ์ถามคำถามหรือสั่งสรุปในแชทได้เลย")
    else:
        st.sidebar.success(f"✅ ไฟล์ '{uploaded_file.name}' พร้อมใช้งานในแชทแล้ว")
else:
    st.session_state.pdf_text = ""
    st.session_state.pdf_name = None

# --- 7. พื้นที่แชทหลัก (Main Page) ---
st.title(ui[lang]["title"])

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "```json_chart" in msg["content"]:
            try:
                json_str = msg["content"].split("```json_chart")[1].split("```")[0]
                data = json.loads(json_str)
                df = pd.DataFrame({'Values': data['values']}, index=data['labels'])
                st.bar_chart(df, color=t['graph'])
            except:
                pass

if user_input := st.chat_input(ui[lang]["chat_placeholder"]):
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_message(st.session_state.session_id, "user", user_input)

    pdf_context = ""
    if st.session_state.pdf_text != "":
        pdf_context = f"\n\n[CONTEXT FROM UPLOADED PDF]:\n{st.session_state.pdf_text[:30000]}\n[END OF CONTEXT]\nIf the user asks questions or requests a summary, answer based heavily on the PDF context above."

    if graph_mode:
        system_instruction = f"""You are Chatbot CE. The user has enabled GRAPH MODE. Output in {lang}.
        You MUST explain the data briefly and YOU MUST include a JSON block exactly like this:
        ```json_chart
        {{"labels": ["A", "B"], "values": [10, 20]}}
        ```
        Extract data from the user to replace A, B and 10, 20. Do not use any other block for charts."""
    else:
        system_instruction = f"""You are Chatbot CE, a helpful assistant. Output in {lang}. 
        Do NOT output any ```json_chart``` blocks unless explicitly asked."""
    
    full_prompt = system_instruction + pdf_context + "\nUser: " + user_input
    
    with st.spinner("กำลังพิมพ์..."):
        response = model.generate_content(full_prompt)
        bot_reply = response.text

    with st.chat_message("assistant"):
        st.markdown(bot_reply)
        
        if "```json_chart" in bot_reply:
            try:
                json_str = bot_reply.split("```json_chart")[1].split("```")[0]
                data = json.loads(json_str)
                df = pd.DataFrame({'Values': data['values']}, index=data['labels'])
                st.bar_chart(df, color=t['graph']) 
            except Exception as e:
                st.error("⚠️ ข้อมูลไม่ครบถ้วน ลองพิมพ์ตัวเลขให้ชัดเจนอีกครั้ง")

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    save_message(st.session_state.session_id, "assistant", bot_reply)
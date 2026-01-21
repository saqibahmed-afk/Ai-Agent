import streamlit as st
import requests
import PyPDF2
from docx import Document
from PIL import Image
import pytesseract
from dotenv import load_dotenv
import os

# ---------------------------
# 1. Page Configuration
# ---------------------------
st.set_page_config(
    page_title="Parhona AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------
# 2. Custom CSS (The "Unique" Look)
# ---------------------------
def inject_custom_css():
    st.markdown("""
    <style>
        /* Import Google Font */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Poppins', sans-serif;
        }

        /* Dark Gradient Background */
        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: rgba(30, 41, 59, 0.9);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Custom Headers */
        h1 {
            background: linear-gradient(to right, #6366f1, #a855f7, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700 !important;
        }

        /* Chat Input Styling */
        .stChatInput {
            border-radius: 20px;
        }
        
        /* Custom Button */
        div.stButton > button {
            background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        div.stButton > button:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ---------------------------
# 3. Setup & Logic
# ---------------------------
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

# Tesseract Setup
_tesseract_env = os.getenv("TESSERACT_CMD")
_windows_default = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

if _tesseract_env and os.path.exists(_tesseract_env):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_env
elif os.name == "nt" and os.path.exists(_windows_default):
    pytesseract.pytesseract.tesseract_cmd = _windows_default

# Document Processor Class
class DocumentProcessor:
    def process_document(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        try:
            if ext == ".txt":
                return open(filepath, "r", encoding="utf-8").read()
            elif ext == ".pdf":
                text = ""
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for p in reader.pages:
                        if p.extract_text():
                            text += p.extract_text() + "\n"
                return text
            elif ext in [".docx", ".doc"]:
                doc = Document(filepath)
                return "\n".join(p.text for p in doc.paragraphs)
            elif ext in [".png", ".jpg", ".jpeg"]:
                img = Image.open(filepath)
                return pytesseract.image_to_string(img)
            else:
                return "[Unsupported file]"
        except Exception as e:
            return f"[Error: {e}]"

doc_processor = DocumentProcessor()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_contents" not in st.session_state:
    st.session_state.document_contents = {}

# ---------------------------
# 4. API Function (Now with Context!)
# ---------------------------
def get_groq_response(user_input):
    if not api_key:
        return "⚠️ Error: API Key is missing. Please check your .env file."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Combine all document text into the system context
    doc_context = ""
    if st.session_state.document_contents:
        doc_context = "\n\nCONTEXT FROM UPLOADED FILES:\n"
        for name, content in st.session_state.document_contents.items():
            doc_context += f"--- START {name} ---\n{content[:5000]}\n--- END {name} ---\n" 
            # Note: Limiting to 5000 chars per file to avoid token limits for now

    system_msg = (
        "You are 'Parhona', an advanced AI tutor. "
        "Use the provided Document Context to answer questions if relevant. "
        "Be concise, friendly, and use formatting (bolding, lists) to make learning easy."
        f"{doc_context}"
    )

    messages = [{"role": "system", "content": system_msg}]
    messages.extend(st.session_state.messages)
    messages.append({"role": "user", "content": user_input})

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 1200
    }

    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Connection Error: {str(e)}"

# ---------------------------
# 5. Sidebar UI
# ---------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=60)
    st.markdown("### ⚙️ Control Panel")
    
    # File Uploader with a unique key
    uploaded = st.file_uploader("📂 Upload Study Materials", type=["txt", "pdf", "docx", "png", "jpg"])
    
    if uploaded:
        path = f"temp/{uploaded.name}"
        os.makedirs("temp", exist_ok=True)
        with open(path, "wb") as f:
            f.write(uploaded.read())
        
        # Process and store
        with st.spinner(f"Reading {uploaded.name}..."):
            text = doc_processor.process_document(path)
            st.session_state.document_contents[uploaded.name] = text
        st.toast(f"✅ {uploaded.name} Loaded!", icon="🧠")

    # Knowledge Base Status
    if st.session_state.document_contents:
        with st.expander("📚 Active Knowledge Base", expanded=True):
            for fname in st.session_state.document_contents:
                st.caption(f"• {fname}")
    else:
        st.info("Upload a document to chat with it.")

    st.markdown("---")
    if st.button("🗑️ Reset Memory"):
        st.session_state.messages = []
        st.session_state.document_contents = {}
        st.rerun()

# ---------------------------
# 6. Main Chat Interface
# ---------------------------
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🎓 Parhona</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8; margin-top: 0;'>Your AI Study Companion</p>", unsafe_allow_html=True)

# Container for chat history
chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        st.markdown("""
        <div style='text-align: center; padding: 40px; color: #64748b;'>
            <h3>👋 Hello! I'm ready to help.</h3>
            <p>Upload a PDF or ask me a question to get started.</p>
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        # Custom avatar handling
        avatar = "🤖" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])

# Input at the bottom
user_input = st.chat_input("Ask a question about your documents...")

if user_input:
    # 1. Add User Message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.write(user_input)

    # 2. Generate AI Response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Analyzing documents..."):
            reply = get_groq_response(user_input)
            st.write(reply)
    
    # 3. Add AI Message to History
    st.session_state.messages.append({"role": "assistant", "content": reply})
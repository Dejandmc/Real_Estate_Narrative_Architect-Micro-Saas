import streamlit as st
import os
from main import run_v11_pipeline 
from supabase import create_client

# 1. Конфигурација на страницата
st.set_page_config(page_title="Luxury Architect v11", layout="wide")

st.markdown("""
    <style>
        input[type="password"]::-ms-reveal,
        input[type="password"]::-ms-clear { display: none !important; }
        input[type="password"]::-webkit-credentials-auto-fill-button { visibility: hidden; display: none !important; }
    </style>
""", unsafe_allow_html=True)

# 2. Безбедно вчитување на Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3. Помошни функции
def check_listings_limit(user_id):
    response = supabase.table("subscriptions").select("listings_count").eq("user_id", user_id).execute()
    if not response.data:
        supabase.table("subscriptions").insert({
            "user_id": user_id, 
            "listings_count": 0, 
            "status": "active", 
            "plan_type": "pro"
        }).execute()
        return 0
    return response.data[0]["listings_count"]

def increment_listings(user_id):
    current = check_listings_limit(user_id)
    supabase.table("subscriptions").update({"listings_count": current + 1}).eq("user_id", user_id).execute()

def get_user_limit_and_plan(user_id):
    response = supabase.table("subscriptions").select("listings_count, plan_type").eq("user_id", user_id).execute()
    if not response.data:
        return 0, 50 
    data = response.data[0]
    listings_count = data.get("listings_count", 0)
    plan_type = data.get("plan_type", "pro")
    limit = 100 if plan_type == "agency" else 50
    return listings_count, limit

def get_file_path(uploaded_file):
    if uploaded_file is not None:
        save_path = f"temp_{st.session_state['username']}_{uploaded_file.name}"
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return save_path
    return None

# Иницијализација на сесија
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

LANGUAGES = [
    # Основни јазици
    "English", "Deutsch", "Français", "Italiano", "Dutch", 
    
    # Јужна Европа и Јужна Америка
    "Español (España)", "Español (Latam)", 
    "Português (Portugal)", "Português (Brasil)", 
    
    # Словенски јазици (Источни)
    "Русский", "Українська", "Беларуская", 
    
    # Словенски јазици (Западни)
    "Polski", "Čeština", "Slovenčina", 
    
    # Словенски јазици (Балкан)
    "Macedonian", "Srpski", "Hrvatski", "Bosanski", "Crnogorski", 
    "Slovenščina", "Български", 
    
    # Nordic & Baltic
    "Lietuvių", "Latviešu", "Eesti", "Suomi", "Svenska", "Norsk", "Dansk", "Íslenska (Icelandic)", 
    
    # Останати Европски
    "Magyar", "Română", "Shqip", "Ελληνικά", "Türkçe", 
    
    # Азиски јазици (Јужна Азија)
    "हिन्दी (Hindi)", "اردو (Urdu)", "বাংলা (Bangla)", "தமிழ் (Tamil)",
    
    # Азиски јазици (Источна и Југоисточна Азија)
    "中文 (Chinese - Simplified)", "繁體中文 (Chinese - Traditional)", "日本語 (Japanese)", "한국어 (Korean)", 
    "Bahasa Indonesia", "Tiếng Việt", "ไทย (Thai)", "Filipino (Tagalog)", 
    "ភាសាខ្មែរ (Khmer)", "ລາວ (Lao)", "Монгол (Mongolian)", 
    
    # Централноазиски јазици
    "Қазақ (Kazakh)", "O'zbek (Uzbek)", "Türkmen (Turkmen)", "Тоҷикӣ (Tajik)", "Кыргыз (Kyrgyz)", 
    
    # Блискоисточни јазици
    "العربية (Arabic)", "فارسی (Persian)", "עברית (Hebrew)", 
    
    # Африкански јазици
    "Afrikaans", "Kiswahili (Swahili)", "isiZulu (Zulu)", "አማርኛ (Amharic)", "Hausa"
]

def login_screen():
    st.title("🔐 Access to Luxury Real Estate Narrative Architect")
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    with tab1:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email_input")
        password = st.text_input("Password", type="password", key="login_pass_input")
        if st.button("Log In"):
            try:
                supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["logged_in"] = True
                st.session_state["username"] = email
                st.rerun()
            except:
                st.error("Invalid email or password.")
    with tab2:
        st.subheader("Create Account")
        email_signup = st.text_input("Email", key="signup_email_input")
        password_signup = st.text_input("Password", type="password", key="signup_pass_input")
        password_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm_pass_input")
        if st.button("Sign Up"):
            if password_signup != password_confirm:
                st.error("Passwords do not match!")
            else:
                try:
                    supabase.auth.sign_up({"email": email_signup, "password": password_signup})
                    st.success("Account created! You can now log in.")
                except Exception as e:
                    st.error(f"Error: {e}")

if not st.session_state["logged_in"]:
    login_screen()
else:
    # --- СЕКОЈА ЛИНИЈА ПОДОЛУ Е ДЕЛ ОД ELSE БЛОКОТ ---
    st.title("🏛️ Luxury Real Estate Narrative Architect")
    st.sidebar.success(f"Logged in as: **{st.session_state['username']}**")
    
    selected_lang = st.sidebar.selectbox("Select target language:", LANGUAGES)
    location = st.text_input("Location:", placeholder="e.g. Ohrid")
    sqm = st.text_input("Square footage:", value="100sqm") 
    custom_rules = st.text_area("Custom brand rules: (optional)", value="Write a luxury, professional listing.")

    st.subheader("Media and Specifications")
    col1, col2 = st.columns(2)
    with col1:
        uploaded_doc = st.file_uploader("Upload PDF/TXT: (optional)", type=['pdf', 'txt'])
    with col2:
        uploaded_img = st.file_uploader("Upload image (JPG/PNG): (optional)", type=['jpg', 'jpeg', 'png'])

    if st.button("🚀 Generate Listing"):
        current_count, allowed_limit = get_user_limit_and_plan(st.session_state["username"])
        if current_count >= allowed_limit:
            st.error(f"You have reached your limit of {allowed_limit} listings!")
        elif not location:
            st.warning("Please enter a location.")
        else:
            doc_path = get_file_path(uploaded_doc)
            img_path = get_file_path(uploaded_img)
            try:
                with st.spinner('The architect is working...'):
                    with st.status("🏛️ Sovereign Architect: Orchestrating...", expanded=True) as status:
                        def update_status(msg): status.write(msg)
                        result = run_v11_pipeline(location=location, sqm=sqm, doc_path=doc_path, img_path=img_path, custom_rules=custom_rules, callback=update_status, target_language=selected_lang)
                        status.update(label="✅ Completed!", state="complete", expanded=False)
                if result:
                    increment_listings(st.session_state["username"])
                    st.success("Success!")
                    st.text_area("Narrative:", value=result, height=300)
            except Exception as e:
                st.error(f"System error: {e}")
            finally:
                for p in [doc_path, img_path]:
                    if p and os.path.exists(p): os.remove(p)

    if st.sidebar.button("Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()

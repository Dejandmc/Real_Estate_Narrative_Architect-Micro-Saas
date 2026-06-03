import streamlit as st
import os
from main import run_v11_pipeline 
from supabase import create_client

# Конфигурација на Supabase
SUPABASE_URL = "https://dzbniqleamqxdizpflsj.supabase.co"
SUPABASE_KEY = "sb_publishable__TnIwjyfOnyEaTWJdNSXDw_zPRLV04a" 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Конфигурација на страницата
st.set_page_config(page_title="Luxury Architect v11", layout="wide")

# Додај ги овие функции
def check_listings_limit(user_id):
    response = supabase.table("subscriptions").select("listings_count").eq("user_id", user_id).execute()
    
    # Ако корисникот не постои, креирај го сега
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
    st.title("🔐 Access to Luxury Real Estate")
    
    # ПРВО дефинирај ги табовите
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
            except Exception as e:
                st.error("Invalid email or password.")

    with tab2:
        st.subheader("Create Account")
        email_signup = st.text_input("Email", key="signup_email_input")
        password_signup = st.text_input("Password", type="password", key="signup_pass_input")
        
        if st.button("Sign Up"):
            try:
                supabase.auth.sign_up({"email": email_signup, "password": password_signup})
                st.success("Account created! You can now log in.")
            except Exception as e:
                st.error(f"Error: {e}")

if not st.session_state["logged_in"]:
    login_screen()
else:
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

    def get_file_path(uploaded_file):
        if uploaded_file is not None:
            # Користиме уникатно име за да избегнеме судири при паралелни повици
            save_path = f"temp_{st.session_state['username']}_{uploaded_file.name}"
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            return save_path
        return None

# Овој дел треба да биде вовлечен под 'else:' од твојот логин систем
    # Овој дел е внатре во 'else:' блокот (најавениот дел)
    if st.button("🚀 Generate Listing"):
        # 1. ПРОВЕРКА НА ЛИМИТ
        current_count = check_listings_limit(st.session_state["username"])
        
        if current_count >= 10:
            st.error("Го достигна лимитот од 10 огласи за овој месец!")
        elif not location:
            st.warning("Please enter a location.")
        else:
            # 2. ПОДГОТОВКА НА ФАЈЛОВИТЕ
            doc_path = get_file_path(uploaded_doc)
            img_path = get_file_path(uploaded_img)
            
            # 3. ГЕНЕРИРАЊЕ
            try:
                with st.status("🏛️ Sovereign Architect: Orchestrating...", expanded=True) as status:
                    def update_status(message):
                        status.write(message) 
                    
                    result = run_v11_pipeline(
                        location=location,
                        sqm=sqm,
                        doc_path=doc_path,
                        img_path=img_path,
                        custom_rules=custom_rules,
                        callback=update_status,
                        target_language=selected_lang
                    )
                    status.update(label="✅ Architecture completed!", state="complete", expanded=False)
                
                # 4. АЖУРИРАЊЕ И ПРИКАЗ
                if result and isinstance(result, str):
                    increment_listings(st.session_state["username"])
                    st.success("Listing generated successfully and your account has been updated.")
                    st.markdown(f"### Result ({selected_lang}):")
                    st.text_area("Narrative:", value=result, height=300)
                    
                    st.download_button(
                        label="📥 Download result",
                        data=result,
                        file_name=f"Luxury_Listing_{location.replace(' ', '_')}.txt",
                        mime="text/plain"
                    )
                else:
                    st.error("The system returned an empty result. Check logs.")
            
            except Exception as e:
                st.error(f"A system error occurred: {e}")
            
            finally:
                # 5. БЕЗБЕДНО ЧИСТЕЊЕ
                for path in [doc_path, img_path]:
                    if path and os.path.exists(path):
                        os.remove(path)
    
    # ЛОГ АУТ КОПЧЕ (исто така вовлечено под 'else')
    if st.sidebar.button("Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()
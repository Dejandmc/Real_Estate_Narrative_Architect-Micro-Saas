import streamlit as st
import os
from main import run_v11_pipeline 
from supabase import create_client

def is_disposable_email(email):
    blocked_domains = [
        "mailinator.com", "10minutemail.com", "guerrillamail.com", "temp-mail.org",
        "yopmail.com", "trashmail.com", "dispostable.com", "sharklasers.com",
        "getnada.com", "throwawaymail.com", "maildrop.cc", "tempmail.net",
        "tempmail.com", "fakeinbox.com", "mintemail.com"
    ]
    try:
        domain = email.split('@')[-1].lower()
        return domain in blocked_domains
    except:
        return False

# 1. Конфигурација на страницата
st.set_page_config(page_title="Luxury Real Estate Narrative Architect Micro Saas", layout="wide")

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
            "plan_type": "basic"  # <-- Смени го ова од "pro" во "basic"
        }).execute()
        return 0
    return response.data[0]["listings_count"]

def increment_listings(user_id):
    current = check_listings_limit(user_id)
    supabase.table("subscriptions").update({"listings_count": current + 1}).eq("user_id", user_id).execute()

def get_user_limit_and_plan(user_id):
    response = supabase.table("subscriptions").select("listings_count, plan_type").eq("user_id", user_id).execute()
    
    # Ако корисникот не е пронајден, го ставаме на 'basic' план со 10 обиди
    if not response.data:
        return 0, 10 
    
    data = response.data[0]
    listings_count = data.get("listings_count", 0)
    # Читање на планот од базата (ако е празно, ставаме 'basic')
    plan_type = data.get("plan_type", "basic") 
    
    # Дефинирање на лимити според плановите
    limits = {
        "basic": 3,
        "pro": 50,
        "agency": 200
    }
    
    # Враќаме лимит според типот на план, со fallback на 10 ако има грешка
    limit = limits.get(plan_type, 10)
    return listings_count, limit

def get_user_plan_name(user_id):
    response = supabase.table("subscriptions").select("plan_type").eq("user_id", user_id).execute()
    if response.data:
        return response.data[0].get("plan_type", "basic")
    return "basic"

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
    "Macedonian", "Srpski (Latinica)", "Srpski (Ćirilica)", "Hrvatski", "Bosanski", "Crnogorski", 
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
                # Обиди се да се најавиш
                auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                
                # Дополнителна проверка: дали навистина има корисник?
                if auth_response.user:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = auth_response.user.email
                    st.rerun()
                else:
                    st.error("Authentication failed. Please try again.")
            except Exception as e:
                # Тука додаваме прецизна порака за грешка
                st.error("Invalid email or password.")
    with tab2:
            st.subheader("Create Account")
            email_signup = st.text_input("Email", key="signup_email_input")
            password_signup = st.text_input("Password", type="password", key="signup_pass_input")
            password_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm_pass_input")
            
            if st.button("Sign Up"):
                if password_signup != password_confirm:
                    st.error("Passwords do not match!")
                # Ова е новата проверка што ја додаваме:
                elif is_disposable_email(email_signup):
                    st.error("Ве молиме користете професионална или приватна е-маил адреса (на пр. Gmail, Outlook).")
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
    
    # СТАТИСТИКАТА СЕГА Е ТУКА - СЕКОГАШ ВИДЛИВА
    current_count, allowed_limit = get_user_limit_and_plan(st.session_state["username"])
    
    # Дополнително: земи го и планот (потребно е да ја прилагодиш функцијата или да го извлечеш од базата)
    # За почеток, еве како да го прикажеш динамично:
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Your plan and limits")
    
    # Прикажување на тековниот план (ако веќе го добиваш од get_user_limit_and_plan)
    # Ако функцијата враќа само (listings, limit), можеш да направиш уште еден повик или да ја апдејтираш функцијата
    st.sidebar.write(f"Plan: **{get_user_plan_name(st.session_state['username'])}**") # Можеш да креираш ваква функција
    
    st.sidebar.write(f"Usage: **{current_count} / {allowed_limit}**")
    
    # Заштита од делене со нула (ако лимитот е 0)
    progress_val = current_count / allowed_limit if allowed_limit > 0 else 0
    st.sidebar.progress(min(progress_val, 1.0))
    
    st.sidebar.markdown("---")

    # --- Админ Панел ---
    if st.session_state["username"] == "dejan.dmc.freelancer@gmail.com": 
        with st.sidebar.expander("🛠️ Admin Panel"):
            admin_email = st.text_input("Upgrade user email:")
            admin_plan = st.selectbox("Select new plan:", ["basic", "pro", "agency"])
            
            if st.button("Apply Upgrade"):
                try:
                    # Ажурирање на планот во базата
                    supabase.table("subscriptions").update({
                        "plan_type": admin_plan,
                        "listings_count": 0
                    }).eq("user_id", admin_email).execute()
                    st.success(f"User {admin_email} upgraded to {admin_plan}!")
                except Exception as e:
                    st.error(f"Error: {e}")
    # -------------------
    
    selected_lang = st.sidebar.selectbox("Select target language:", LANGUAGES)
    location = st.text_input("Location:", placeholder="e.g. Ohrid")
    sqm = st.text_input("Square footage:", value="100sqm") 
    target_price = st.text_input("Target Price:", placeholder="e.g. 350.000€") # <-- ДОДАЈ ГО ОВА
    custom_rules = st.text_area("Custom brand rules: (optional)", value="Write a luxury, professional listing.")

    st.subheader("Media and Specifications")
    col1, col2 = st.columns(2)
    with col1:
        uploaded_doc = st.file_uploader("Upload PDF/TXT: (optional)", type=['pdf', 'txt'])
    with col2:
        uploaded_img = st.file_uploader("Upload image (JPG/PNG): (optional)", type=['jpg', 'jpeg', 'png'])

    # СЕКОГАШ ИМАШ САМО ЕДЕН БЛОК ЗА ГЕНЕРИРАЊЕ
    if st.button("🚀 Generate Listing"):
        # 1. Проверка на лимитот (само еднаш)
        current_count, allowed_limit = get_user_limit_and_plan(st.session_state["username"])
        
        if current_count >= allowed_limit:
            st.error(f"You have reached your limit of {allowed_limit} listings! Upgrade your plan to continue.")
            
            # Приказ на плановите за надградба
            st.markdown("### 🚀 Unlock more listings with a premium plan:")
            col1, col2 = st.columns(2)
            
            with col1:
                st.info("**Standard Edition**\n50 listings/mo")
                st.link_button("Upgrade to Standard", "https://dmcfreelance.gumroad.com/l/Luxury_Real_Estate_Narrative_Architect_Micro_Saas_Standard_Edition")
            
            with col2:
                st.warning("**Agency Edition**\n200 listings/mo")
                st.link_button("Upgrade to Agency", "https://dmcfreelance.gumroad.com/l/Luxury_Real_Estate_Narrative_Architect_Micro_Saas_Agency_Edition")

            st.markdown("---")
            st.markdown("Have questions? Contact me at: **dejan.dmc.freelancer@gmail.com**")
            
            st.stop()
            
        elif not location:
            st.warning("Please enter a location.")
        else:
            # 2. Иницирање на процесот
            doc_path = get_file_path(uploaded_doc)
            img_path = get_file_path(uploaded_img)
            
            try:
                with st.spinner('The architect is working...'):
                    # Извршување на pipeline-от
                    result = run_v11_pipeline(
                        location=location, sqm=sqm, doc_path=doc_path, 
                        img_path=img_path, custom_rules=custom_rules, 
                        target_price=target_price, callback=lambda msg: st.write(msg), 
                        target_language=selected_lang
                    )
                
                if result:
                    increment_listings(st.session_state["username"])
                    st.success("Success!")
                    st.text_area("Narrative:", value=result, height=300)
                    
                    st.download_button(
                        label="📥 Download Listing",
                        data=result,
                        file_name=f"Luxury_Listing_{location.replace(' ', '_')}.txt",
                        mime="text/plain"
                    )
                    # ОТСТРАНИ ГО st.rerun() ОВДЕ - НЕ Е ПОТРЕБНО
            except Exception as e:
                st.error(f"System error: {e}")
            finally:
                # Ова е добро, но додади мала проверка
                for p in [doc_path, img_path]:
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except:
                            pass

    # И на крај, логично, оди копчето за одјавување
    if st.sidebar.button("Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()

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
        "basic": 10,
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
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email_input")
            password = st.text_input("Password", type="password", key="login_pass_input")
            submit = st.form_submit_button("Log In")
            
            if submit:
                try:
                    # Обид за најава
                    auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    
                    if auth_response.user:
                        st.balloons() # Визуелна потврда за успех
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = auth_response.user.email
                        st.rerun()
                except Exception:
                    st.error("Invalid email or password. Please try again.")

    with tab2:
        st.subheader("Create Account")
        with st.form("signup_form"):
            email_signup = st.text_input("Email", key="signup_email_input")
            password_signup = st.text_input("Password", type="password", key="signup_pass_input")
            password_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm_pass_input")
            signup_submit = st.form_submit_button("Sign Up")
            
            if signup_submit:
                if password_signup != password_confirm:
                    st.error("Passwords do not match!")
                elif is_disposable_email(email_signup):
                    st.error("Ве молиме користете професионална или приватна е-маил адреса (на пр. Gmail, Outlook).")
                else:
                    try:
                        # Регистрација на корисник
                        supabase.auth.sign_up({"email": email_signup, "password": password_signup})
                        st.success("Account created! Please check your email to confirm if required.")
                    except Exception as e:
                        st.error(f"Error during sign up: {e}")
                        
if not st.session_state["logged_in"]:
    login_screen()
else:
    # --- СЕ ШТО Е ПОД ELSE Е ВОВЛЕЧЕНО И СЕ КРИЕ КОГА НЕ СИ НАЈАВЕН ---
    st.title("🏛️ Luxury Real Estate Narrative Architect")
    st.sidebar.success(f"Logged in as: **{st.session_state['username']}**")
    
    # Статистика
    current_count, allowed_limit = get_user_limit_and_plan(st.session_state["username"])
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Your plan and limits")
    st.sidebar.write(f"Plan: **{get_user_plan_name(st.session_state['username'])}**")
    st.sidebar.write(f"Usage: **{current_count} / {allowed_limit}**")
    progress_val = current_count / allowed_limit if allowed_limit > 0 else 0
    st.sidebar.progress(min(progress_val, 1.0))
    st.sidebar.markdown("---")
        
    # --- Админ Панел ---
    if st.session_state["username"] == "dejan.dmc.freelancer@gmail.com": 
        with st.sidebar.expander("🛠️ Admin Panel"):
            admin_email = st.text_input("Upgrade user email:", key="admin_email_input")
            admin_plan = st.selectbox("Select new plan:", ["basic", "pro", "agency"], key="admin_plan_select")
            
            # Додаден е уникатен клуч овде
            if st.button("Apply Upgrade", key="admin_apply_upgrade_btn"):
                try:
                    supabase.table("subscriptions").update({
                        "plan_type": admin_plan,
                        "listings_count": 0  
                    }).eq("user_id", admin_email).execute()
                    
                    st.success(f"User {admin_email} upgraded to {admin_plan}!")
                    st.rerun() 
                except Exception as e:
                    st.error(f"Error: {e}")
    # -------------------
    
    # Влезни полиња во Sidebar-от (секогаш достапни за корисникот)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Property Details")
    
    selected_lang = st.sidebar.selectbox(
        "Select target language:", 
        LANGUAGES, 
        key="lang_select",
        help="Choose the language for the final AI-generated narrative."
    )
    
    location = st.text_input(
        "Location:", 
        placeholder="e.g. Ohrid", 
        key="location_input"
    )
    
    sqm = st.text_input(
        "Square footage:", 
        value="100sqm", 
        key="sqm_input"
    ) 
    
    target_price = st.text_input(
        "Target Price:", 
        placeholder="e.g. 350.000€", 
        key="price_input"
    )
    
    custom_rules = st.text_area(
        "Custom brand rules: (optional)", 
        value="Write a luxury, professional listing.", 
        key="rules_input",
        help="Specify tone or specific brand requirements (e.g., 'Use bullet points', 'Emphasize lake views')."
    )

    # Главен дел на страницата
    st.subheader("Media and Specifications")
    col1, col2 = st.columns(2)
    
    with col1:
        uploaded_doc = st.file_uploader(
            "Upload PDF/TXT: (optional)", 
            type=['pdf', 'txt'], 
            key="doc_uploader",
            help="Upload property documentation, floor plans, or extra specs."
        )
        
    with col2:
        uploaded_img = st.file_uploader(
            "Upload image (JPG/PNG): (optional)", 
            type=['jpg', 'jpeg', 'png'], 
            key="img_uploader",
            help="Upload a high-quality property photo for visual analysis."
        )

    # 1. БЛОКОТ ЗА ГЕНЕРИРАЊЕ - ВОВЛЕЧЕН ВНАТРЕ ВО ELSE (ЛОГИЧКИ ПРАВИЛНО)
    if st.button("🚀 Generate Listing", key="gen_listing_btn"):
        current_count, allowed_limit = get_user_limit_and_plan(st.session_state["username"])
        
        # ПРОВЕРКА НА ЛИМИТИТЕ
        if current_count >= allowed_limit:
            st.error(f"⚠️ You have reached your limit of {allowed_limit} listings.")
            st.subheader("🚀 Upgrade Your Plan to Continue")
            
            # Дефинирање на CSS со потемна боја при hover
            green_button_style = """
                <style>
                .stLinkButton > a {
                    background-color: #28a745 !important;
                    color: white !important;
                    font-weight: bold !important;
                    transition: background-color 0.3s ease !important;
                    border: none !important;
                }
                .stLinkButton > a:hover {
                    background-color: #1e7e34 !important; /* Ова е потемната нијанса */
                    color: white !important;
                }
                </style>
            """
            st.markdown(green_button_style, unsafe_allow_html=True)

            # Колони за плановите
            col_std, col_agy = st.columns(2)
            
            with col_std:
                with st.container(border=True):
                    st.markdown("### Standard Plan")
                    st.write("✅ 50 listings")
                    st.write("💰 $49")
                    st.link_button("Pay Standard", "https://dmcfreelance.gumroad.com/l/Luxury_Real_Estate_Narrative_Architect_Micro_Saas_Standard_Edition", use_container_width=True)
                
            with col_agy:
                with st.container(border=True):
                    st.markdown("### Agency Plan")
                    st.write("✅ 200 listings")
                    st.write("💰 $99")
                    st.link_button("Pay Agency", "https://dmcfreelance.gumroad.com/l/Luxury_Real_Estate_Narrative_Architect_Micro_Saas_Agency_Edition", use_container_width=True)
            
            st.info("Once you have completed the payment, please contact us for manual plan activation.")
            st.stop()
                
        elif not location:
            st.warning("Please enter a location.")
        else:
            # Логика за генерирање
            log_container = st.container()
            with st.spinner("Generating your luxury listing..."):
                try:
                    def update_log(msg):
                        log_container.info(msg)

                    result = run_v11_pipeline(
                        location=location,
                        sqm=sqm,
                        target_price=target_price,
                        custom_rules=custom_rules,
                        doc_path=get_file_path(uploaded_doc),
                        img_path=get_file_path(uploaded_img),
                        target_language=selected_lang,
                        callback=update_log
                    )
                    
                    if result:
                        st.markdown("### ✨ Generated Listing:")
                        # Го земаме текстот од резултатот
                        generated_text = result.get("final_draft", result)
                        
                        # Го прикажуваме на екранот
                        st.write(generated_text)
                        
                        # КОПЧЕ ЗА ПРЕЗЕМАЊЕ
                        st.download_button(
                            label="📥 Download Listing as TXT",
                            data=generated_text,
                            file_name="Luxury_Property_Listing.txt",
                            mime="text/plain"
                        )
                        
                        increment_listings(st.session_state["username"])
                        st.success("Listing generated successfully!")
                    else:
                        st.error("Pipeline finished but returned no content.")
                except Exception as e:
                    st.error(f"Грешка во pipeline: {e}")

    # 2. LOGOUT КОПЧЕТО - ВОВЛЕЧЕНО ПОД ELSE
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", key="logout_btn_sidebar"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.rerun()

# 3. FOOTER - НАДВОР ОД ELSE, СЕКОГАШ ВИДЛИВ
# Овој дел е на исто ниво како и главниот 'if/else' блок, затоа се гледа секогаш.
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: grey; font-size: 0.8em;'>"
    "Crafted with precision by <b>Dejan Stojanoski</b> © 2026"
    "</div>", 
    unsafe_allow_html=True
)

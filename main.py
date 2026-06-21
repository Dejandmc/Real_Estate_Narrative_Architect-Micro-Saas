import sys
import os
import time
import datetime
import warnings  # ОВА МОРА ДА Е ОВДЕ!
import streamlit as st

from typing import TypedDict, Any
from dotenv import load_dotenv
from pypdf import PdfReader
from PIL import Image
from google import genai
from google.genai.errors import APIError
from langgraph.graph import StateGraph, END
from tavily import TavilyClient
# SUPABASE импорт - ако го немаш во requirements.txt, ова ќе паѓа!
from supabase import create_client 

# --- 1. SETUP & CONFIGURATION ---
# Сега 'warnings' е дефиниран, па ова нема да предизвика NameError
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

load_dotenv()

# Иницијализација
api_key = os.getenv("GOOGLE_API_KEY") # Директно од env за тестирање
tavily_key = os.getenv("TAVILY_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY не е поставен!")

client = genai.Client(api_key=api_key)
tavily = TavilyClient(api_key=tavily_key)

# Ултра-сигурен автономен ланец на модели (Maximum Resilience Fallback Chain)
# Исчистени префикси за 100% софтверска стабилност со новиот Client
FALLBACK_ENGINES = [
    "gemini-3.1-flash-lite",          # Твојот докажан шампион кој веќе помина успешно
    "gemini-2.5-flash-lite",          # Стабилна прва линија од претходната генерација
    "gemini-3.5-flash",               # Најнова генерација (2026) - брз, паметен и со свежа квота (ама квотата брзо се троши)
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-3.1-flash-image-preview", # Специјален визуелен бекап доколку претходните јават 429 во Vision Node
    "gemini-2.5-pro",                 # Тешка артилерија за длабока ревизија кај Critic Node
    "gemini-3.1-pro-preview"          # Краен логички штит со највисока интелигенција на пазарот
]
COST_PER_1K_TOKENS = 0.0001 

# 1. На врвот на фајлот, каде што ги имаш импортите:
from typing import TypedDict, Any  # <-- Додади Any овде

class AgentState(TypedDict):
    # Влезни податоци
    pdf_data: str
    vision_description: str
    research_data: str
    persona_profile: str      # <--- НОВО ПОЛЕ
    
    # Работни верзии
    draft: str
    critic_feedback: str
    iteration_count: int
    
    # Метрики и системски податоци
    total_tokens: int
    estimated_cost: float
    engine_index: int
    
    # Излезни артефакти
    voice_script: str
    generated_narrative: str
    translated_version: str
    
    # Конфигурација
    target_language: str
    master_rules: str
    lessons_learned: str
    callback: Any
    target_price: str

def track_usage(response, state: AgentState):
    """Детално LLMOps следење на потрошените токени и буџет во реално време"""
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage = response.usage_metadata
        state["total_tokens"] += usage.total_token_count
        state["estimated_cost"] += (usage.total_token_count / 1000) * COST_PER_1K_TOKENS

def load_context_file(filepath: str) -> str:
    """Стабилно вчитување на куќните правила и еволуциските датотеки"""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# --- НОВ КОД (Подобрен) ---
def execute_with_resilient_fallback(state: AgentState, prompt_contents):
    # Користиме локален индекс кој се базира на состојбата
    current_idx = state.get("engine_index", 0)
    
    while current_idx < len(FALLBACK_ENGINES):
        current_model = FALLBACK_ENGINES[current_idx]
        model_success = False
        
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=prompt_contents
                )
                model_success = True
                # Ажурирај го глобалниот state пред враќање доколку е успешен обидот
                state["engine_index"] = current_idx
                return response, state
                
            except APIError as e:
                # Ако наидеме на ограничувања на квотата или серверски грешки, почекај и обиди се повторно
                if e.code in [429, 500, 503]:
                    time.sleep((attempt + 1) * 5)
                    continue 
                raise e

        if not model_success:
            # Ако моделот не успеа по 3 обиди, премини на следниот модел од листата
            current_idx += 1  
            state["engine_index"] = current_idx 
            print(f"🔄 [Failover] Switching to model: {current_model}...")
            time.sleep(15) 
            continue 

    # Ако сите модели во листата се исцрпени, прекини ја работата
    raise RuntimeError("🚨 The agent has exhausted all 9 models!")

# --- 2. VISION NODE (Визуелна интелигенција - Адаптирана за јазик) ---
def vision_node(state: AgentState):
    if state.get("vision_description") and len(state["vision_description"]) > 10:
        return state

    cb = state.get("callback") 
    lang = state.get("target_language", "English")
    current_model = FALLBACK_ENGINES[state["engine_index"]]
    
    status_msg = f"📸 VISION AGENT: Analyzing property image in {lang} with {current_model}..."
    print(status_msg)
    if cb: cb(status_msg)
    
    # ПРОВЕРКА: Користиме стандардизирано име 'property_image.jpg'
    # кое мора да биде подготвено претходно во run_v11_pipeline
    target_img_path = "property_image.jpg"
    
    try:
        if not os.path.exists(target_img_path):
            raise FileNotFoundError(f"Image not found at {target_img_path}")
        
        # Отворање на сликата
        img = Image.open(target_img_path)
        
    except Exception as e:
        print(f"⚠️ Vision Error: {e}")
        state["vision_description"] = "No luxury image context available."
        return state

    # Промпт кој го зема предвид јазикот
    payload = [
        f"Describe this luxury interior in {lang}. Focus on high-end materials, textures, and atmospheres to guide elite copywriters.",
        img
    ]
    
    # Извршување
    response, state = execute_with_resilient_fallback(state, payload)
    
    state["vision_description"] = response.text
    track_usage(response, state)
    
    # Важно: img.close() помага при ослободување на меморијата
    img.close()
    
    time.sleep(3) 
    return state

# --- 3. RESEARCH NODE (Динамично пазарно разузнавање) ---
def research_node(state: AgentState):
    cb = state.get("callback")
    lang = state.get("target_language", "English")
    
    location = state.get("pdf_data", "Ohrid")
    query = f"luxury real estate market trends {location} 2026 UNESCO protection investment"
    
    status_msg = f"🔍 RESEARCH AGENT: Searching market data for: {query}..."
    print(status_msg)
    if cb: cb(status_msg)
    
    try:
        # ОВДЕ БЕШЕ ПРОБЛЕМОТ - ФАЛЕШЕ try БЛОКОТ
        search_result = tavily.search(query=query, max_results=3, search_depth="advanced")
        results = search_result.get('results', [])
        
        if not results:
            raise ValueError("Tavily returned empty results.")
            
        context = "\n\n".join([f"Source: {res['url']}\nContent: {res['content']}" for res in results])
        state["research_data"] = context
        if cb: cb("✅ RESEARCH AGENT: Data successfully integrated.")
        
    except Exception as e:
        error_msg = f"⚠️ Research Warning: {e}. Applying localized 'Safe-Mode' market insights."
        print(error_msg)
        if cb: cb(error_msg)
        
        if lang.lower() == "macedonian":
            state["research_data"] = "Market context: High demand for luxury properties in Ohrid under UNESCO protection. Investors are looking for authentic materials and lake views."
        else:
            state["research_data"] = "Market Context: High demand for UNESCO-protected luxury properties in Ohrid. Investors prioritize authentic materials and lake views."
            
    return state

# --- 4. PERSONA REFINER NODE (Елитен Наратив - Директен на целниот јазик) ---
def persona_node(state: AgentState):
    cb = state.get("callback")
    if cb: cb("🎯 PERSONA AGENT: Profiling the ideal investor...")
    
    prompt = f"""
    Based on the property specs: {state['pdf_data']}
    And market intel: {state['research_data']}
    
    Identify the specific psychological profile of the elite buyer for this property.
    Focus on: Motivations, lifestyle values, and emotional triggers for luxury real estate.
    Output a concise persona profile to guide the copywriter.
    """
    
    response, state = execute_with_resilient_fallback(state, prompt)
    state["persona_profile"] = response.text
    return state

def writer_node(state: AgentState):
    # 1. Извлекување на јазикот
    lang = state.get("target_language")
    if not lang:
        raise ValueError("🚨 CRITICAL ERROR: target_language is not defined in state!")

    cb = state.get("callback")
    attempt = state["iteration_count"] + 1
    
    status_msg = f"✍️ WRITER AGENT: Crafting elite narrative for target profile in {lang} (Attempt #{attempt})..."
    print(status_msg)
    if cb: cb(status_msg)
    
    # 3. Ажуриран промпт со вклучена 'TARGET PERSONA'
    prompt = f"""
    You are a Senior Luxury Real Estate Copywriter. 
    TASK: Write an uncompromised promotional narrative EXCLUSIVELY in {lang}.
    
    ### TARGET AUDIENCE PROFILE: {state.get('persona_profile', 'High-net-worth individual seeking exclusivity.')}
    ### TARGET PRICE POINT: {state.get("target_price", "N/A")}
    
    ### INSTRUCTION ON PRICE & PERSONA: 
    Explain the "intangible value" of this property specifically for the identified target audience. 
    Connect the features (materials, location, UNESCO status) to the emotional triggers, 
    aspirations, and lifestyle values of this specific buyer. Why does this property 
    perfectly align with their status and vision for the future?
    
    ### RAW SPECIFICATIONS: {state["pdf_data"]}
    ### VISION: {state["vision_description"]}
    ### MARKET INTEL: {state["research_data"]}
    ### MASTER RULES: {state["master_rules"]}
    
    STRICT CONSTRAINTS:
    1. Output language MUST be exactly {lang}.
    2. Do not use English words or phrases.
    3. No exclamation marks.
    4. Use luxury-tier tone and "curated aesthetics" vocabulary appropriate for {lang}.
    """
    
    response, state = execute_with_resilient_fallback(state, prompt)
    
    state["draft"] = response.text
    state["generated_narrative"] = response.text 
    
    track_usage(response, state)
    time.sleep(3)
    return state

# --- 5. TRANSLATION NODE (ФИНАЛНА ВЕРЗИЈА - ПОЛИРАЊЕ) ---
def translation_node(state: AgentState):
    # 1. Земи го јазикот без fallback - ако го нема, системот треба да крене грешка
    lang = state.get("target_language")
    if not lang:
        raise ValueError("🚨 CRITICAL ERROR: target_language is not defined for TRANSLATION NODE!")

    cb = state.get("callback")
    
    # 2. Неутрална логика за "Refinement" наместо "Translation"
    if cb: cb(f"🌍 TRANSLATION AGENT: Final polishing of narrative in {lang}...")

    prompt = f"""
    You are a Senior Luxury Real Estate Editor.
    Task: Review and refine the provided narrative.
    
    STRICT CONSTRAINTS:
    1. Output Language: MUST be exclusively {lang}.
    2. Forbidden: DO NOT output any text in a different language.
    3. Tone: Ensure absolute prestige, elegance, and high-end luxury vocabulary.
    4. Accuracy: Maintain all technical specs (sqm, locations, materials).
    5. No exclamation marks.
    
    ### SOURCE TEXT:
    {state.get("draft")}
    """
    
    try:
        response, state = execute_with_resilient_fallback(state, prompt)
        state["translated_version"] = response.text
        # Ажурирај го draft-от за да ја има финалната, полирана верзија
        state["draft"] = response.text 
        track_usage(response, state)
    except Exception as e:
        if cb: cb(f"⚠️ Translation/Refinement Warning: {e}")
        # Ако падне, барем врати го она што веќе го напишал Writer агентот
        state["translated_version"] = state.get("draft", "Content unavailable.")
        
    return state
    
# --- 6. VOICE-OVER NODE (Кинематографско сценарио - Локализирано) ---
def voice_over_node(state: AgentState):
    cb = state.get("callback")
    lang = state.get("target_language", "English")
    
    status_msg = f"🎙️ VOICE-OVER AGENT: Creating cinematic script in {lang}..."
    print(status_msg)
    if cb: cb(status_msg)
    
    # Користи го 'draft' (кое сега е веќе полирано на целниот јазик)
    base_narrative = state.get("draft", "")
    
    prompt = f"""
    Create a highly professional voice-over script in {lang} for an architectural teaser video based on this narrative.
    
    STRICT CONSTRAINTS:
    1. Language: MUST be exclusively {lang}.
    2. Include ambient cues (e.g., [Sound of wind over the lake], [Soft cello enter], [Pause]).
    3. Tone: Calm, slow, and commanding.
    4. Forbidden: No exclamation marks.

    ### BASE NARRATIVE:
    {base_narrative}
    """
    
    response, state = execute_with_resilient_fallback(state, prompt)
    state["voice_script"] = response.text
    track_usage(response, state)
    
    time.sleep(3)
    return state

# --- 7. CRITIC NODE (Ревизор кој разбира што проверува) ---
def critic_node(state: AgentState):
    cb = state.get("callback")
    # Користи го јазикот од state, ако го нема - fail-fast (превенирај грешки)
    lang = state.get("target_language")
    if not lang:
        raise ValueError("🚨 CRITICAL ERROR: target_language is not defined for CRITIC NODE!")
    
    if cb: cb(f"⚖️ CRITIC AGENT: Performing audit in {lang}...")
    
    prompt = f"""
    You are a Senior Luxury Real Estate Editor.
    Audit the text below against the master rules provided.
    
    ### MASTER LAWS: {state["master_rules"]}
    ### GENERATED TEXT: {state["draft"]}
    
    CRITICAL AUDIT TASKS:
    1. Language Check: Is the text EXCLUSIVELY in {lang}? (Strictly reject if mixed with English or other languages).
    2. Tone Check: Does it maintain a luxury-tier tone and "curated aesthetics" vocabulary?
    3. Rule Check: Any exclamation marks present? (Strictly forbidden).
    
    If the text meets all standards, reply with: "APPROVED".
    If there are errors, provide a professional critique starting with "REWRITE: [detailed reasons]".
    """
    
    response, state = execute_with_resilient_fallback(state, prompt)
    state["critic_feedback"] = response.text.strip()
    state["iteration_count"] += 1
    
    return state

# --- 8. CONDITIONAL EDGES (Интелигентно рутирање) ---
def should_continue(state: AgentState):
    cb = state.get("callback")
    feedback = state.get("critic_feedback", "").upper()
    
    # 1. Ако има REWRITE и сме под 3 итерации
    if "REWRITE" in feedback and state["iteration_count"] < 3:
        status_msg = f"🔄 SELF-CORRECTION LOOP (Attempt {state['iteration_count']}/3): Returning to Writer agent..."
        print(status_msg)
        if cb: cb(status_msg)
        return "rewrite"
        
    # 2. Ако е APPROVED или сме ја достигнале границата од 3 итерации (Safety First!)
    else:
        if "REWRITE" in feedback:
            status_msg = "⚠️ MAX ITERATIONS REACHED: Forced finalization of current quality."
        else:
            status_msg = "✅ FINALIZATION: All criteria met. Moving to completion."
            
        print(status_msg)
        if cb: cb(status_msg)
        return "end"

# --- 9. STATEGRAPH WORKFLOW BUILDER (Со вметнат Persona Refiner) ---
workflow = StateGraph(AgentState)

# Додавање на јазли
workflow.add_node("vision", vision_node)
workflow.add_node("research", research_node)
workflow.add_node("persona", persona_node)  # <--- НОВ ЈАЗОЛ
workflow.add_node("writer", writer_node)
workflow.add_node("translation", translation_node) 
workflow.add_node("voice_over", voice_over_node)
workflow.add_node("critic", critic_node)

# Дефинирање на редослед
workflow.set_entry_point("vision")
workflow.add_edge("vision", "research")
workflow.add_edge("research", "persona")   # <--- Редослед: Research -> Persona
workflow.add_edge("persona", "writer")     # <--- Редослед: Persona -> Writer

workflow.add_edge("writer", "translation") 
workflow.add_edge("translation", "voice_over")
workflow.add_edge("voice_over", "critic")

# Условна логика (останува иста)
workflow.add_conditional_edges(
    "critic",
    should_continue,
    {"rewrite": "writer", "end": END}
)

app = workflow.compile()

# --- 10. SYSTEM EXECUTION (Оптимизиран и дебагиран) ---
def run_v11_pipeline(location, sqm, target_price, target_language, custom_rules, doc_path, img_path, callback=None): 
    # 0. ЧИСТЕЊЕ
    try:
        if os.path.exists("FINAL_OUTPUT"):
            for file in os.listdir("FINAL_OUTPUT"):
                file_path = os.path.join("FINAL_OUTPUT", file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    except Exception as e:
        print(f"⚠️ Warning: Could not clean FINAL_OUTPUT folder: {e}")

    # 1. ПРАВИЛА
    rules_text = custom_rules if custom_rules else load_context_file("brand_identity_rules.txt")
    
    if callback:
        callback("🏛️ Sovereign Architect: Pipeline initialization...")
    
    # 2. ЕКСТРАКЦИЈА НА ПОДАТОЦИ
    pdf_text = ""
    if doc_path:
        if os.path.exists(doc_path):
            if doc_path.lower().endswith('.pdf'):
                try:
                    reader = PdfReader(doc_path)
                    pdf_text = "".join([page.extract_text() for page in reader.pages if page.extract_text()])
                    if not pdf_text:
                        print("⚠️ Warning: PDF appears empty.")
                except Exception as e:
                    print(f"⚠️ PDF Reading Error: {e}")
            else:
                pdf_text = load_context_file(doc_path)
        else:
            print(f"⚠️ Warning: Document path {doc_path} not found.")

    # 3. ИНИЦИЈАЛИЗАЦИЈА НА СОСТОЈБА
    initial_state: AgentState = {
        "pdf_data": pdf_text + f" Location: {location}, Square footage: {sqm}м².",
        "target_price": target_price,
        "vision_description": "",
        "research_data": "",
        "persona_profile": "",      # <--- ДОДАДИ ГО ОВА!
        "draft": "",
        "critic_feedback": "",
        "iteration_count": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
        "voice_script": "",
        "generated_narrative": "",
        "translated_version": "",
        "master_rules": rules_text,
        "lessons_learned": load_context_file("lessons_learned.txt"),
        "engine_index": 0,
        "callback": callback,
        "target_language": target_language
    }
    
    # 4. ИЗВРШУВАЊЕ СО ОБИД ЗА ФАТАЊЕ НА ГРЕШКИ
    try:
        # Додадено: Лог за дебагирање пред старт
        print(f"🚀 Starting pipeline for {location}...")
        final_output = app.invoke(initial_state)
        
        if not final_output:
            raise Exception("Workflow completed but returned no output.")
            
        return {
            "final_draft": final_output.get("draft", "Content unavailable."),
            "voice_script": final_output.get("voice_script", "Content unavailable."),
            "total_tokens": final_output.get("total_tokens", 0),
            "estimated_cost": final_output.get("estimated_cost", 0.0)
        }
        
    except Exception as e:
        print(f"🚨 CRITICAL Workflow failure: {str(e)}")
        # Овде враќаме None, но сега знаеме дека грешката е веќе испечатена во терминалот
        return None
    

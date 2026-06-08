import streamlit as st
import requests
import hashlib
import pandas as pd
import plotly.express as px
from requests.exceptions import Timeout, ConnectionError

# 1. Page Configuration (Wide Layout)
st.set_page_config(
    page_title="Retail Intelligence Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Advanced Enterprise CSS Injection
st.markdown("""
    <style>
    /* Hide Default Menu */
    [data-testid="stSidebarNav"] { display: none !important; }
    
    /* Clean, bright background */
    .stApp { background-color: #f4f7f6; font-family: 'Inter', -apple-system, sans-serif; }
    
    /* Deep dark sidebar */
    section[data-testid="stSidebar"] { background-color: #0f172a !important; border-right: 1px solid #1e293b; }
    section[data-testid="stSidebar"] * { color: #f8fafc !important; }
    
    /* Ensure Chat Text is always dark and readable */
    div[data-testid="stChatMessageContent"] * { color: #0f172a !important; }
    
    /* Sleek Metric/Info Cards */
    .info-card {
        background: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 15px;
    }
    
    /* Vibrant Gradient Action Button */
    div.stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        color: white !important; border: none !important; border-radius: 8px !important;
        padding: 12px 24px !important; font-weight: 600 !important; letter-spacing: 0.5px !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important; width: 100%;
    }
    div.stButton > button:hover { transform: translateY(-2px) !important; box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4) !important; }
    
    /* Elegant Title Banner */
    .header-banner {
        background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
        padding: 24px 30px; border-radius: 12px; color: white; margin-bottom: 25px; 
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-left: 4px solid #3b82f6;
    }
    .header-banner h1 { margin: 0; font-size: 28px; font-weight: 800; color: white; letter-spacing: -0.5px; }
    .header-banner p { margin: 5px 0 0 0; color: #94a3b8; font-size: 15px; }
    </style>
""", unsafe_allow_html=True)

BACKEND_URL = "http://127.0.0.1:8000"

# 3. Session State Management
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "active_product_id" not in st.session_state:
    st.session_state["active_product_id"] = None
if "active_product_title" not in st.session_state:
    st.session_state["active_product_title"] = ""
if "chunks_stored" not in st.session_state:
    st.session_state["chunks_stored"] = 0

def generate_automated_id(url: str) -> int:
    clean_url = url.strip().lower()
    hash_object = hashlib.sha256(clean_url.encode('utf-8'))
    return int(hash_object.hexdigest(), 16) % (10**6)

def run_ingestion(target_url: str):
    with st.spinner(f"Extracting {target_url[:40]}..."):
        try:
            automated_id = generate_automated_id(target_url)
            payload = {"url": target_url, "product_id": automated_id}
            response = requests.post(f"{BACKEND_URL}/ingest", json=payload, timeout=180)
            
            if response.status_code == 200:
                data = response.json()
                st.session_state["active_product_id"] = automated_id
                st.session_state["active_product_title"] = data.get("product_title", "Active Session")
                st.session_state["chunks_stored"] = data.get("chunks_inserted", 0)
                st.success("Vector indexing complete!")
            else:
                st.error(f"Ingestion Error: {response.text}")
        except Timeout:
            st.error("Gateway Timeout: Pipeline took longer than 180s.")
        except ConnectionError:
            st.error("Backend Disconnected. Is Uvicorn running?")

# 4. Sidebar Control Panel
with st.sidebar:
    st.markdown("### ⚡ Data Ingestion Engine")
    st.markdown("<p style='color:#94a3b8; font-size:14px;'>Supply a target URL to map unstructured web data into PostgreSQL vector space.</p>", unsafe_allow_html=True)
    
    url_input = st.text_input("Target URL:", placeholder="e.g., https://amazon.in/...")
    if st.button("🚀 Initialize Scraper Pipeline", use_container_width=True):
        if url_input: run_ingestion(url_input)
        else: st.error("Please enter a URL first.")
            
    st.markdown("<br><p style='color: #64748b; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;'>Quick Start Demos</p>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💻 Laptop"): run_ingestion("https://www.flipkart.com/apple-macbook-air-m1-8-gb-256-gb-mac-os-big-sur-mgn63hn-a/p/itmfc87c8560d2ca")
    with col2:
        if st.button("👟 Sneakers"): run_ingestion("https://www.flipkart.com/nike-revolution-6-running-shoes-men/p/itm5a3b2cb2088f3")

    st.write("---")
    if st.button("🗑️ Purge Chat Memory", use_container_width=True):
        st.session_state["chat_history"] = []
        st.rerun()

# 5. Main Dashboard Layout
col_main, col_side = st.columns([6, 4], gap="large")

with col_main:
    if st.session_state["active_product_title"]:
        st.markdown(f"""
            <div class="header-banner">
                <h1>{st.session_state['active_product_title']}</h1>
                <p>Hybrid RAG pipeline actively monitoring context for this product.</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div class="header-banner">
                <h1>Global Retail Intelligence</h1>
                <p>Awaiting target URL input from the control panel...</p>
            </div>
        """, unsafe_allow_html=True)

    tab_chat, tab_logs = st.tabs(["💬 Intelligence Chat", "⚙️ System Logs"])
    
    with tab_chat:
        for message in st.session_state["chat_history"]:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        if user_query := st.chat_input("Run a query (e.g., 'What are the specs?' or 'Lowest price?')..."):
            if not st.session_state["active_product_id"]:
                st.warning("Action required: Please ingest a product URL first.")
            else:
                with st.chat_message("user"): st.write(user_query)
                st.session_state["chat_history"].append({"role": "user", "content": user_query})
                
                with st.spinner("Routing via NLP Engine..."):
                    try:
                        query_payload = {"question": user_query, "product_id": st.session_state["active_product_id"]}
                        response = requests.post(f"{BACKEND_URL}/query", json=query_payload, timeout=60)
                        
                        if response.status_code == 200:
                            result = response.json()
                            answer_text = result.get("response", "Processing error.")
                            with st.chat_message("assistant"): st.write(answer_text)
                            st.session_state["chat_history"].append({"role": "assistant", "content": answer_text})
                        else: st.error("RAG Engine Error.")
                    except ConnectionError: st.error("Connection Refused.")

    with tab_logs:
        st.markdown("<h3 style='color: #0f172a;'>Runtime Analytics</h3>", unsafe_allow_html=True)
        st.info("System logs and execution routes will appear here to keep the main chat clean.")

# 6. Right Side Panel (Context & Metrics)
with col_side:
    st.markdown("<h3 style='color: #0f172a; margin-bottom: 15px;'>📊 Market Intelligence</h3>", unsafe_allow_html=True)
    
    if st.session_state["active_product_id"]:
        col_id, col_chunk = st.columns(2)
        with col_id:
            st.markdown(f"""
                <div class="info-card">
                    <p style="color: #64748b; margin: 0; font-size: 11px; font-weight: 700; text-transform: uppercase;">Unique Target ID</p>
                    <h4 style="margin: 5px 0 0 0; color: #0f172a;">#{st.session_state["active_product_id"]}</h4>
                </div>
            """, unsafe_allow_html=True)
        with col_chunk:
            st.markdown(f"""
                <div class="info-card">
                    <p style="color: #64748b; margin: 0; font-size: 11px; font-weight: 700; text-transform: uppercase;">Vector Chunks</p>
                    <h4 style="margin: 5px 0 0 0; color: #2563eb;">{st.session_state["chunks_stored"]} Blocks</h4>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<h4 style='color: #0f172a; margin-top: 20px;'>🔍 Competitor Pricing Matrix</h4>", unsafe_allow_html=True)
        try:
            comp_url = f"{BACKEND_URL}/query/compare/{st.session_state['active_product_id']}"
            comp_response = requests.get(comp_url, params={"current_title": st.session_state["active_product_title"]}, timeout=10)
            
            if comp_response.status_code == 200:
                comp_data = comp_response.json()
                df_comp = pd.DataFrame(comp_data.get("comparisons", []))
                category = comp_data.get("category", "General")
                
                st.markdown(f"<p style='color: #64748b; font-size: 13px;'>Detected Category: <b>{category}</b></p>", unsafe_allow_html=True)
                
                # 1. FIXED Plotly Bar Chart (Visible Text)
                fig_bar = px.bar(
                    df_comp, x='Price', y='Platform', orientation='h', color='Price',
                    color_continuous_scale='Blues_r', text_auto='.0f'
                )
                fig_bar.update_layout(
                    font=dict(color="#475569"), # Forces text to be dark gray
                    margin=dict(l=0, r=0, t=10, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    coloraxis_showscale=False,
                    xaxis=dict(title="Price (₹)", showgrid=True, gridcolor="#e2e8f0"),
                    yaxis={'categoryorder':'total descending', 'title': ''}
                )
                st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
                
                # 2. BEAUTIFUL Custom HTML Table (Replaces the dark st.dataframe)
                table_html = """
                <table style='width:100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); font-size: 14px;'>
                    <tr style='background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;'>
                        <th style='padding: 12px; text-align: left; color: #475569;'>Platform</th>
                        <th style='padding: 12px; text-align: right; color: #475569;'>Price</th>
                        <th style='padding: 12px; text-align: right; color: #475569;'>Delivery</th>
                    </tr>
                """
                for _, row in df_comp.iterrows():
                    table_html += f"""
                    <tr style='border-bottom: 1px solid #f1f5f9;'>
                        <td style='padding: 12px; font-weight: 600; color: #0f172a;'>{row['Platform']}</td>
                        <td style='padding: 12px; text-align: right; color: #2563eb; font-weight: 700;'>₹{row['Price']:,}</td>
                        <td style='padding: 12px; text-align: right; color: #64748b;'>{row['Delivery']}</td>
                    </tr>
                    """
                table_html += "</table>"
                st.markdown(table_html, unsafe_allow_html=True)
                
            else: st.warning("Comparison data offline.")
        except Exception: st.warning("Failed to poll competitors.")

        st.markdown("<h4 style='color: #0f172a; margin-top: 30px;'>📈 30-Day Historical Trend</h4>", unsafe_allow_html=True)
        try:
            trend_response = requests.get(f"{BACKEND_URL}/query/trend/{st.session_state['active_product_id']}", timeout=10)
            if trend_response.status_code == 200:
                trend_data = trend_response.json().get("trend", [])
                df_trend = pd.DataFrame(trend_data)
                
                # FIXED Plotly Line Chart (Visible Text)
                fig_trend = px.line(df_trend, x='date', y='price', line_shape='spline')
                fig_trend.update_traces(line_color='#2563eb', line_width=3, fill='tozeroy', fillcolor='rgba(37, 99, 235, 0.1)')
                fig_trend.update_layout(
                    font=dict(color="#475569"), # Forces text to be dark gray
                    margin=dict(l=0, r=0, t=10, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(title="", showgrid=False),
                    yaxis=dict(title="", showgrid=True, gridcolor="#e2e8f0")
                )
                st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': False})
        except: st.warning("Could not sync trend visualization.")
            
    else:
        st.markdown("""
            <div class="info-card" style="text-align: center; padding: 40px 20px;">
                <h1 style="margin:0; font-size: 40px;">📉</h1>
                <p style="color: #64748b; margin-top: 10px;">No active data streams.</p>
            </div>
        """, unsafe_allow_html=True)
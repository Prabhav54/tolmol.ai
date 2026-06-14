import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from requests.exceptions import Timeout, ConnectionError

# 1. Page Configuration
st.set_page_config(
    page_title="Retail Intelligence Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Advanced CSS Injection
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] { display: none !important; }
    .stApp { background-color: #f4f7f6; font-family: 'Inter', -apple-system, sans-serif; }
    section[data-testid="stSidebar"] { background-color: #0f172a !important; border-right: 1px solid #1e293b; }
    section[data-testid="stSidebar"] * { color: #f8fafc !important; }
    div[data-testid="stChatMessageContent"] * { color: #0f172a !important; }
    .info-card {
        background: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 15px;
    }
    div.stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        color: white !important; border: none !important; border-radius: 8px !important;
        padding: 12px 24px !important; font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2) !important; transition: transform 0.2s ease !important; width: 100%;
    }
    div.stButton > button:hover { transform: translateY(-2px) !important; }
    .header-banner {
        background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
        padding: 24px 30px; border-radius: 12px; color: white; margin-bottom: 25px; 
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-left: 4px solid #3b82f6;
    }
    .header-banner h1 { margin: 0; font-size: 28px; font-weight: 800; color: white; }
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

def run_ingestion(target_url: str):
    with st.spinner(f"Extracting intelligence from URL..."):
        try:
            # Frontend no longer hashes the ID. It just passes the URL.
            payload = {"url": target_url}
            response = requests.post(f"{BACKEND_URL}/ingest", json=payload, timeout=180)
            
            if response.status_code == 200:
                data = response.json()
                # Backend returns the true database ID
                st.session_state["active_product_id"] = data.get("product_id")
                st.session_state["active_product_title"] = data.get("product_title", "Active Session")
                platform = data.get("detected_platform", "Web")
                st.success(f"Successfully synced data from {platform}!")
            else:
                st.error(f"Ingestion Error: {response.text}")
        except Timeout:
            st.error("Gateway Timeout: Pipeline took longer than 180s.")
        except ConnectionError:
            st.error("Backend Disconnected. Ensure Uvicorn is running.")

# 4. Sidebar Control Panel
with st.sidebar:
    st.markdown("### ⚡ Unified Pipeline")
    st.markdown("<p style='color:#94a3b8; font-size:14px;'>Paste URLs from Amazon, Flipkart, or Myntra.</p>", unsafe_allow_html=True)
    
    url_input = st.text_input("Target URL:", placeholder="https://amazon.in/...")
    if st.button("🚀 Initialize Sync", use_container_width=True):
        if url_input: run_ingestion(url_input)
        else: st.error("Please enter a URL first.")

    st.write("---")
    if st.button("🗑️ Purge Context", use_container_width=True):
        st.session_state["chat_history"] = []
        st.rerun()

# 5. Main Dashboard Layout
col_main, col_side = st.columns([6, 4], gap="large")

with col_main:
    if st.session_state["active_product_title"]:
        st.markdown(f"""
            <div class="header-banner">
                <h1>{st.session_state['active_product_title']}</h1>
                <p>Hybrid RAG Engine linked to Database ID: #{st.session_state['active_product_id']}</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div class="header-banner">
                <h1>Global Retail Intelligence</h1>
                <p>Awaiting target URL input from the control panel...</p>
            </div>
        """, unsafe_allow_html=True)

    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if "engine" in message:
                st.caption(f"⚡ Processed via {message['engine']}")
    
    if user_query := st.chat_input("Ask a question about pricing, reviews, or specs..."):
        if not st.session_state["active_product_id"]:
            st.warning("Action required: Please ingest a product URL first.")
        else:
            with st.chat_message("user"): st.write(user_query)
            st.session_state["chat_history"].append({"role": "user", "content": user_query})
            
            with st.spinner("Routing query through AI engines..."):
                try:
                    query_payload = {"question": user_query, "product_id": st.session_state["active_product_id"]}
                    response = requests.post(f"{BACKEND_URL}/query", json=query_payload, timeout=60)
                    
                    if response.status_code == 200:
                        result = response.json()
                        answer_text = result.get("response", "Processing error.")
                        engine_used = result.get("engine_selected", "Unknown Route")
                        
                        with st.chat_message("assistant"): 
                            st.write(answer_text)
                            st.caption(f"⚡ Processed via {engine_used}")
                            
                        st.session_state["chat_history"].append({"role": "assistant", "content": answer_text, "engine": engine_used})
                    else: 
                        st.error("RAG Engine Error.")
                except ConnectionError: 
                    st.error("Connection Refused.")

# 6. Right Side Panel (Context & Metrics)
with col_side:
    st.markdown("<h3 style='color: #0f172a; margin-bottom: 15px;'>📊 Real-time Database Telemetry</h3>", unsafe_allow_html=True)
    
    if st.session_state["active_product_id"]:
        product_id = st.session_state["active_product_id"]

        # COMPETITOR PRICING MATRIX
        st.markdown("<h4 style='color: #0f172a; margin-top: 20px;'>🔍 Pricing Cross-Reference</h4>", unsafe_allow_html=True)
        try:
            comp_response = requests.get(f"{BACKEND_URL}/query/compare/{product_id}", timeout=10)
            if comp_response.status_code == 200:
                comp_data = comp_response.json()
                df_comp = pd.DataFrame(comp_data.get("comparisons", []))
                
                if not df_comp.empty:
                    # Clean custom HTML Table for prices
                    table_html = (
                        "<table style='width:100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); font-size: 14px;'>"
                        "<tr style='background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;'>"
                        "<th style='padding: 12px; text-align: left; color: #475569;'>Platform</th>"
                        "<th style='padding: 12px; text-align: right; color: #475569;'>Price</th>"
                        "<th style='padding: 12px; text-align: right; color: #475569;'>Delivery</th>"
                        "</tr>"
                    )
                    for _, row in df_comp.iterrows():
                        table_html += f"<tr style='border-bottom: 1px solid #f1f5f9;'><td style='padding: 12px; font-weight: 600; color: #0f172a;'>{row['Platform']}</td><td style='padding: 12px; text-align: right; color: #2563eb; font-weight: 700;'>₹{row['Price']:,}</td><td style='padding: 12px; text-align: right; color: #64748b;'>{row['Delivery']}</td></tr>"
                    table_html += "</table>"
                    st.markdown(table_html, unsafe_allow_html=True)
                else:
                    st.info("Pricing data syncing...")
            else: st.warning("Database offline.")
        except Exception: st.warning("Failed to poll database.")

        # HISTORICAL TREND CHART
        st.markdown("<h4 style='color: #0f172a; margin-top: 30px;'>📈 Multi-Platform Trend</h4>", unsafe_allow_html=True)
        try:
            trend_response = requests.get(f"{BACKEND_URL}/query/trend/{product_id}", timeout=10)
            if trend_response.status_code == 200:
                trend_data = trend_response.json().get("trend", [])
                if trend_data:
                    df_trend = pd.DataFrame(trend_data)
                    # Automatically group by platform to handle multi-retailer lines
                    fig_trend = px.line(df_trend, x='date', y='price', color='platform', line_shape='spline')
                    fig_trend.update_layout(
                        font=dict(color="#475569"),
                        margin=dict(l=0, r=0, t=10, b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(title="", showgrid=False),
                        yaxis=dict(title="Price (₹)", showgrid=True, gridcolor="#e2e8f0"),
                        legend=dict(title="", orientation="h", y=1.1)
                    )
                    st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("Insufficient historical rows to render chart.")
        except: st.warning("Could not render history table.")
            
    else:
        st.markdown("""
            <div class="info-card" style="text-align: center; padding: 40px 20px;">
                <h1 style="margin:0; font-size: 40px;">📉</h1>
                <p style="color: #64748b; margin-top: 10px;">Connect to the Supabase stream to view live metrics.</p>
            </div>
        """, unsafe_allow_html=True)
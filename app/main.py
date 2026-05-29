import streamlit as st
import requests

# Base configuration setup
st.set_page_config(page_title="E-Commerce Intelligence Platform", page_icon="🛍️", layout="wide")
API_URL = "http://127.0.0.1:8000"

st.title("🛍️ Hybrid E-Commerce Intelligence Platform")
st.markdown("Drop any product link to scrape its contents instantly, run vector embeddings, and ask contextual questions.")

# Structural layout splitting: Left for Link Processing, Right for Chatting
col1, col2 = st.columns([1, 2])

with col1:
    st.header("🔌 Live Data Ingestion")
    target_url = st.text_input("Product URL Link", placeholder="https://example-ecommerce.com/product")
    assigned_id = st.number_input("Assign Product ID Lookup Key", min_value=100, max_value=999, value=101)
    
    if st.button("Scrape & Process Content", use_container_width=True):
        if not target_url:
            st.warning("Please provide a valid URL endpoint before initiating processing.")
        else:
            with st.spinner("Fetching site headers, chunking text sequences, and generating vectors..."):
                try:
                    payload = {"url": target_url, "product_id": assigned_id}
                    response = requests.post(f"{API_URL}/ingest", json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"Successfully Processed: **{data['product_title']}**")
                        st.info(f"Stored {data['chunks_inserted']} text segments into Docker Postgres Database (Port 5433).")
                    else:
                        st.error(f"Processing Failure: {response.json().get('detail', 'Unknown error')}")
                except Exception as ex:
                    st.error(f"Cannot reach backend server pipeline. Verify Uvicorn status. Exception: {ex}")

with col2:
    st.header("💬 Context-Aware Query Terminal")
    
    # Track conversational states dynamically across user sessions
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "engine" in msg:
                st.caption(f"Engine: {msg['engine']} | Route Intent: {msg['intent']}")

    user_query = st.chat_input("Ask a question (e.g., 'How many reviews discuss build durability?')")
    
    if user_query:
        # Display human inquiry visually
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)
            
        with st.chat_message("assistant"):
            with st.spinner("Analyzing intent, scanning database parameters..."):
                try:
                    query_payload = {"prompt": user_query, "product_id": assigned_id}
                    response = requests.post(f"{API_URL}/query", json=query_payload)
                    
                    if response.status_code == 200:
                        res_data = response.json()
                        answer_text = res_data["response"]
                        
                        st.markdown(answer_text)
                        st.caption(f"Engine: {res_data['engine']} | Logic Path: {res_data['query_executed']}")
                        
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer_text,
                            "engine": res_data["engine"],
                            "intent": res_data["intent"]
                        })
                    else:
                        st.error(f"Inference error returned: {response.json().get('detail')}")
                except Exception as runtime_err:
                    st.error(f"Communication layer failure: {runtime_err}")
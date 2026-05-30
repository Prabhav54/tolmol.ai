import streamlit as st
import requests
import hashlib

# Configure the page layout and title
st.set_page_config(
    page_title="Hybrid RAG E-Commerce Intelligence",
    page_icon="🛍️",
    layout="wide"
)

# Backend API Configuration (Points to your FastAPI Uvicorn server)
BACKEND_URL = "http://127.0.0.1:8000"

# Initialize persistent session state variables for chat history and active product ID
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "active_product_id" not in st.session_state:
    st.session_state["active_product_id"] = None
if "active_product_title" not in st.session_state:
    st.session_state["active_product_title"] = "No Product Loaded"

# Helper Function: Generate a unique, reproducible integer ID from any product URL
def generate_automated_id(url: str) -> int:
    clean_url = url.strip().lower()
    # Create a SHA-256 hash string, convert to integer, and restrict to a 6-digit limit
    hash_object = hashlib.sha256(clean_url.encode('utf-8'))
    unique_id = int(hash_object.hexdigest(), 16) % (10**6)
    return unique_id

# Title Section
st.title("🛍️ Hybrid RAG E-Commerce Intelligence Platform")
st.markdown("Analyze products, capture dynamic pricing, and run natural language calculations instantly.")
st.write("---")

# Layout: Split into a Sidebar for Data Ingestion and a Main Panel for the Chat System
with st.sidebar:
    st.header("📥 Ingest Product Data")
    st.markdown("Paste a product link from an e-commerce platform (e.g., Flipkart, Amazon, or Wikipedia) to parse its contents.")
    
    url_input = st.text_input("Product URL Link:", placeholder="https://flipkart.com/product-link-here...")
    
    if st.button("Process & Scrape Content", use_container_width=True):
        if not url_input:
            st.error("Please provide a valid URL link first.")
        else:
            with st.spinner("Launching headless browser to render JavaScript & extract details..."):
                try:
                    # Automatically generate the key silently
                    automated_id = generate_automated_id(url_input)
                    
                    # Prepare the network payload for your FastAPI endpoint
                    payload = {
                        "url": url_input,
                        "product_id": automated_id
                    }
                    
                    # Post data to your FastAPI ingestion route
                    response = requests.post(f"{BACKEND_URL}/ingest", json=payload, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Update session state with the backend results
                        st.session_state["active_product_id"] = automated_id
                        st.session_state["active_product_title"] = data.get("product_title", "Unknown Product")
                        
                        st.success(f"Successfully processed product context!")
                        st.metric(label="Chunks Generated & Stored", value=data.get("chunks_inserted", 0))
                    else:
                        st.error(f"Backend failed (Status {response.status_code}): {response.text}")
                        
                except Exception as e:
                    st.sidebar.error(f"Could not connect to the FastAPI server: {e}")

    st.write("---")
    st.markdown("### Active Session Metadata")
    st.caption(f"**Loaded Title:** {st.session_state['active_product_title']}")
    st.caption(f"**Automated Internal ID Key:** {st.session_state['active_product_id']}")
    
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state["chat_history"] = []
        st.rerun()

# Main Panel: Interactive Chat System
st.subheader(f"💬 Chatting About: {st.session_state['active_product_title']}")

# Display previous chat messages from history
for message in st.session_state["chat_history"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if "engine" in message:
            st.caption(f"⚙️ Route Executed: **{message['engine']}**")
        if "sql" in message and message["sql"]:
            st.code(message["sql"], language="sql")

# Accept new user queries
if user_query := st.chat_input("Ask about specifications, counts, features, or the pricing of this item..."):
    
    # Check if a product has been loaded into the database first
    if st.session_state["active_product_id"] is None:
        st.warning("Please submit and analyze a product URL via the left sidebar before asking questions.")
    else:
        # Display the user's message immediately
        with st.chat_message("user"):
            st.write(user_query)
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        
        # Request answer from backend routing engines
        with st.spinner("Routing query to execution layer..."):
            try:
                query_payload = {
                    "question": user_query,
                    "product_id": st.session_state["active_product_id"]
                }
                
                response = requests.post(f"{BACKEND_URL}/query", json=query_payload, timeout=20)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    answer_text = result.get("response", "No answer received.")
                    engine_used = result.get("engine_selected", "Unknown Engine")
                    sql_executed = result.get("sql_executed", None)
                    
                    # Display the AI response block
                    with st.chat_message("assistant"):
                        st.write(answer_text)
                        st.caption(f"⚙️ Route Executed: **{engine_used}**")
                        if sql_executed:
                            st.code(sql_executed, language="sql")
                    
                    # Save context to memory session list
                    st.session_state["chat_history"].append({
                        "role": "assistant",
                        "content": answer_text,
                        "engine": engine_used,
                        "sql": sql_executed
                    })
                else:
                    st.error(f"Query Engine Error (Status {response.status_code}): {response.text}")
                    
            except Exception as e:
                st.error(f"Failed to communicate with RAG engine backend: {e}")
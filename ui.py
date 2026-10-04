import streamlit as st
from db import get_threads, create_thread


def inject_custom_styles():
    """Inject custom Geist typography and dark minimalist CSS."""
    with open("assets/style.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_sidebar():
    """
    Renders the persistent left sidebar containing:
    1. Document Upload / Active File Status
    2. '+ New Chat' action
    3. Saved thread history from Supabase
    """
    with st.sidebar:
        st.markdown("### 📄 Document Hub")

        # Permanent PDF upload zone in sidebar
        uploaded_file = st.file_uploader(
            "Upload or Replace PDF",
            type=["pdf"],
            key="sidebar_pdf_uploader",
            help="Upload any PDF to index and query"
        )

        if st.session_state.get("active_doc_name"):
            st.success(f"Active: **{st.session_state['active_doc_name']}**")
        else:
            st.caption("No document loaded yet.")

        st.divider()

        # Thread Management
        st.markdown("### 💬 Conversations")
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            new_id = create_thread(title="New Chat")
            if new_id:
                st.session_state["active_thread_id"] = new_id
                st.session_state["thread_title_set"] = False
                st.rerun()

        # Render list of saved threads from Supabase
        threads = get_threads()
        if not threads:
            st.caption("No saved conversations.")
        else:
            for thread in threads:
                tid = thread["id"]
                title = thread["title"]
                is_active = (tid == st.session_state.get("active_thread_id"))
                
                label = f"▸ {title}" if is_active else f"  {title}"
                if st.button(label, key=f"thread_btn_{tid}", use_container_width=True):
                    st.session_state["active_thread_id"] = tid
                    st.rerun()

    return uploaded_file

from db import get_messages, save_message, update_thread_title
from rag_engine import retrieve_relevant_docs, stream_rag_answer


def render_empty_state():
    """Prominent default screen when no PDF has been uploaded yet."""
    st.markdown(
        """
        <div style="text-align: center; margin-top: 3rem; margin-bottom: 2rem;">
            <h1 style="font-size: 2.2rem; font-weight: 700; color: #FFFFFF;">
                PDF Question Answering
            </h1>
            <p style="color: #A1A1AA; font-size: 1rem; max-width: 500px; margin: 0 auto;">
                Drop any document, syllabus, research paper, or textbook below to extract insights, summarize chapters, and ask grounded questions.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # Center hero drag-and-drop zone
    center_file = st.file_uploader(
        "Drop your PDF file here",
        type=["pdf"],
        key="main_pdf_uploader",
        label_visibility="collapsed"
    )
    return center_file


def render_chat_area(vectorstore, gemini_api_key: str):
    """
    Renders active document bar, message history, live token streaming,
    and source citations.
    """
    thread_id = st.session_state.get("active_thread_id")
    if not thread_id:
        st.info("Creating a fresh conversation thread...")
        return

    # Pinned document badge at the top of the chat
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"📄 **Active Document:** `{st.session_state.get('active_doc_name')}`")
    with col2:
        st.caption("⚡ Live Citations On")

    st.markdown("<hr style='border-color: #1F1F23; margin: 0.5rem 0 1rem 0;'>", unsafe_allow_html=True)

    # 1. Render all previous messages from Supabase
    messages = get_messages(thread_id)
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📚 View Document Citations", expanded=False):
                    for src in msg["sources"]:
                        st.caption(f"**Page {src.get('page', '?')}:** {src.get('snippet', '')}")

    # 2. Accept new question from user
    if prompt := st.chat_input("Ask a question about your document..."):
        # Auto-title thread from the first question
        if not messages:
            update_thread_title(thread_id, prompt)

        # Display user message instantly
        with st.chat_message("user"):
            st.markdown(prompt)
        save_message(thread_id=thread_id, role="user", content=prompt)

        # Retrieve relevant passages
        docs, sources = retrieve_relevant_docs(vectorstore, prompt, k=4)

        # Stream assistant response in real time
        with st.chat_message("assistant"):
            stream_gen = stream_rag_answer(docs, prompt, messages, gemini_api_key)
            full_response = st.write_stream(stream_gen)

            # Display source citations directly under the answer
            if sources:
                with st.expander("📚 View Document Citations", expanded=False):
                    for src in sources:
                        st.caption(f"**Page {src.get('page', '?')}:** {src.get('snippet', '')}")

        # Persist assistant response & citations to Supabase
        save_message(thread_id=thread_id, role="assistant", content=full_response, sources=sources)
        st.rerun()

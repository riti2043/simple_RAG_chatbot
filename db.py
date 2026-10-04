import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase_client() -> Client:
    """Initialize and cache the Supabase connection pool."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def get_threads():
    """Fetch all conversation threads ordered by newest first."""
    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("threads")
            .select("id, title, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        st.warning(f"Database sync note: {str(e)}")
        return []


def create_thread(title: str = "New Chat") -> str:
    """Create a new conversation thread and return its UUID."""
    try:
        supabase = get_supabase_client()
        response = supabase.table("threads").insert({"title": title}).execute()
        if response.data:
            return response.data[0]["id"]
    except Exception as e:
        st.warning(f"Could not create thread: {str(e)}")
    return ""

def update_thread_title(thread_id: str, new_title: str):
    """Update a thread's title (e.g., using the first question asked)."""
    try:
        supabase = get_supabase_client()
        supabase.table("threads").update({"title": new_title[:40]}).eq("id", thread_id).execute()
    except Exception:
        pass


def get_messages(thread_id: str):
    """Retrieve full conversation history for a specific thread."""
    if not thread_id:
        return []
    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("messages")
            .select("id, role, content, sources, created_at")
            .eq("thread_id", thread_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def save_message(thread_id: str, role: str, content: str, sources: list = None):
    """Persist a user question or assistant answer to Supabase."""
    if not thread_id:
        return
    try:
        supabase = get_supabase_client()
        payload = {
            "thread_id": thread_id,
            "role": role,
            "content": content,
            "sources": sources or []
        }
        supabase.table("messages").insert(payload).execute()
    except Exception:
        pass
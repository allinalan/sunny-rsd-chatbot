"""
Rising Sun Division (RSD) — Sales Rep AI Assistant
====================================================
A Streamlit chatbot with RAG (Retrieval-Augmented Generation) powered by Claude.
Sales reps tap a link, ask a question, get a conversational answer instantly.

Author: Built for Rising Sun Division (RSD) Cutco Events Team
"""

# ============================================================
# ✏️  CUSTOMIZE THESE — Change to match your company
# ============================================================

BOT_NAME = "Sunny"
COMPANY_NAME = "Rising Sun Division"
COMPANY_WEBSITE = "https://www.risingsunevents.net"

SYSTEM_PROMPT = """You are Sunny, a friendly and knowledgeable assistant for Rising Sun Division (RSD)
sales representatives. RSD is a Cutco sales team based in Arizona that runs events-based sales through
kiosks, service & sales events, and marketplace shows like Mesa Marketplace.

Your job is to help reps quickly answer questions about:
- Cutco products (knives, cookware, flatware, wellness mats, business gifts)
- Show and event setup (kiosks, service events, Mesa Marketplace)
- Team processes (joining, ordering supplies, booth requirements, VectorConnect)
- Scripts, approaches, and how to handle objections
- Team contacts, documents, and resources on risingsunevents.net
- Meetings, important dates, and team structure

Key contacts reps may need:
- Alan Hernandez (Coordinator): 480-277-5057
- Matt Foss (Coordinator): 978-604-7112
- Adam Jeffrey (Storage/Visualization): 313-392-3495
- Team email: rsdcoordinator2@gmail.com

Personality guidelines:
- Warm, friendly, and conversational — like a knowledgeable teammate on the show floor, NOT a robot
- Concise but complete — give the full answer without padding or fluff
- Use bullet points for multi-step processes; use prose for simple single-answer questions
- Always assume the rep is in the field and needs a fast, clear answer on their phone

When you truly don't know: say "That's a great question — I'm not 100% sure on that one. Let me flag
this for your manager." Then provide whatever partial information you can, and suggest they call Alan
or Matt directly.

Always ground your answers in the provided knowledge base context. If the knowledge base has the answer,
use it. If not, say so honestly rather than guessing."""

# Phrases that trigger an escalation flag for manager follow-up.
# Add or remove phrases here to tune what gets escalated.
ESCALATION_TRIGGERS = [
    "want to quit",
    "thinking about leaving",
    "thinking of leaving",
    "considering quitting",
    "thinking about quitting",
    "burned out",
    "burned-out",
    "not making enough",
    "not hitting my numbers",
    "struggling with sales",
    "can't close",
    "nobody wants to buy",
    "losing motivation",
    "not motivated",
    "overwhelmed",
    "stressed out",
    "this job is too hard",
    "not worth it",
    "hate this job",
    "not cut out for this",
    "ready to quit",
    "done with this",
]

# ============================================================
# ⚙️  TECHNICAL SETTINGS — Less common to change
# ============================================================

CONVERSATION_MEMORY   = 10    # Number of past messages to include as context
CHUNK_SIZE_WORDS      = 500   # Target words per knowledge base chunk
CHUNK_OVERLAP_WORDS   = 50    # Word overlap between adjacent chunks
TOP_K_RESULTS         = 4     # How many knowledge base chunks to retrieve per query
MAX_RESPONSE_TOKENS   = 1024  # Max tokens in Claude's response

KNOWLEDGE_BASE_DIR      = "knowledge_base"
CHROMA_DB_DIR           = ".chroma_db"
QUESTION_LOG_FILE       = "question_log.jsonl"
PROCESSED_FILES_TRACKER = ".processed_files.json"

SUPPORTED_FILE_TYPES = [".pdf", ".docx", ".txt", ".md", ".csv"]
CLAUDE_MODEL         = "claude-sonnet-4-20250514"

# ============================================================
# IMPORTS
# ============================================================

import streamlit as st
import anthropic
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import json
import os
import hashlib
import datetime
from pathlib import Path
import pypdf
from docx import Document as DocxDocument
import csv

# ============================================================
# PAGE CONFIG — Must be the very first Streamlit call
# ============================================================

st.set_page_config(
    page_title=f"{BOT_NAME} | {COMPANY_NAME}",
    page_icon="☀️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ============================================================
# CUSTOM CSS — Mobile-first, clean design
# ============================================================

st.markdown("""
<style>
    /* Center and constrain width for mobile readability */
    .block-container { max-width: 760px; padding-top: 1rem; padding-bottom: 5rem; }

    /* Gradient header banner */
    .bot-header {
        background: linear-gradient(135deg, #E8500A 0%, #FF8C42 100%);
        color: white;
        padding: 18px 24px;
        border-radius: 14px;
        margin-bottom: 24px;
        text-align: center;
    }
    .bot-header h1 { color: white; margin: 0 0 4px; font-size: 1.7rem; font-weight: 700; }
    .bot-header p  { color: rgba(255,255,255,0.88); margin: 0; font-size: 0.92rem; }

    /* Chat bubbles */
    .stChatMessage { border-radius: 14px !important; }

    /* Escalation warning strip */
    .escalation-notice {
        background: #FFF8E1;
        border-left: 4px solid #FFA000;
        border-radius: 6px;
        padding: 10px 14px;
        margin-top: 10px;
        font-size: 0.85rem;
        color: #5D4037;
    }

    /* Subtle section dividers in sidebar */
    .sidebar-divider {
        border: none;
        border-top: 1px solid rgba(255,255,255,0.15);
        margin: 12px 0;
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# VECTOR DATABASE — Cached so it only loads once per session
# ============================================================

@st.cache_resource(show_spinner="Loading knowledge base engine...")
def get_chroma_collection():
    """
    Initialize a persistent ChromaDB client and return the collection.
    SentenceTransformer handles embedding — it downloads the model on first run (~80 MB).
    """
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.get_or_create_collection(
        name="rsd_knowledge_base",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


# ============================================================
# FILE HASHING — Detect changes to avoid re-processing
# ============================================================

def get_file_hash(file_path: str) -> str:
    """Return the SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def load_processed_files() -> dict:
    """Load the dict of {file_path: hash} for already-indexed files."""
    if os.path.exists(PROCESSED_FILES_TRACKER):
        with open(PROCESSED_FILES_TRACKER, "r") as f:
            return json.load(f)
    return {}


def save_processed_files(data: dict):
    """Persist the processed-files tracker."""
    with open(PROCESSED_FILES_TRACKER, "w") as f:
        json.dump(data, f, indent=2)


# ============================================================
# DOCUMENT LOADING — Supports PDF, DOCX, TXT, MD, CSV
# ============================================================

def extract_text(file_path: str) -> str:
    """
    Extract plain text from a file.
    Each format has its own reader; unrecognised formats return empty string.
    """
    ext = Path(file_path).suffix.lower()

    try:
        if ext == ".pdf":
            reader = pypdf.PdfReader(file_path)
            return "\n\n".join(
                page.extract_text() or "" for page in reader.pages
            )

        elif ext == ".docx":
            doc = DocxDocument(file_path)
            return "\n".join(p.text for p in doc.paragraphs)

        elif ext in (".txt", ".md"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif ext == ".csv":
            rows = []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for row in csv.reader(f):
                    rows.append(" | ".join(row))
            return "\n".join(rows)

    except Exception as e:
        st.warning(f"⚠️ Could not read **{Path(file_path).name}**: {e}")

    return ""


# ============================================================
# TEXT CHUNKING — Overlapping word-based windows
# ============================================================

def chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks of ~CHUNK_SIZE_WORDS words.
    Think of it like cutting a long scroll into overlapping index cards —
    each card shares a few lines with its neighbors so no context gets lost
    at the seams.
    """
    words = text.split()
    if not words:
        return []

    chunks, start = [], 0
    while start < len(words):
        end   = min(start + CHUNK_SIZE_WORDS, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(words):
            break
        start = end - CHUNK_OVERLAP_WORDS

    return chunks


# ============================================================
# DOCUMENT INGESTION — Add file to ChromaDB
# ============================================================

def remove_document(filename: str, collection) -> tuple[bool, str]:
    """
    Remove a document from the knowledge base completely:
      1. Deletes its chunks from ChromaDB
      2. Removes it from the processed-files tracker
      3. Deletes the file from disk (best-effort)
    Returns (success, message).
    """
    kb_path   = Path(KNOWLEDGE_BASE_DIR)
    file_path = kb_path / filename

    # Step 1 — purge vectors
    try:
        existing = collection.get(where={"source": filename})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception as e:
        return False, f"Could not remove vectors: {e}"

    # Step 2 — remove from processed tracker
    processed = load_processed_files()
    fp_str    = str(file_path)
    if fp_str in processed:
        del processed[fp_str]
        save_processed_files(processed)

    # Step 3 — delete the file itself
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception:
        # File delete failed (e.g. permissions), but vectors + tracker are already clean
        return True, (
            f"**{filename}** removed from the knowledge base, but the file itself "
            f"could not be deleted automatically. Please delete it manually from the "
            f"`knowledge_base/` folder."
        )

    return True, f"**{filename}** removed successfully."


def ingest_file(file_path: str, collection, source_name: str | None = None) -> int:
    """
    Ingest one file into the vector store.
    Returns the number of chunks stored (0 if nothing was indexed).
    """
    source_name = source_name or Path(file_path).name
    text = extract_text(file_path)
    if not text.strip():
        return 0

    chunks = chunk_text(text)
    if not chunks:
        return 0

    # Remove any previously stored chunks for this source
    try:
        existing = collection.get(where={"source": source_name})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    ids       = [f"{source_name}::chunk::{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_name, "chunk_index": i} for i in range(len(chunks))]

    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    return len(chunks)


def process_knowledge_base(collection) -> dict:
    """
    Scan the knowledge_base/ folder. Ingest new or modified files; skip unchanged ones.
    Returns a summary dict with keys: new, unchanged, errors.
    """
    kb_path = Path(KNOWLEDGE_BASE_DIR)
    kb_path.mkdir(exist_ok=True)

    processed = load_processed_files()
    summary   = {"new": [], "unchanged": [], "errors": []}

    for fp in kb_path.rglob("*"):
        if fp.suffix.lower() not in SUPPORTED_FILE_TYPES:
            continue

        fp_str    = str(fp)
        file_hash = get_file_hash(fp_str)

        if processed.get(fp_str) == file_hash:
            summary["unchanged"].append(fp.name)
            continue

        try:
            chunks = ingest_file(fp_str, collection)
            processed[fp_str] = file_hash
            summary["new"].append({"name": fp.name, "chunks": chunks})
        except Exception as e:
            summary["errors"].append({"name": fp.name, "error": str(e)})

    save_processed_files(processed)
    return summary


# ============================================================
# CONTEXT RETRIEVAL — Semantic search in ChromaDB
# ============================================================

def retrieve_context(query: str, collection) -> str:
    """
    Query the vector store for the most relevant knowledge base chunks.
    Returns a formatted string to inject into the system prompt.
    """
    try:
        total = collection.count()
        if total == 0:
            return ""

        results = collection.query(
            query_texts=[query],
            n_results=min(TOP_K_RESULTS, total),
        )

        docs      = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas",  [[]])[0]

        if not docs:
            return ""

        parts = []
        for doc, meta in zip(docs, metadatas):
            source = meta.get("source", "unknown")
            parts.append(f"[From: {source}]\n{doc}")

        return "\n\n---\n\n".join(parts)

    except Exception:
        return ""


# ============================================================
# ESCALATION DETECTION
# ============================================================

def is_escalation(message: str) -> bool:
    """Return True if the message contains any escalation trigger phrases."""
    lower = message.lower()
    return any(trigger in lower for trigger in ESCALATION_TRIGGERS)


# ============================================================
# QUESTION LOGGING — Append to JSONL file
# ============================================================

def log_question(question: str, answer: str, escalated: bool):
    """Write a single Q&A entry to the log file (one JSON object per line)."""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "question":  question,
        "answer":    answer,
        "escalation": escalated,
    }
    with open(QUESTION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_log() -> list[dict]:
    """Load all entries from the question log."""
    if not os.path.exists(QUESTION_LOG_FILE):
        return []
    entries = []
    with open(QUESTION_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


# ============================================================
# AI RESPONSE — RAG + Claude
# ============================================================

def get_response(
    user_message: str,
    history: list[dict],
    api_key: str,
    collection,
) -> tuple[str, bool]:
    """
    Build a context-enriched prompt and call Claude.
    Returns (response_text, escalated_flag).
    """
    # 1. Pull relevant knowledge base snippets
    context  = retrieve_context(user_message, collection)
    escalated = is_escalation(user_message)

    # 2. Build the system prompt
    system = SYSTEM_PROMPT

    if context:
        system += (
            "\n\n=== KNOWLEDGE BASE (use this to answer the question) ===\n"
            + context
        )
    else:
        system += (
            "\n\nNote: No matching knowledge base content was found for this query. "
            "Be transparent about this — suggest the rep check with their manager."
        )

    if escalated:
        system += (
            "\n\nSPECIAL INSTRUCTION: This rep may be experiencing personal struggles "
            "or feeling discouraged. Respond with extra warmth and empathy. Acknowledge "
            "how they're feeling, offer encouragement, and gently suggest they reach out "
            "to their manager for a one-on-one conversation."
        )

    # 3. Build message history (last N turns for context window)
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history[-CONVERSATION_MEMORY:]
    ]
    messages.append({"role": "user", "content": user_message})

    # 4. Call Claude
    client   = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_RESPONSE_TOKENS,
        system=system,
        messages=messages,
    )

    answer = response.content[0].text

    # 5. Persist the log entry
    log_question(user_message, answer, escalated)

    return answer, escalated


# ============================================================
# SIDEBAR — Admin Panel
# ============================================================

def render_sidebar(collection):
    """Render the admin panel in the sidebar."""
    with st.sidebar:
        st.markdown(f"## ⚙️ Admin Panel")
        st.caption(f"{COMPANY_NAME} · Internal Use")
        st.divider()

        # --- API Key ---
        st.markdown("### 🔑 Anthropic API Key")
        key_input = st.text_input(
            "API Key",
            type="password",
            value=st.session_state.get("api_key", ""),
            placeholder="sk-ant-api03-...",
            help="Get your key at console.anthropic.com",
            label_visibility="collapsed",
        )
        if key_input:
            st.session_state.api_key = key_input
            st.success("Key saved for this session ✓", icon="🔐")

        st.divider()

        # --- Knowledge Base Status ---
        st.markdown("### 📚 Knowledge Base")

        try:
            chunk_count = collection.count()
            processed   = load_processed_files()
            col1, col2  = st.columns(2)
            col1.metric("Chunks",    chunk_count)
            col2.metric("Documents", len(processed))

            if chunk_count == 0:
                st.warning("Knowledge base is empty. Upload documents below and click **Refresh**.")
        except Exception as e:
            st.error(f"DB error: {e}")

        if st.button("🔄 Refresh Knowledge Base", use_container_width=True):
            with st.spinner("Scanning and indexing documents..."):
                results = process_knowledge_base(collection)

            if results["new"]:
                for doc in results["new"]:
                    st.success(f"✅ **{doc['name']}** — {doc['chunks']} chunks")
            if results["unchanged"]:
                st.info(f"ℹ️ {len(results['unchanged'])} file(s) already up to date")
            if results["errors"]:
                for err in results["errors"]:
                    st.error(f"❌ **{err['name']}**: {err['error']}")
            if not results["new"] and not results["errors"]:
                st.info("✓ Everything is up to date!")

        st.divider()

        # --- Document Upload ---
        st.markdown("### 📤 Upload Documents")
        uploaded = st.file_uploader(
            "Drop files here",
            type=["pdf", "docx", "txt", "md", "csv"],
            help="Files are saved to the knowledge_base/ folder. Click Refresh to index them.",
            label_visibility="collapsed",
        )
        if uploaded:
            kb_path = Path(KNOWLEDGE_BASE_DIR)
            kb_path.mkdir(exist_ok=True)
            dest = kb_path / uploaded.name
            with open(dest, "wb") as f:
                f.write(uploaded.getbuffer())
            st.success(f"📁 Saved **{uploaded.name}**. Click **Refresh Knowledge Base** to index it.")

        st.divider()

        # --- Remove Documents ---
        st.markdown("### 🗑️ Remove Document")
        kb_path  = Path(KNOWLEDGE_BASE_DIR)
        kb_files = sorted([
            f.name for f in kb_path.rglob("*")
            if f.suffix.lower() in SUPPORTED_FILE_TYPES
        ]) if kb_path.exists() else []

        if kb_files:
            doc_to_remove = st.selectbox(
                "Select a document to remove",
                options=kb_files,
                label_visibility="collapsed",
            )
            if st.button("🗑️ Remove Selected Document", use_container_width=True):
                ok, msg = remove_document(doc_to_remove, collection)
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
        else:
            st.caption("No documents in the knowledge base yet.")

        st.divider()

        # --- Question Log ---
        st.markdown("### 📋 Question Log")
        log = load_log()

        if log:
            escalated_entries = [e for e in log if e.get("escalation")]
            col1, col2        = st.columns(2)
            col1.metric("Total Qs",     len(log))
            col2.metric("🚨 Escalated", len(escalated_entries))

            if escalated_entries:
                with st.expander(f"🚨 Escalated Questions ({len(escalated_entries)})"):
                    for entry in reversed(escalated_entries[-15:]):
                        ts = entry.get("timestamp", "")[:16].replace("T", " ")
                        st.markdown(f"**{ts}**")
                        st.markdown(f"> {entry['question']}")
                        st.markdown("---")

            with st.expander("📋 Recent Questions (last 25)"):
                for entry in reversed(log[-25:]):
                    ts   = entry.get("timestamp", "")[:16].replace("T", " ")
                    flag = "🚨 " if entry.get("escalation") else ""
                    st.markdown(f"**{flag}{ts}**")
                    st.markdown(f"**Q:** {entry['question']}")
                    answer_preview = entry['answer'][:250]
                    if len(entry['answer']) > 250:
                        answer_preview += "…"
                    st.markdown(f"**A:** {answer_preview}")
                    st.markdown("---")
        else:
            st.info("No questions logged yet.")

        st.divider()

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()


# ============================================================
# MAIN APP
# ============================================================

def main():
    # ── Session state defaults ────────────────────────────────
    if "messages"       not in st.session_state:
        st.session_state.messages = []
    if "api_key"        not in st.session_state:
        st.session_state.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if "kb_initialized" not in st.session_state:
        st.session_state.kb_initialized = False

    # ── Vector DB ─────────────────────────────────────────────
    collection = get_chroma_collection()

    # Auto-index the knowledge_base/ folder on first load
    if not st.session_state.kb_initialized:
        kb_path = Path(KNOWLEDGE_BASE_DIR)
        if kb_path.exists() and any(kb_path.rglob("*.*")):
            with st.spinner("Indexing knowledge base — this may take a moment on first run..."):
                process_knowledge_base(collection)
        st.session_state.kb_initialized = True

    # ── Sidebar ───────────────────────────────────────────────
    render_sidebar(collection)

    # ── Header ───────────────────────────────────────────────
    st.markdown(f"""
    <div class="bot-header">
        <h1>☀️ {BOT_NAME}</h1>
        <p>Your {COMPANY_NAME} sales assistant — ask me anything!</p>
    </div>
    """, unsafe_allow_html=True)

    # ── API key gate ──────────────────────────────────────────
    if not st.session_state.get("api_key"):
        st.warning(
            "👈 **No API key set.** Open the sidebar and enter your Anthropic API key to get started.",
            icon="⚠️",
        )
        st.info(
            "💡 **Tip for reps:** Ask your manager for the link — they'll send you one that's already set up!",
            icon="📱",
        )
        st.stop()

    # ── Chat history ──────────────────────────────────────────
    for msg in st.session_state.messages:
        avatar = "☀️" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("escalation"):
                st.markdown(
                    '<div class="escalation-notice">'
                    "🚨 <strong>Manager note:</strong> This conversation has been flagged. "
                    "Your manager will reach out to chat — you're not alone! 💛"
                    "</div>",
                    unsafe_allow_html=True,
                )

    # ── Welcome message (empty state) ────────────────────────
    if not st.session_state.messages:
        with st.chat_message("assistant", avatar="☀️"):
            st.markdown(f"""
Hey there! 👋 I'm **{BOT_NAME}**, your {COMPANY_NAME} assistant.

I can help you with things like:
- 🔪 **Cutco products** — knives, cookware, flatware, wellness mats, business gifts
- 📍 **Event locations** — Mesa Marketplace, kiosks, service events
- ✅ **Setup & booth requirements** — JV vs Varsity/Elite, what to bring
- 📋 **Scripts & approaches** — new customer, owner upgrade, objections
- 🔗 **Tools & resources** — VectorConnect, Textingbase, team documents
- 📞 **Contacts** — Alan (480-277-5057), Matt (978-604-7112), Adam Jeffrey

Type your question below and I'll get you an answer right away! 🚀
            """)

    # ── Chat input ────────────────────────────────────────────
    if prompt := st.chat_input("Ask me anything about Rising Sun Events…"):

        # Show the user's message immediately
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Generate and display the assistant's response
        with st.chat_message("assistant", avatar="☀️"):
            with st.spinner("Thinking…"):
                try:
                    # Pass history *without* the current message (it's already in `messages`)
                    history = st.session_state.messages[:-1]
                    answer, escalated = get_response(
                        prompt, history, st.session_state.api_key, collection
                    )

                    st.markdown(answer)

                    if escalated:
                        st.markdown(
                            '<div class="escalation-notice">'
                            "🚨 <strong>Heads up:</strong> This question has been flagged for your manager. "
                            "They'll be in touch — you've got a great team behind you! 💛"
                            "</div>",
                            unsafe_allow_html=True,
                        )

                    st.session_state.messages.append({
                        "role":      "assistant",
                        "content":   answer,
                        "escalation": escalated,
                    })

                except anthropic.AuthenticationError:
                    st.error("❌ Invalid API key. Double-check it in the sidebar.")
                except anthropic.RateLimitError:
                    st.error("⏱️ Rate limit reached — wait a moment and try again.")
                except anthropic.APIConnectionError:
                    st.error("🌐 Connection error — check your internet and try again.")
                except Exception as e:
                    st.error(f"❌ Something went wrong: {e}")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

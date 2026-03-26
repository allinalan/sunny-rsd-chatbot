# ☀️ Sunny — Rising Sun Events Sales Rep Chatbot

A web-based AI assistant your sales reps can access from any phone browser — no login, no app install.
Reps tap a link, type a question, and get a conversational answer powered by Claude AI and your own knowledge base.

---

## What Sunny Does

- **Answers rep questions instantly** using your knowledge base documents (PDFs, Word docs, text files, etc.)
- **Runs on any device** — phones, tablets, laptops — via a simple web link
- **Escalates sensitive questions** (reps struggling, wanting to quit, etc.) and flags them in your admin log
- **Logs every question** so you can see what your team is actually asking
- **Admin panel** built into the sidebar — upload docs, check status, view question logs, manage the knowledge base

---

## File Structure

```
chatbot/
├── app.py                  ← The entire application (one file)
├── requirements.txt        ← Python dependencies
├── README.md               ← This file
├── knowledge_base/         ← Drop your documents here
│   └── faq.md              ← Sample FAQ — fill this in with your real info
├── .chroma_db/             ← Auto-created: vector database storage
├── question_log.jsonl      ← Auto-created: all Q&A logs
└── .processed_files.json   ← Auto-created: tracks which files are indexed
```

---

## Quick Start — Running Locally

### Prerequisites

- Python 3.10 or newer
- An Anthropic API key (get one free at [console.anthropic.com](https://console.anthropic.com))

### Step 1 — Download the project

If you received this as a zip file, unzip it to a folder on your computer, e.g., `~/Documents/chatbot/`.

If you're using Git:
```bash
git clone <your-repo-url>
cd chatbot
```

### Step 2 — Create a virtual environment (recommended)

This keeps the project's packages isolated from the rest of your system.

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` at the start of your terminal prompt.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This will install Streamlit, the Anthropic SDK, ChromaDB, and the document parsers.
The sentence-transformer embedding model (~80 MB) downloads automatically on first run.

> ⏱️ This step can take 2–5 minutes depending on your internet speed. It only happens once.

### Step 4 — Fill in your knowledge base

Open `knowledge_base/faq.md` in any text editor and replace the `[FILL IN: ...]` placeholders with
your actual company info — show charge details, your commission structure, exact booth locations,
product descriptions, etc.

You can also drop additional files into the `knowledge_base/` folder:
- PDF files (product catalogs, policy docs, price sheets)
- Word documents (.docx)
- Plain text files (.txt, .md)
- Spreadsheets saved as CSV

### Step 5 — Run the app

```bash
streamlit run app.py
```

Streamlit will print a URL like `http://localhost:8501`. Open that in your browser.

### Step 6 — Enter your API key

Click the **☰ sidebar arrow** (top-left of the page) to open the Admin Panel. Paste your
Anthropic API key into the API Key field.

### Step 7 — Index your knowledge base

In the Admin Panel, click **🔄 Refresh Knowledge Base**. Sunny will read all your documents and
build the vector database. You'll see a confirmation for each file indexed.

That's it — Sunny is live! Test it by typing a question in the chat box.

---

## Giving Reps Access

When running locally, reps on the same WiFi network can access the app at your computer's local
IP address (e.g., `http://192.168.1.42:8501`). This is fine for testing but not suitable for
production — reps need access from anywhere.

**For production use, deploy to Streamlit Community Cloud (free) — see below.**

---

## Deployment — Streamlit Community Cloud (Free & Public)

Streamlit Community Cloud hosts your app for free and gives you a permanent public URL like:
`https://rsd-sunny.streamlit.app`

### Prerequisites for Cloud Deployment

1. A free [GitHub](https://github.com) account
2. A free [Streamlit Community Cloud](https://streamlit.io/cloud) account (sign in with GitHub)

### Step 1 — Push to GitHub

Create a new **private** GitHub repository and push your project to it.

```bash
git init
git add app.py requirements.txt knowledge_base/
git commit -m "Initial Sunny deployment"
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

> ⚠️ **Important:** Do NOT commit your API key to GitHub. We'll add it as a secret in the next step.
> The `.chroma_db/`, `question_log.jsonl`, and `.processed_files.json` files are auto-generated and
> don't need to be committed (add them to `.gitignore`).

### Step 2 — Create a `.gitignore` file (recommended)

Create a file called `.gitignore` in your project folder with this content:
```
.chroma_db/
question_log.jsonl
.processed_files.json
__pycache__/
venv/
*.pyc
```

### Step 3 — Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
3. Select your repository, branch (`main`), and main file (`app.py`)
4. Click **Advanced settings**
5. Under **Secrets**, add your API key:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-api03-..."
   ```
6. Click **Deploy**

Streamlit will build and launch your app. In a few minutes you'll have a public URL to share with your team.

> 💡 **Tip:** With the `ANTHROPIC_API_KEY` set as a secret, reps don't need to enter it — the app
> reads it automatically. The admin panel API key field becomes just a fallback.

### Step 4 — Share the link

Send the URL to your sales reps. They bookmark it, tap it from their phone, and they're in — no download, no login.

---

## Updating the Knowledge Base on Cloud Deployment

Since Streamlit Cloud's filesystem resets on redeploy, there are two approaches:

**Option A (simplest) — Commit docs to Git:**
Add your knowledge base files to the repository. Every time you push to GitHub, the app redeploys
with the updated docs and re-indexes them on first load.

```bash
git add knowledge_base/
git commit -m "Update FAQ with new show locations"
git push
```

**Option B — Use the upload panel:**
Use the Admin Panel → Upload Documents feature to upload files directly during a session.
Note: these uploads are temporary on Streamlit Cloud and reset on redeploy. Use this for quick
testing; commit to Git for permanent updates.

---

## Customizing Sunny

All the easy customizations are at the top of `app.py` under the `CUSTOMIZE THESE` section:

| Constant | What it does | Example |
|---|---|---|
| `BOT_NAME` | The chatbot's name | `"Sunny"` |
| `COMPANY_NAME` | Your company name | `"Rising Sun Events"` |
| `COMPANY_WEBSITE` | Your website URL | `"https://risingsunevents.net"` |
| `SYSTEM_PROMPT` | Claude's personality and instructions | (see the file) |
| `ESCALATION_TRIGGERS` | Phrases that flag a rep for manager follow-up | `["want to quit", ...]` |

For visual changes (colors, fonts), edit the CSS in the `CUSTOM CSS` section of `app.py`.
The brand orange (`#E8500A`) in the header gradient is easy to swap out.

---

## Admin Panel Guide

Open the sidebar by clicking the **☰** icon in the top-left corner.

| Section | What it does |
|---|---|
| 🔑 API Key | Enter your Anthropic key. Set once per session, or use Streamlit secrets for permanent setup. |
| 📚 Knowledge Base | Shows how many documents and chunks are indexed. Click Refresh to re-scan. |
| 📤 Upload Documents | Upload new files directly from the browser — no file system access needed. |
| 📋 Question Log | See every question reps have asked, with timestamps. Escalated questions are highlighted. |
| 🗑️ Clear Chat | Wipes the current conversation (doesn't delete logs). |

---

## Troubleshooting

**"No API key set" warning appears:**
Open the sidebar and paste your Anthropic API key into the API Key field.

**"Knowledge base is empty" warning:**
Click 🔄 Refresh Knowledge Base in the sidebar. If it shows 0 chunks after refreshing, check
that your files are in the `knowledge_base/` folder and are a supported format (PDF, DOCX, TXT, MD, CSV).

**App is slow on first load:**
The sentence-transformer embedding model downloads on first use (~80 MB). Subsequent loads are much faster.

**Sunny gives wrong or outdated answers:**
Update the relevant document in `knowledge_base/`, then click Refresh Knowledge Base in the admin panel.
The file hash tracker will detect the change and re-index only the updated file.

**Streamlit Cloud app "goes to sleep" after inactivity:**
Free Streamlit Cloud accounts sleep after a period of inactivity. The app wakes back up when someone
visits the URL — there's a ~20-second delay. Upgrade to a paid Streamlit plan to keep it always-on.

---

## Security Notes

- The Admin Panel is accessible to anyone who has the URL and opens the sidebar. For internal tools,
  this is usually fine — but if you want to restrict it, add a password check using
  [Streamlit's `st.secrets`](https://docs.streamlit.io/develop/api-reference/connections/st.secrets).
- Never commit your Anthropic API key to a public GitHub repository. Use Streamlit secrets instead.
- The question log (`question_log.jsonl`) contains all rep questions in plain text. Treat it as
  internal/confidential data.

---

## Adding This to Your Workflow

Here's the recommended way to keep Sunny sharp over time:

1. **Weekly:** Check the Question Log for questions Sunny couldn't answer well. Add those answers to `faq.md`.
2. **Monthly:** Review escalated questions. Is there a pattern? Does your training or FAQ need updating?
3. **When anything changes** (new show location, updated commission structure, new product line): update the relevant doc and click Refresh.

Think of the knowledge base like Sunny's brain — the more you feed it, the smarter she gets. 🧠

---

*Built for Rising Sun Events · Powered by Claude AI · Need help? Contact your system administrator.*

# Multi-Agent Research Assistant

An automated multi-agent pipeline that discovers, analyses, and summarises academic papers on any topic — with a web UI for uploading papers and viewing results, plus an optional human-in-the-loop approval step via the CLI.

---

## APIs Required

| API | Key needed? | Where to get it | Cost |
|---|---|---|---|
| **Google Gemini** | YES — recommended | https://aistudio.google.com/app/apikey | Free tier (no card) |
| **Groq** | YES — alternative | https://console.groq.com | Free tier (no card) |
| **arXiv** | NO | Built-in, no signup | Free forever |

You only need ONE of Gemini or Groq. Both are completely free with no credit card required.

> **Gemini:** 15 requests/min, 1500/day free
> **Groq:** Very generous free limits, great for heavy use

---

## Project Structure

```
research_assistant/
│
├── main.py                  ← CLI entry point
├── app.py                   ← Flask web UI entry point
├── config.py                ← Loads .env, detects provider (Gemini or Groq)
├── requirements.txt         ← All dependencies
├── .env.example             ← Template — copy to .env and add your key
│
├── agents/
│   ├── __init__.py
│   ├── tools.py             ← arXiv search function (free, no key needed)
│   └── definitions.py       ← All 5 AI agents (Gemini or Groq powered)
│
├── utils/
│   ├── __init__.py
│   ├── hitl.py              ← Human-in-the-loop approval gate (CLI only)
│   └── workflow.py          ← ResearchWorkflow — full pipeline orchestration
│
├── templates/
│   └── index.html           ← Web UI (dark theme, drag-and-drop upload)
│
└── output/                  ← Reports saved here as .md files
    └── report_<topic>_<timestamp>.md
```

---

## Two Ways to Run

### Option A — Web UI (recommended)
```powershell
python app.py
```
Open http://localhost:5000 in your browser. You can:
- Type a research topic
- Drag and drop PDF or .txt papers to include in the analysis
- Watch live progress as each agent runs
- View paper cards with insights and relevance scores
- Download the full Markdown report

### Option B — Command Line
```powershell
python main.py "transformer attention mechanisms"
python main.py --no-hitl "federated learning"
python main.py --max-papers 3 "quantum error correction"
python main.py   # prompts for topic interactively
```

---

## Setup (Windows — PowerShell)

### 1. Clone the repo
```powershell
git clone https://github.com/yourusername/research-assistant
cd research-assistant
```

### 2. Create and activate a virtual environment
```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

### 4. Create your .env file
```powershell
Copy-Item .env.example .env
```
Open `.env` and add your key:

**Using Gemini (recommended):**
```
GEMINI_API_KEY=AIzaSy_xxxxxxxxxxxxxxxxxxxxxxxx
MODEL=gemini-2.0-flash
MAX_PAPERS=5
OUTPUT_DIR=./output
ENABLE_HITL=true
```

**Using Groq instead:**
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
MODEL=llama-3.3-70b-versatile
MAX_PAPERS=5
OUTPUT_DIR=./output
ENABLE_HITL=true
```

### 5. Run
```powershell
python app.py        # web UI
python main.py "your topic"   # CLI
```

---

## What Happens When You Run It

```
1. Topic Refiner Agent
   Converts your topic into a precise academic search query
   + identifies 3-5 sub-topics and writes a plain-English description

2. HITL Checkpoint (CLI only, if ENABLE_HITL=true)
   Shows the refined query — press Enter to approve,
   type a new query to override, or type "quit" to abort
   (Web UI skips this — always auto-approves)

3. Paper Discovery Agent
   Calls the free arXiv API, fetches papers, re-ranks by relevance
   Also includes any papers you uploaded via the web UI

4. Insight Synthesizer Agent
   Analyses each paper one at a time:
   Contribution · Methodology · Key Results · Limitations · Relevance score

5. Report Compiler Agent
   Writes a structured Markdown report:
   Executive Summary → Topic Overview → Paper Analyses → Synthesis

6. Gap Analysis Agent
   Identifies what is MISSING from the literature:
   Research gaps · Methodological gaps · Application gaps · Future directions

7. Report saved to output/report_<topic>_<timestamp>.md
```

---

## How the Curriculum Tasks Map to Files

| Task | Description | File |
|---|---|---|
| Task 0 | Set up environment + load API keys | `config.py`, `.env.example` |
| Task 1 | Import libraries | `requirements.txt` |
| Task 2 | arXiv paper search function | `agents/tools.py` |
| Task 3 | Topic Refinement Agent | `agents/definitions.py` |
| Task 4 | Paper Discovery Agent | `agents/definitions.py` |
| Task 5 | Insight Synthesizer Agent | `agents/definitions.py` |
| Task 6 | Report Compiler Agent | `agents/definitions.py` |
| Task 7 | Gap Analysis Agent | `agents/definitions.py` |
| Task 8 | Termination conditions | `utils/workflow.py` |
| Task 9 | Multi-agent workflow | `utils/workflow.py` |
| Task 10 | UserProxyAgent for HITL | `utils/hitl.py` |
| Task 11 | Custom selector function | `utils/hitl.py` |
| Task 12 | Full interactive execution | `utils/workflow.py`, `main.py`, `app.py` |

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Google Gemini key (free at aistudio.google.com) |
| `GROQ_API_KEY` | — | Groq key (free at console.groq.com) |
| `MODEL` | `gemini-2.0-flash` | Model name — must match your provider |
| `MAX_PAPERS` | `5` | Papers fetched per run (1–10) |
| `OUTPUT_DIR` | `./output` | Where reports are saved |
| `ENABLE_HITL` | `true` | CLI only — pause for human review |

---

## Every Session (after first-time setup)

```powershell
cd D:\Projects\research_assistant
.venv\Scripts\activate
python app.py          # for web UI
# OR
python main.py "topic" # for CLI
```

---

## Output

Reports are saved to `output/report_<topic>_<timestamp>.md`.
Open in VS Code → press `Ctrl+Shift+V` for rendered Markdown preview.
Each run creates a new timestamped file — nothing is ever overwritten.

---

*Built with Python 3.13 · Google Gemini / Groq · Flask · Rich*
"""
app.py — Flask web UI for the Multi-Agent Research Assistant.

Run:  python app.py
Then open: http://localhost:5000
"""

import os
import threading
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "./uploads"
app.config["OUTPUT_FOLDER"] = "./output"
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB max upload

Path(app.config["UPLOAD_FOLDER"]).mkdir(exist_ok=True)
Path(app.config["OUTPUT_FOLDER"]).mkdir(exist_ok=True)

# In-memory job store: job_id -> {status, progress, log, result, error}
jobs: dict = {}


def run_pipeline(job_id: str, topic: str, uploaded_texts: list[str]):
    """Run the research pipeline in a background thread."""
    jobs[job_id]["status"]   = "running"
    jobs[job_id]["progress"] = 0
    log = jobs[job_id]["log"]

    try:
        from dotenv import load_dotenv
        load_dotenv()

        from config import cfg
        cfg.ENABLE_HITL = False  # always off in web mode

        # ── Stage 1: Topic Refinement ──────────────────────────────
        log.append({"stage": "Topic Refinement", "msg": f"Refining: {topic}"})
        jobs[job_id]["progress"] = 10

        from agents.definitions import (
            TopicRefinerAgent, PaperDiscoveryAgent,
            InsightSynthesizerAgent, ReportCompilerAgent, GapAnalysisAgent,
        )
        from agents.tools import search_arxiv

        refiner = TopicRefinerAgent()
        refined = refiner.run(topic)
        log.append({"stage": "Topic Refinement",
                    "msg": f"Search query: {refined['search_query']}"})
        jobs[job_id]["progress"] = 20

        # ── Stage 2: Paper Discovery ───────────────────────────────
        log.append({"stage": "Paper Discovery", "msg": "Searching papers (Semantic Scholar + arXiv)..."})

        raw_papers = search_arxiv(refined["search_query"])

        # Also add any uploaded paper texts as synthetic paper dicts
        for i, text in enumerate(uploaded_texts):
            if text.strip():
                raw_papers.insert(0, {
                    "title":    f"Uploaded Paper {i+1}",
                    "authors":  ["(Uploaded by user)"],
                    "year":     2024,
                    "abstract": text[:2000],
                    "url":      "",
                })

        discoverer = PaperDiscoveryAgent()
        papers     = discoverer.run(refined["search_query"], raw_papers)
        log.append({"stage": "Paper Discovery",
                    "msg": f"{len(papers)} paper(s) selected"})
        jobs[job_id]["progress"] = 35

        if not papers:
            raise ValueError("No papers found for this topic.")

        # ── Stage 3: Insight Synthesis ─────────────────────────────
        log.append({"stage": "Insight Synthesis",
                    "msg": f"Analysing {len(papers)} paper(s)..."})

        synthesizer = InsightSynthesizerAgent()
        insights    = []
        for i, paper in enumerate(papers):
            log.append({"stage": "Insight Synthesis",
                        "msg": f"[{i+1}/{len(papers)}] {paper['title'][:60]}..."})
            insight = synthesizer.run(paper, refined["search_query"])
            insights.append(insight)
            jobs[job_id]["progress"] = 35 + int(30 * (i + 1) / len(papers))

        insights.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        # ── Stage 4: Report Compilation ────────────────────────────
        log.append({"stage": "Report Compilation", "msg": "Writing report..."})
        jobs[job_id]["progress"] = 70

        compiler  = ReportCompilerAgent()
        report_md = compiler.run(insights, refined)
        jobs[job_id]["progress"] = 85

        # ── Stage 5: Gap Analysis ──────────────────────────────────
        log.append({"stage": "Gap Analysis", "msg": "Identifying research gaps..."})

        gap_agent = GapAnalysisAgent()
        gap_md    = gap_agent.run(insights, refined["search_query"])
        jobs[job_id]["progress"] = 95

        # ── Save report ────────────────────────────────────────────
        import re
        from datetime import datetime

        full_report  = report_md + "\n\n" + gap_md
        full_report += build_references(insights)

        slug = re.sub(r"[^\w\s-]", "", topic.lower())
        slug = re.sub(r"[\s_]+", "_", slug)[:40]
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"report_{slug}_{ts}.md"
        fpath = Path(app.config["OUTPUT_FOLDER"]) / fname
        fpath.write_text(full_report, encoding="utf-8")

        jobs[job_id]["status"]   = "done"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["result"]   = {
            "report_md":  full_report,
            "filename":   fname,
            "papers":     len(insights),
            "topic":      refined["search_query"],
            "sub_topics": refined.get("sub_topics", []),
            "insights":   insights,
        }
        log.append({"stage": "Complete", "msg": f"Report saved: {fname}"})

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = str(e)
        log.append({"stage": "Error", "msg": str(e)})


def build_references(insights: list) -> str:
    lines = ["\n\n## References\n"]
    for i, ins in enumerate(insights, 1):
        authors = "; ".join(ins.get("authors", [])[:6]) or "Unknown"
        year    = ins.get("year") or "n.d."
        title   = ins.get("title", "Untitled")
        url     = ins.get("url", "")
        ref     = f"{i}. {authors} ({year}). *{title}*."
        if url:
            ref += f" {url}"
        lines.append(ref)
    return "\n".join(lines)


# ── Routes ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    topic = request.form.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    # Handle uploaded files — extract text from PDFs or plain text files
    uploaded_texts = []
    for f in request.files.getlist("papers"):
        if f and f.filename:
            filename = f.filename.lower()
            if filename.endswith(".pdf"):
                try:
                    import pypdf
                    import io
                    reader = pypdf.PdfReader(io.BytesIO(f.read()))
                    text   = "\n".join(p.extract_text() or "" for p in reader.pages)
                    uploaded_texts.append(text[:3000])
                except Exception:
                    pass  # skip unreadable PDFs
            elif filename.endswith(".txt"):
                uploaded_texts.append(f.read().decode("utf-8", errors="ignore")[:3000])

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0, "log": [],
                    "result": None, "error": None}

    t = threading.Thread(target=run_pipeline,
                         args=(job_id, topic, uploaded_texts), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status":   job["status"],
        "progress": job["progress"],
        "log":      job["log"],
        "error":    job.get("error"),
        "result":   job.get("result") if job["status"] == "done" else None,
    })


@app.route("/download/<filename>")
def download(filename):
    path = Path(app.config["OUTPUT_FOLDER"]) / filename
    if not path.exists():
        return "File not found", 404
    return send_file(str(path), as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
import os
import re
import time
from datetime import datetime
from pathlib  import Path

from rich.console import Console
from rich.panel   import Panel
from rich.rule    import Rule

from config     import cfg
from agents     import (
    search_arxiv,
    TopicRefinerAgent,
    PaperDiscoveryAgent,
    InsightSynthesizerAgent,
    ReportCompilerAgent,
    GapAnalysisAgent,
)
from utils.hitl import request_approval

console = Console()


class ResearchWorkflow:
    """
    Orchestrates the full 5-agent research pipeline.

    Usage
    -----
    wf     = ResearchWorkflow()
    result = wf.run("transformer attention mechanisms")
    """

    def __init__(self):
        self.refiner     = TopicRefinerAgent()
        self.discoverer  = PaperDiscoveryAgent()
        self.synthesizer = InsightSynthesizerAgent()
        self.compiler    = ReportCompilerAgent()
        self.gap_agent   = GapAnalysisAgent()

        Path(cfg.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    def run(self, raw_topic: str) -> dict:
        """Run the complete pipeline. Returns the context dict."""
        start   = time.time()
        context = {"raw_topic": raw_topic, "aborted": False}

        console.print()
        console.print(Rule("[bold blue]Multi-Agent Research Assistant[/bold blue]", style="blue"))
        console.print(f"  Topic: [italic cyan]{raw_topic}[/italic cyan]\n")

        console.print(Rule("Stage 1 — Topic Refinement", style="purple"))
        refined = self.refiner.run(raw_topic)
        context["refined_topic"] = refined
        console.print(f"  [green]✓[/green] Search query: [cyan]{refined['search_query']}[/cyan]")
        for sub in refined.get("sub_topics", []):
            console.print(f"    • {sub}")

        context = request_approval(context)
        if context.get("aborted"):
            console.print("[red]Run aborted by user.[/red]")
            return context

        console.print(Rule("Stage 2 — Paper Discovery", style="cyan"))
        query      = context["refined_topic"]["search_query"]
        raw_papers = search_arxiv(query)               # Task 2: arXiv tool
        console.print(f"  arXiv returned {len(raw_papers)} raw result(s)")

        if not raw_papers:
            console.print("[red]  No papers found — aborting.[/red]")
            context["aborted"] = True
            return context

        papers = self.discoverer.run(query, raw_papers)  # re-rank
        context["papers"] = papers
        console.print(f"  [green]✓[/green] {len(papers)} paper(s) selected")
        for p in papers:
            console.print(f"    - {p['title'][:65]}{'…' if len(p['title'])>65 else ''}")

        console.print(Rule("Stage 3 — Insight Synthesis", style="blue"))
        insights = []
        for i, paper in enumerate(papers, 1):
            console.print(
                f"  [{i}/{len(papers)}] "
                f"{paper['title'][:60]}{'…' if len(paper['title'])>60 else ''}"
            )
            insight = self.synthesizer.run(paper, query)
            insights.append(insight)
            console.print(f"         relevance: {insight.get('relevance', '?')}/10")

        # Sort best-first
        insights.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        context["insights"] = insights
        console.print(f"  [green]✓[/green] All insights extracted")

        console.print(Rule("Stage 4 — Report Compilation", style="white"))
        report_md = self.compiler.run(insights, context["refined_topic"])
        context["report_markdown"] = report_md
        console.print("  [green]✓[/green] Report compiled")

        console.print(Rule("Stage 5 — Gap Analysis", style="magenta"))
        gap_md = self.gap_agent.run(insights, query)
        context["gap_markdown"] = gap_md
        console.print("  [green]✓[/green] Gap analysis complete")

        # ── Assemble + save ────────────────────────────────────────────
        full_report  = report_md + "\n\n" + gap_md
        full_report += self._build_references(insights)
        filepath     = self._save(full_report, raw_topic)
        context["report_filepath"] = filepath

        elapsed   = time.time() - start
        gap_count = len(re.findall(r"^- ", gap_md, re.MULTILINE))

        console.print()
        console.print(Panel(
            f"[bold green]Pipeline complete[/bold green] in {elapsed:.1f}s\n\n"
            f"  Papers analysed:  [cyan]{len(insights)}[/cyan]\n"
            f"  Gap items found:  [cyan]{gap_count}[/cyan]\n\n"
            f"  Report saved to:\n  [cyan]{filepath}[/cyan]",
            border_style="green", expand=False,
        ))

        return context

    def _build_references(self, insights: list[dict]) -> str:
        """Build references section programmatically — no LLM needed."""
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

    def _save(self, markdown: str, topic: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", topic.lower())
        slug = re.sub(r"[\s_]+", "_", slug)[:40]
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(cfg.OUTPUT_DIR) / f"report_{slug}_{ts}.md"
        path.write_text(markdown, encoding="utf-8")
        return str(path.resolve())
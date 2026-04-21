"""
agents/definitions.py — Tasks 3-7: All five research agents.
"""
import re
import time
from config import cfg


class BaseAgent:
    def __init__(self, name: str, system_prompt: str):
        self.name          = name
        self.system_prompt = system_prompt

    def call(self, user_message: str, max_tokens: int = 1500) -> str:
        if cfg.provider == "gemini":
            return self._call_gemini(user_message, max_tokens)
        else:
            return self._call_groq(user_message, max_tokens)

    def _call_gemini(self, user_message: str, max_tokens: int,
                     _retry: int = 0) -> str:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=cfg.GEMINI_API_KEY)
        try:
            response = client.models.generate_content(
                model=cfg.MODEL,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    max_output_tokens=max_tokens,
                    temperature=0,
                ),
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                if _retry < 3:
                    wait = 60 * (_retry + 1)
                    print(f"  [{self.name}] Rate limit — waiting {wait}s...")
                    time.sleep(wait)
                    return self._call_gemini(user_message, max_tokens, _retry+1)
                raise RuntimeError("Gemini rate limit exceeded. Switch to Groq.") from e
            raise

    def _call_groq(self, user_message: str, max_tokens: int) -> str:
        from groq import Groq
        client = Groq(api_key=cfg.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=cfg.MODEL,
            max_tokens=max_tokens,
            temperature=0,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user",   "content": user_message},
            ],
        )
        return response.choices[0].message.content.strip()


# ── Task 3 — Topic Refiner ─────────────────────────────────────────
class TopicRefinerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="TopicRefiner",
            system_prompt="""You are a research librarian who creates short academic search queries.

Convert the user's topic into a structured output for querying academic databases.

Respond in EXACTLY this format:

SEARCH_QUERY: <2-4 keywords only — short and precise, like you would type into Google Scholar>
SUB_TOPICS:
- <sub-topic 1>
- <sub-topic 2>
- <sub-topic 3>
DESCRIPTION: <2-3 sentences explaining the topic and why it matters>

CRITICAL RULES for SEARCH_QUERY:
- Maximum 4 words
- No filler words like "mechanisms", "underlying", "neurobiological", "developmental"
- Just the core subject keywords
- Examples of GOOD queries: "dyslexia reading", "transformer attention NLP", "federated learning privacy"
- Examples of BAD queries: "Neurobiological mechanisms underlying developmental dyslexia"
""",
        )

    def run(self, raw_topic: str) -> dict:
        response = self.call(f"Refine this research topic: {raw_topic}")
        return self._parse(response, raw_topic)

    def _parse(self, text: str, raw_topic: str) -> dict:
        result = {"original": raw_topic, "search_query": raw_topic,
                  "sub_topics": [], "description": ""}
        cur = None
        desc_lines = []
        for line in text.splitlines():
            s = line.strip()
            if s.upper().startswith("SEARCH_QUERY:"):
                result["search_query"] = s.split(":", 1)[1].strip(); cur = None
            elif s.upper().startswith("SUB_TOPICS:"):
                cur = "sub"
            elif s.upper().startswith("DESCRIPTION:"):
                cur = "desc"
                rest = s.split(":", 1)[1].strip()
                if rest: desc_lines.append(rest)
            elif cur == "sub" and s.startswith("-"):
                result["sub_topics"].append(s.lstrip("- ").strip())
            elif cur == "desc" and s:
                desc_lines.append(s)
        result["description"] = " ".join(desc_lines)
        return result


# ── Task 4 — Paper Discovery ───────────────────────────────────────
class PaperDiscoveryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="PaperDiscovery",
            system_prompt="""You are a research librarian who re-ranks academic papers by relevance.

Given a search query and a numbered list of papers, return ONLY the paper numbers
ranked from most to least relevant, one per line. Nothing else.

Example output:
3
1
5
2""",
        )

    def run(self, query: str, papers: list) -> list:
        if not papers:
            return []
        paper_list = "\n\n".join(
            f"{i+1}. TITLE: {p['title']}\n   ABSTRACT: {p['abstract'][:250]}..."
            for i, p in enumerate(papers)
        )
        try:
            response = self.call(
                f'Search query: "{query}"\n\nPapers to rank:\n\n{paper_list}',
                max_tokens=200,
            )
            ranked, seen = [], set()
            for line in response.splitlines():
                s = line.strip()
                if s.isdigit():
                    idx = int(s) - 1
                    if 0 <= idx < len(papers) and idx not in seen:
                        ranked.append(papers[idx]); seen.add(idx)
            for i, p in enumerate(papers):
                if i not in seen: ranked.append(p)
            return ranked[: cfg.MAX_PAPERS]
        except Exception:
            return papers[: cfg.MAX_PAPERS]


# ── Task 5 — Insight Synthesizer ──────────────────────────────────
class InsightSynthesizerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="InsightSynthesizer",
            system_prompt="""You are a research analyst extracting structured insights from papers.

Given a paper title and abstract, output EXACTLY these five fields.
Use present tense. Be specific.

CONTRIBUTION: <1-2 sentences — the single most important novel contribution>
METHODOLOGY: <1-2 sentences — the core technical or experimental approach>
KEY_RESULTS: <2-3 sentences — the strongest quantitative or qualitative findings>
LIMITATIONS: <1 sentence — the most significant limitation or open question>
RELEVANCE: <integer 1-10>  (10 = directly addresses the research topic)

Never add text outside the five fields above.""",
        )

    def run(self, paper: dict, topic: str) -> dict:
        authors = ", ".join(paper.get("authors", [])[:3])
        prompt  = (
            f"Research topic: {topic}\n\n"
            f"TITLE: {paper['title']}\n"
            f"AUTHORS: {authors}\n"
            f"YEAR: {paper.get('year', 'n/a')}\n"
            f"ABSTRACT:\n{paper['abstract']}"
        )
        try:
            return {**paper, **self._parse(self.call(prompt, max_tokens=600))}
        except Exception as e:
            return {**paper, "contribution": f"[Error: {e}]",
                    "methodology": "", "key_results": "",
                    "limitations": "", "relevance": 0}

    def _parse(self, text: str) -> dict:
        fields  = {"contribution": "", "methodology": "",
                   "key_results": "", "limitations": "", "relevance": 5}
        key_map = {
            "CONTRIBUTION:": "contribution", "METHODOLOGY:":  "methodology",
            "KEY_RESULTS:":  "key_results",  "LIMITATIONS:":  "limitations",
            "RELEVANCE:":    "relevance",
        }
        cur_key, buf = None, []

        def flush():
            if cur_key and buf:
                raw = " ".join(buf).strip()
                if cur_key == "relevance":
                    m = re.search(r"\d+", raw)
                    fields["relevance"] = min(int(m.group()), 10) if m else 5
                else:
                    fields[cur_key] = raw

        for line in text.splitlines():
            s = line.strip()
            matched = False
            for prefix, fld in key_map.items():
                if s.upper().startswith(prefix):
                    flush(); buf = []; cur_key = fld
                    rest = s[len(prefix):].strip()
                    if rest: buf.append(rest)
                    matched = True; break
            if not matched and s:
                buf.append(s)
        flush()
        return fields


# ── Task 6 — Report Compiler ───────────────────────────────────────
class ReportCompilerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ReportCompiler",
            system_prompt="""You are a senior research analyst writing clear Markdown reports.

Given a topic and paper insights, write a polished report in EXACTLY this structure:

# Research Report: <topic title>

## Executive Summary
(2-3 paragraphs synthesising the most important findings)

## Topic Overview
(1-2 paragraphs — why this topic matters, current state of the field)

## Paper Analyses

### <Paper Title> (<Year>)
**Authors:** <names>
**Relevance:** <score>/10
**Contribution:** <text>
**Methodology:** <text>
**Key Results:** <text>
**Limitations:** <text>
**Read more:** [Full paper](<url>)

(Repeat ### block for every paper)

## Synthesis of Major Themes
(3-4 paragraphs identifying patterns across papers)

---
*Report generated by Multi-Agent Research Assistant*""",
        )

    def run(self, insights: list, refined: dict) -> str:
        parts = []
        for i, ins in enumerate(insights, 1):
            authors = ", ".join(ins.get("authors", [])[:3])
            parts.append(
                f"--- Paper {i} ---\n"
                f"Title:        {ins['title']}\n"
                f"Authors:      {authors}\n"
                f"Year:         {ins.get('year', 'n/a')}\n"
                f"URL:          {ins.get('url', '')}\n"
                f"Relevance:    {ins.get('relevance', 0)}/10\n"
                f"Contribution: {ins.get('contribution', '')}\n"
                f"Methodology:  {ins.get('methodology', '')}\n"
                f"Key Results:  {ins.get('key_results', '')}\n"
                f"Limitations:  {ins.get('limitations', '')}\n"
            )
        return self.call(
            f"Research topic: {refined['search_query']}\n"
            f"Description: {refined.get('description', '')}\n\n"
            f"Paper insights:\n" + "\n".join(parts),
            max_tokens=3000,
        )


# ── Task 7 — Gap Analyzer ─────────────────────────────────────────
class GapAnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="GapAnalyzer",
            system_prompt="""You are a research strategist identifying gaps in the literature.

Given paper summaries, reason about what is ABSENT. Be specific.

Respond in EXACTLY this format:

## Research Gaps and Future Directions

### Research Gaps
- <specific unanswered question grounded in the papers>
- <gap 2>
- <gap 3>

### Methodological Gaps
- <experimental approach not yet applied>
- <gap 2>

### Application Gaps
- <real-world domain not yet studied>
- <gap 2>

### Suggested Future Directions
- <specific actionable research question>
- <direction 2>
- <direction 3>""",
        )

    def run(self, insights: list, topic: str) -> str:
        summary = "\n".join(
            f"Paper {i}: {ins['title']} ({ins.get('year','n/a')})\n"
            f"  Contribution: {ins.get('contribution','')}\n"
            f"  Key Results:  {ins.get('key_results','')}\n"
            f"  Limitations:  {ins.get('limitations','')}"
            for i, ins in enumerate(insights, 1)
        )
        return self.call(
            f"Research topic: {topic}\n\nPaper summaries:\n{summary}",
            max_tokens=1200,
        )
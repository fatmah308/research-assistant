"""
main.py — entry point.

Usage:
  python main.py
  python main.py "transformer attention mechanisms"
  python main.py --no-hitl "federated learning"
  python main.py --max-papers 3 "quantum error correction"
"""
import sys
import argparse
from rich.console import Console

from config         import cfg
from utils.workflow import ResearchWorkflow

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        prog="research_assistant",
        description="Multi-Agent Research Assistant",
    )
    parser.add_argument("topic", nargs="?", default=None)
    parser.add_argument("--no-hitl",     action="store_true")
    parser.add_argument("--max-papers",  type=int, default=None, metavar="N")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.no_hitl:
        cfg.ENABLE_HITL = False
    if args.max_papers:
        if not (1 <= args.max_papers <= 10):
            console.print("[red]--max-papers must be 1-10.[/red]")
            sys.exit(1)
        cfg.MAX_PAPERS = args.max_papers

    try:
        cfg.validate()
    except EnvironmentError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        sys.exit(1)

    if args.topic:
        topic = args.topic.strip()
    else:
        console.print("\n[bold blue]Multi-Agent Research Assistant[/bold blue]")
        console.print("Enter a topic and I'll discover and summarise papers.\n")
        topic = input("Research topic: ").strip()
        if not topic:
            console.print("[red]No topic provided.[/red]")
            sys.exit(1)

    wf     = ResearchWorkflow()
    result = wf.run(topic)
    sys.exit(0 if not result.get("aborted") else 1)


if __name__ == "__main__":
    main()
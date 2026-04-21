from rich.console import Console
from rich.panel   import Panel

console = Console()


def request_approval(context: dict) -> dict:
    """
    Task 10 & 11: Show the refined topic to the human and wait for input.

    Reads  : context["refined_topic"]
    Mutates: context["refined_topic"]["search_query"]  (if overridden)
             context["aborted"]                        (if quit)
    Returns: updated context
    """
    from config import cfg
    if not cfg.ENABLE_HITL:
        console.print("  [dim]HITL disabled — auto-approving.[/dim]")
        return context

    refined = context.get("refined_topic", {})

    sub_topics = "\n".join(
        f"  • {s}" for s in refined.get("sub_topics", [])
    )

    console.print()
    console.print(Panel(
        f"[bold]Original:[/bold]  {refined.get('original', '')}\n"
        f"[bold]Refined query:[/bold]  [cyan]{refined.get('search_query', '')}[/cyan]\n\n"
        f"[bold]Sub-topics:[/bold]\n{sub_topics}\n\n"
        f"[bold]Description:[/bold]\n{refined.get('description', '')[:220]}",
        title="[yellow]⏸  HITL Checkpoint — Review Refined Topic[/yellow]",
        subtitle="[dim]Enter = approve   |   type new query = override   |   quit = abort[/dim]",
        border_style="yellow",
        expand=False,
    ))

    console.print(
        "\n[yellow]Options:[/yellow]\n"
        "  Press [bold]Enter[/bold]             — approve and continue\n"
        "  Type a [bold]new search query[/bold] — override\n"
        "  Type [bold]quit[/bold]               — abort\n"
    )

    user_input = input("Your choice: ").strip()

    if user_input.lower() in ("quit", "exit", "q"):
        context["aborted"] = True
        return context

    if user_input:
        context["refined_topic"]["search_query"] = user_input
        console.print(f"  [green]✓[/green] Query overridden to: [cyan]{user_input}[/cyan]")
    else:
        console.print("  [green]✓[/green] Approved.")

    return context
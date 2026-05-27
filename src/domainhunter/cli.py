from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import store
from .config import load_config
from .generate import build_markov
from .models import RankedDomain
from .pipeline import check_domains, run_hunt
from .score import score_name

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Domain Hunter — find cool, cheap, unowned domains.")
watch_app = typer.Typer(no_args_is_help=True, help="Save + re-check favourite domains.")
app.add_typer(watch_app, name="watch")
console = Console()

_STATUS_STYLE = {"available": "green", "premium": "yellow", "taken": "red", "unknown": "dim"}
_VERIFIED = ("porkbun", "cache")


def _run_with_progress(coro_factory):
    """Drive an async pipeline, rendering a live progress bar per reported phase."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    ) as progress:
        bars: dict[str, int] = {}

        def cb(phase: str, done: int, total: int) -> None:
            if phase not in bars:
                bars[phase] = progress.add_task(phase, total=total)
            progress.update(bars[phase], completed=done, total=total)

        return asyncio.run(coro_factory(cb))


def _price_cell(value, verified: bool) -> str:
    if value is None:
        return "—"
    return ("" if verified else "~") + f"${value:,.2f}"


def _render(results: list[RankedDomain], show: int) -> None:
    results = sorted(results, key=lambda r: r.score, reverse=True)
    table = Table(title="Domain Hunter", header_style="bold")
    table.add_column("#", justify="right", style="dim")
    table.add_column("domain", style="bold")
    table.add_column("cool", justify="right")
    table.add_column("price", justify="right")
    table.add_column("renew", justify="right")
    table.add_column("status")
    table.add_column("via", style="dim")

    for i, r in enumerate(results[:show], 1):
        style = _STATUS_STYLE.get(r.status, "white")
        verified = r.source in _VERIFIED
        table.add_row(str(i), r.domain, f"{r.coolness:.2f}",
                      _price_cell(r.price, verified), _price_cell(r.renewal, verified),
                      f"[{style}]{r.status}[/]", r.source)
    console.print(table)

    n_avail = sum(1 for r in results if r.status == "available")
    n_prem = sum(1 for r in results if r.status == "premium")
    n_taken = sum(1 for r in results if r.status == "taken")
    console.print(
        f"[green]{n_avail} available[/] · [yellow]{n_prem} premium[/] · "
        f"[red]{n_taken} taken[/] · {len(results)} checked"
    )
    console.print("[dim]~ = TLD base rate (premium unverified) · plain = confirmed via Porkbun[/]")


def _export(results: list[RankedDomain], path_str: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [r.__dict__ for r in sorted(results, key=lambda r: r.score, reverse=True)]
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(rows, indent=2))
    else:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
            writer.writeheader()
            writer.writerows(rows)
    console.print(f"[dim]wrote {len(rows)} rows → {path}[/]")


@app.command()
def hunt(
    limit: int = typer.Option(None, help="Max domains to network-check this run."),
    budget: float = typer.Option(None, help="Override max first-year price (USD)."),
    tld: str = typer.Option(None, help="Comma-separated TLDs, overrides config."),
    strategy: str = typer.Option(None, help="Comma-separated generators to use."),
    verify: int = typer.Option(0, help="Premium-verify the top N gems via Porkbun (~10s each)."),
    export: str = typer.Option(None, help="Write results to a .csv or .json path."),
    show: int = typer.Option(30, help="How many rows to print."),
) -> None:
    """Generate cool names, find unowned ones, price + rank the gems."""
    config = load_config()
    if budget:
        config.budget = budget
    if tld:
        config.tlds = [t if t.startswith(".") else "." + t for t in tld.split(",")]
    if strategy:
        config.strategies = [s.strip() for s in strategy.split(",")]

    results = _run_with_progress(lambda cb: run_hunt(config, limit=limit, verify=verify, on_progress=cb))
    _render(results, show)
    saved = sum(1 for r in results if r.status in ("available", "premium"))
    if saved:
        console.print(f"[green]saved {saved} gems[/] → run [bold]dh gems[/] to revisit them")
    if not verify:
        console.print("[dim]tip: re-run with --verify N to confirm premium pricing on the top N gems.[/]")
    if export:
        _export(results, export)


@app.command()
def check(domains: list[str] = typer.Argument(..., help="Domains or bare labels to check.")) -> None:
    """Check availability + authoritative price for specific domains (bare labels expand across configured TLDs)."""
    config = load_config()
    results = _run_with_progress(lambda cb: check_domains(config, domains, on_progress=cb))
    _render(results, len(results))


@app.command()
def score(name: str = typer.Argument(..., help="A name (no TLD) to score.")) -> None:
    """Show the coolness breakdown for a single name."""
    config = load_config()
    markov = build_markov()
    value, breakdown = score_name(name, markov, config.min_len, config.max_len)
    console.print(f"[bold]{name}[/]  →  coolness [bold cyan]{value:.3f}[/]")
    table = Table(show_header=False, box=None)
    for k, v in breakdown.items():
        table.add_row(k, f"{v:.3f}")
    console.print(table)


@app.command()
def gems(
    show_all: bool = typer.Option(False, "--all", help="Include premium + everything saved, not just cheap available ones."),
    max_price: float = typer.Option(None, help="Only gems at/under this first-year price (USD)."),
    tld: str = typer.Option(None, help="Filter to one TLD, e.g. .com"),
    limit: int = typer.Option(50, help="Max rows to show."),
    export: str = typer.Option(None, help="Write the listing to a .csv or .json path."),
    clear: bool = typer.Option(False, "--clear", help="Delete all saved gems and exit."),
) -> None:
    """List gems saved from previous hunts (persisted in data/domains.db)."""
    con = store.connect()
    if clear:
        store.clear_gems(con)
        con.close()
        console.print("[dim]cleared saved gems[/]")
        return
    rows = store.list_gems(con, available_only=not show_all, max_price=max_price, tld=tld, limit=limit)
    con.close()
    if not rows:
        console.print("[dim]no saved gems yet — run `dh hunt` first[/]")
        return
    results = [
        RankedDomain(r["domain"], r["name"], r["tld"], r["coolness"],
                     r["status"] in ("available", "premium"), r["price"], r["renewal"],
                     bool(r["premium"]), r["score"], r["strategy"], r["status"], r["source"])
        for r in rows
    ]
    _render(results, limit)
    if export:
        _export(results, export)


@watch_app.command("add")
def watch_add_cmd(domain: str) -> None:
    con = store.connect()
    store.watch_add(con, domain.strip().lower())
    con.close()
    console.print(f"[green]watching[/] {domain}")


@watch_app.command("list")
def watch_list_cmd() -> None:
    con = store.connect()
    domains = store.watch_list(con)
    con.close()
    if not domains:
        console.print("[dim]watchlist empty[/]")
        return
    for d in domains:
        console.print(d)


@watch_app.command("rm")
def watch_rm_cmd(domain: str) -> None:
    con = store.connect()
    store.watch_remove(con, domain.strip().lower())
    con.close()
    console.print(f"removed {domain}")


@watch_app.command("run")
def watch_run_cmd() -> None:
    """Re-check every domain on the watchlist."""
    config = load_config()
    con = store.connect()
    domains = store.watch_list(con)
    con.close()
    if not domains:
        console.print("[dim]watchlist empty[/]")
        return
    results = _run_with_progress(lambda cb: check_domains(config, domains, on_progress=cb))
    _render(results, len(results))


if __name__ == "__main__":
    app()

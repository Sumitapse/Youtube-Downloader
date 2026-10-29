import os, sys
import questionary
import requests
from questionary import Style
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (Progress, SpinnerColumn, TextColumn, BarColumn,
                           DownloadColumn, TransferSpeedColumn, TimeRemainingColumn)
from rich.text import Text

console = Console()
UPLOAD_URL = "https://upload.gofile.io/uploadfile"
BLUE = "#00b0ff"

# hovered item = gofile blue, everything else = grey
style = Style([
    ("qmark", f"fg:{BLUE} bold"),
    ("question", "bold"),
    ("pointer", f"fg:{BLUE} bold"),
    ("highlighted", f"fg:{BLUE} bold"),
    ("text", "fg:#9e9e9e"),
    ("answer", "fg:#00e676 bold"),
])

BANNER = [
    " ██████╗  ██████╗ ███████╗██╗██╗     ███████╗",
    "██╔════╝ ██╔═══██╗██╔════╝██║██║     ██╔════╝",
    "██║  ███╗██║   ██║█████╗  ██║██║     █████╗  ",
    "██║   ██║██║   ██║██╔══╝  ██║██║     ██╔══╝  ",
    "╚██████╔╝╚██████╔╝██║     ██║███████╗███████╗",
    " ╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚══════╝╚══════╝",
]
SHADES = ["#0091ea", "#00a2f0", "#00b0ff", "#40c4ff", "#6fd3ff", "#9ee1ff"]

def banner():
    console.clear()
    t = Text()
    for line, c in zip(BANNER, SHADES):
        t.append(line + "\n", style=f"bold {c}")
    console.print(Align.center(t))
    console.print(Align.center(Text("  ▶  -SumitKumar  ", style="bold white on blue")))
    console.print(Align.center(Text("Anonymous file sharing via Gofile", style="dim")))
    console.print()

def human(n):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def fail(msg):
    console.print(Align.center(Panel(str(msg).strip()[-600:], title="Error",
                                     border_style="red", width=70)))
    sys.exit(1)

def choose_file(start):
    """Arrow keys to move, Enter on a folder opens it, Enter on a file returns it."""
    cwd = os.path.abspath(start)
    while True:
        try:
            entries = sorted(os.scandir(cwd), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            cwd = os.path.dirname(cwd)
            continue
        entries = [e for e in entries if not e.name.startswith(".")]

        choices = []
        if os.path.dirname(cwd) != cwd:
            choices.append(questionary.Choice(".. (go up)", value="UP"))
        for e in entries:
            if e.is_dir():
                choices.append(questionary.Choice(f"📁 {e.name}/", value="D:" + e.path))
            else:
                choices.append(questionary.Choice(f"{e.name}   ({human(e.stat().st_size)})",
                                                  value="F:" + e.path))
        if not choices:
            console.print("[yellow]Empty folder.[/]")
            cwd = os.path.dirname(cwd)
            continue

        pick = questionary.select(f"Choose a file   {cwd}", choices=choices,
                                  qmark="📤", style=style, pointer=">",
                                  use_indicator=False, instruction=" ").ask()
        if pick is None:
            return None
        if pick == "UP":
            cwd = os.path.dirname(cwd)
        elif pick.startswith("D:"):
            cwd = pick[2:]
        else:
            return pick[2:]

def upload(path):
    with Progress(SpinnerColumn(style=BLUE), TextColumn(f"[bold {BLUE}]Uploading"),
                  BarColumn(bar_width=None, complete_style=BLUE, finished_style="green"),
                  DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(),
                  console=console) as prog:
        with open(path, "rb") as fh:
            enc = MultipartEncoder(fields={"file": (os.path.basename(path), fh,
                                                    "application/octet-stream")})
            task = prog.add_task("up", total=enc.len)
            mon = MultipartEncoderMonitor(enc, lambda m: prog.update(task, completed=m.bytes_read))
            r = requests.post(UPLOAD_URL, data=mon,
                              headers={"Content-Type": mon.content_type}, timeout=None)
            prog.update(task, completed=enc.len)
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "ok":
        raise RuntimeError(j)
    return j["data"]

def main():
    banner()
    path = choose_file(os.getcwd())
    if not path:
        console.print(Align.center(Text("Cancelled.", style=f"bold {BLUE}")))
        return

    # safety: cookies.txt holds your login session
    if os.path.basename(path) == "cookies.txt":
        console.print("[bold red]⚠ cookies.txt contains your login session![/]")
        if not questionary.confirm("Really upload it?", default=False, style=style).ask():
            return

    try:
        data = upload(path)
    except Exception as e:
        fail(f"Upload failed: {e}")

    link = data.get("downloadPage") or "no link returned"
    console.print(Align.center(Panel(
        Align.center(Text.assemble(("✔ Uploaded!\n\n", "bold green"),
                                   (link, f"bold underline {BLUE}"))),
        title="Share this link", border_style="green", width=70)))

try:
    main()
except KeyboardInterrupt:
    console.print("\n[bold blue]Cancelled.[/]")
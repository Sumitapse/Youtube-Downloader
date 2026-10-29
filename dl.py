import json, os, re, subprocess, sys
import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.progress import (Progress, BarColumn, TextColumn,
                           TimeRemainingColumn, SpinnerColumn)

console = Console()
here = os.path.dirname(os.path.abspath(__file__))
cookies = os.path.join(here, "cookies.txt")

common = ["yt-dlp", "--js-runtimes", "node"]
if os.path.exists(cookies):
    common += ["--cookies", cookies]

style = Style([
    ("qmark", "fg:#ff0000 bold"),
    ("question", "bold"),
    ("pointer", "fg:#ff0000 bold"),
    ("highlighted", "fg:#ff4d4d bold"),
    ("selected", "fg:#00e676"),
    ("answer", "fg:#00e676 bold"),
    ("text", ""),
])

BANNER = [
    "██╗   ██╗ ██████╗ ██╗   ██╗████████╗██╗   ██╗██████╗ ███████╗",
    "╚██╗ ██╔╝██╔═══██╗██║   ██║╚══██╔══╝██║   ██║██╔══██╗██╔════╝",
    " ╚████╔╝ ██║   ██║██║   ██║   ██║   ██║   ██║██████╔╝█████╗  ",
    "  ╚██╔╝  ██║   ██║██║   ██║   ██║   ██║   ██║██╔══██╗██╔══╝  ",
    "   ██║   ╚██████╔╝╚██████╔╝   ██║   ╚██████╔╝██████╔╝███████╗",
    "   ╚═╝    ╚═════╝  ╚═════╝    ╚═╝    ╚═════╝ ╚═════╝ ╚══════╝",
]
SHADES = ["#ff0000", "#ff1a1a", "#ff3333", "#ff4d4d", "#ff6666", "#ff8080"]

LABELS = {2160: "4K Ultra HD", 1440: "2K QHD", 1080: "Full HD",
          720: "HD", 480: "SD", 360: "Low", 240: "Very low", 144: "Tiny"}

def banner():
    console.clear()
    t = Text()
    for line, c in zip(BANNER, SHADES):
        t.append(line + "\n", style=f"bold {c}")
    console.print(Align.center(t))
    console.print(Align.center(Text("▶  D O W N L O A D E R   •   MP4 only   •   yt-dlp + ffmpeg",
                                    style="bold white on red")))
    console.print()

def fail(msg):
    console.print(Panel(msg.strip()[-600:], title="Error", border_style="red"))
    sys.exit(1)

def run_json(args, status):
    with console.status(f"[bold red]{status}", spinner="dots12"):
        r = subprocess.run(common + args, capture_output=True, text=True)
    if r.returncode != 0:
        fail(r.stderr)
    return json.loads(r.stdout)

def dur(s):
    if not s:
        return "LIVE"
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02}:{sec:02}" if h else f"{m}:{sec:02}"

def pick_video():
    q = questionary.text("Paste a link or type a search:", qmark="🔎", style=style).ask()
    if not q or not q.strip():
        return None
    q = q.strip()
    if q.startswith("http"):
        return q
    res = run_json(["--flat-playlist", "-J", f"ytsearch10:{q}"], f"Searching for “{q}”...")
    entries = [e for e in res["entries"] if e]
    if not entries:
        fail("No results found.")
    choices = [questionary.Choice(
        f"{e['title'][:60]:<60}  {(e.get('channel') or '')[:20]:<20}  {dur(e.get('duration'))}",
        value=f"https://www.youtube.com/watch?v={e['id']}") for e in entries]
    return questionary.select("Pick a video (↑/↓, Enter):", choices=choices,
                              qmark="🎬", style=style, pointer="▶").ask()

def pick_quality(info):
    heights = sorted({f["height"] for f in info["formats"]
                      if f.get("height") and f.get("vcodec") != "none"}, reverse=True)
    console.print(Panel(
        f"[bold]{info['title']}[/]\n[dim]{info.get('channel', '')}  •  {dur(info.get('duration'))}[/]",
        border_style="red", title="Selected video"))
    return questionary.select(
        "Choose quality:", qmark="🎞 ", style=style, pointer="▶",
        choices=[questionary.Choice(f"{h}p  {LABELS.get(h, '')}", value=h) for h in heights]).ask()

def download(url, h):
    fmt = (f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
           f"bv*[height<={h}]+ba/b[height<={h}]")
    cmd = common + ["--no-playlist", "-q", "--progress", "--newline", "--no-simulate",
                    "--progress-template", "download:PROG %(progress._percent_str)s",
                    "--print", "after_move:filepath",
                    "-f", fmt, "--merge-output-format", "mp4", url]
    path = ""
    with Progress(SpinnerColumn(style="red"), TextColumn("[bold red]Downloading"),
                  BarColumn(bar_width=None, complete_style="red", finished_style="green"),
                  TextColumn("[bold]{task.percentage:>5.1f}%"),
                  TimeRemainingColumn(), console=console) as prog:
        task = prog.add_task("dl", total=100)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            line = line.strip()
            m = re.search(r"PROG\s+([\d.]+)%", line)
            if m:
                prog.update(task, completed=float(m.group(1)))
            elif line and not line.startswith("PROG"):
                path = line
        p.wait()
        if p.returncode == 0:
            prog.update(task, completed=100)
    if p.returncode != 0:
        fail("Download failed.")
    size = os.path.getsize(path) / 1024 / 1024 if os.path.exists(path) else 0
    console.print(Panel(f"[bold green]✔ Done![/]\n[white]{os.path.basename(path)}[/]\n"
                        f"[dim]{size:.1f} MB  •  {os.path.dirname(os.path.abspath(path))}[/]",
                        border_style="green"))

def main():
    while True:
        banner()
        url = pick_video()
        if not url:
            break
        info = run_json(["--no-playlist", "-J", url], "Fetching available qualities...")
        h = pick_quality(info)
        if h is None:
            break
        download(url, h)
        if not questionary.confirm("Download another?", qmark="🔁", style=style).ask():
            break
    console.print("[bold red]Bye! 👋[/]")

try:
    main()
except KeyboardInterrupt:
    console.print("\n[bold red]Cancelled.[/]")
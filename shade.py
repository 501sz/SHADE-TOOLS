#!/usr/bin/env python3
"""
SHADE TOOLS - a terminal security console for Linux (Arch-first).

Design principle: never more dangerous to its owner than the threat it
defends against. Every action is read-only, reversible, or explicitly
confirmed. SHADE is a cockpit over trusted system tools (firejail,
cryptsetup, wg, clamscan, lsof/fuser, ufw) -- it reinvents none of them.

Run as your normal user. Individual actions elevate with sudo only for
the specific command that needs it; the console itself never runs as root.
"""

import os
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Presentation layer: use `rich` if available, else fall back to plain ANSI.
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    _console = Console()
    HAVE_RICH = True
except Exception:  # rich not installed -- degrade gracefully
    _console = None
    HAVE_RICH = False


# ANSI codes for the no-rich fallback
class C:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    GREY = "\033[90m"


BANNER = r"""
   _____ _   _          _____  ______   _______ ____   ____  _       _____
  / ____| | | |   /\   |  __ \|  ____| |__   __/ __ \ / __ \| |     / ____|
 | (___ | |_| |  /  \  | |  | | |__       | | | |  | | |  | | |    | (___
  \___ \|  _  | / /\ \ | |  | |  __|      | | | |  | | |  | | |     \___ \
  ____) | | | |/ ____ \| |__| | |____     | | | |__| | |__| | |____ ____) |
 |_____/|_| |_/_/    \_\_____/|______|    |_|  \____/ \____/|______|_____/
"""

TAGLINE = "  terminal security console  ::  defensive tools only"


def clear_screen():
    """Clear the visible terminal only. Does NOT touch shell history or
    system logs -- that would be anti-forensic and break user expectations."""
    os.system("cls" if os.name == "nt" else "clear")


def show_banner():
    clear_screen()
    if HAVE_RICH:
        _console.print(Text(BANNER, style="bold cyan"))
        _console.print(Text(TAGLINE, style="dim"))
        _console.print()
    else:
        print(C.BOLD + C.CYAN + BANNER + C.RESET)
        print(C.DIM + TAGLINE + C.RESET)
        print()


def have(tool: str) -> bool:
    """Is a system tool available on PATH?"""
    return shutil.which(tool) is not None


def run(cmd, capture=False, check=False):
    """Run a command. cmd is a list (never a shell string, to avoid injection).
    Returns CompletedProcess. Elevation, when needed, is done by prefixing
    'sudo' in the specific feature, not by running SHADE as root."""
    try:
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd[0]}: not found")
    except KeyboardInterrupt:
        raise
    except Exception as e:  # noqa: BLE001
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


# --- small styled-print helpers that work with or without rich -------------
def info(msg):
    print((C.CYAN + "[*] " + C.RESET if not HAVE_RICH else "") + msg) if not HAVE_RICH \
        else _console.print(f"[cyan][*][/cyan] {msg}")


def ok(msg):
    _console.print(f"[green][+][/green] {msg}") if HAVE_RICH \
        else print(C.GREEN + "[+] " + C.RESET + msg)


def warn(msg):
    _console.print(f"[yellow][!][/yellow] {msg}") if HAVE_RICH \
        else print(C.YELLOW + "[!] " + C.RESET + msg)


def err(msg):
    _console.print(f"[red][x][/red] {msg}") if HAVE_RICH \
        else print(C.RED + "[x] " + C.RESET + msg)


def pause():
    input("\n    press Enter to return to the menu ... ")


def confirm(prompt: str) -> bool:
    """Explicit yes for any action with side effects."""
    ans = input(f"    {prompt} [y/N] ").strip().lower()
    return ans in ("y", "yes")


def require(tool: str, pkg: str = None) -> bool:
    """Guard: warn and bail if a needed tool is missing, telling the user
    exactly what to install on Arch."""
    if have(tool):
        return True
    pkg = pkg or tool
    err(f"'{tool}' is not installed.")
    info(f"install it on Arch with:  sudo pacman -S {pkg}")
    return False


# ===========================================================================
# FEATURE 1: TRAPBOX  -- sandbox launcher (firejail / bubblewrap)
# ===========================================================================
def trapbox():
    show_banner()
    print("  TRAPBOX  ::  run apps trapped in an isolated sandbox\n")
    if not require("firejail"):
        pause()
        return

    print("    [1] Launch an app sandboxed")
    print("    [2] Launch an app sandboxed with a throwaway home (--private)")
    print("    [3] List active sandboxes")
    print("    [4] Kill a sandbox")
    print("    [0] Back")
    choice = input("\n  trapbox> ").strip()

    if choice == "1" or choice == "2":
        app = input("    app to launch (e.g. firefox): ").strip()
        if not app:
            return
        if not have(app):
            warn(f"'{app}' not found on PATH -- launching anyway in case it's a flatpak/alias")
        cmd = ["firejail"]
        if choice == "2":
            # throwaway home: the app sees an empty temp home, discarded on exit.
            cmd.append("--private")
        cmd.append(app)
        info(f"launching: {' '.join(cmd)}")
        # Launch detached so the console stays usable.
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ok(f"'{app}' started in a sandbox")
        except Exception as e:  # noqa: BLE001
            err(f"could not start: {e}")

    elif choice == "3":
        res = run(["firejail", "--list"], capture=True)
        out = (res.stdout or "").strip()
        print()
        print(out if out else "    (no active sandboxes)")

    elif choice == "4":
        name = input("    sandbox name or PID to kill: ").strip()
        if name and confirm(f"kill sandbox '{name}'?"):
            run(["firejail", "--shutdown=" + name])
            ok("shutdown signal sent")

    pause()


# ===========================================================================
# FEATURE 2: DISKGUARD -- LUKS / UEFI status (honest replacement for Paniclock)
# ===========================================================================
def diskguard():
    show_banner()
    print("  DISKGUARD  ::  full-disk encryption status\n")
    print("    The real 'panic' protection: if your disk is encrypted, then a")
    print("    lost, stolen, or seized machine is unreadable ciphertext once")
    print("    powered off. No risky self-wipe -- just power down.\n")

    if not require("lsblk", "util-linux"):
        pause()
        return

    # Detect LUKS containers via lsblk fstype column.
    res = run(["lsblk", "-o", "NAME,FSTYPE,MOUNTPOINT"], capture=True)
    out = res.stdout or ""
    encrypted = "crypto_LUKS" in out
    print(out)
    print()
    if encrypted:
        ok("LUKS encryption detected on this system.")
    else:
        warn("No LUKS container detected.")
        info("Full-disk encryption must be set up at install time (or via a")
        info("careful in-place conversion). SHADE will not modify your disks.")
        info("Arch guide:  https://wiki.archlinux.org/title/Dm-crypt")

    # UEFI firmware password can't be read from the OS -- just remind.
    print()
    info("Reminder: also set a UEFI/BIOS firmware password in your firmware")
    info("setup screen. SHADE cannot read or set it from inside the OS.")
    pause()


# ===========================================================================
# FEATURE 3: TUNNEL -- your own WireGuard config up/down
# ===========================================================================
def tunnel():
    show_banner()
    print("  TUNNEL  ::  bring your own WireGuard VPN up or down\n")
    print("    SHADE toggles a WireGuard config YOU trust. It never picks a")
    print("    'free VPN' for you -- free VPNs often log and sell your traffic,")
    print("    the opposite of what this tool is for.\n")

    if not require("wg-quick", "wireguard-tools"):
        pause()
        return

    print("    [1] Bring a tunnel up")
    print("    [2] Bring a tunnel down")
    print("    [3] Show status")
    print("    [0] Back")
    choice = input("\n  tunnel> ").strip()

    if choice == "1":
        iface = input("    config name (e.g. wg0): ").strip() or "wg0"
        if confirm(f"bring up '{iface}' (needs sudo)?"):
            run(["sudo", "wg-quick", "up", iface])
    elif choice == "2":
        iface = input("    config name (e.g. wg0): ").strip() or "wg0"
        if confirm(f"bring down '{iface}' (needs sudo)?"):
            run(["sudo", "wg-quick", "down", iface])
    elif choice == "3":
        run(["sudo", "wg", "show"])
    pause()


# ===========================================================================
# FEATURE 4: SCAN -- ClamAV over a chosen directory (honest labeling)
# ===========================================================================
def scan():
    show_banner()
    print("  SCAN  ::  check files for KNOWN malware (ClamAV)\n")
    print("    Honest note: this detects *known* signatures only. A clean")
    print("    result means 'nothing known was found', not 'definitely safe'.\n")

    if not require("clamscan", "clamav"):
        pause()
        return

    default = os.path.expanduser("~/Downloads")
    target = input(f"    directory to scan [{default}]: ").strip() or default
    if not os.path.isdir(target):
        err(f"not a directory: {target}")
        pause()
        return

    info(f"scanning {target} (recursive)... this can take a while")
    # -r recursive, -i show only infected. Signatures should be updated via
    # freshclam separately; we note that if the DB looks stale.
    run(["clamscan", "-r", "-i", target])
    print()
    info("tip: keep signatures fresh with:  sudo freshclam")
    pause()


# ===========================================================================
# FEATURE 5: WATCHTOWER -- who is using the webcam / mic right now
# ===========================================================================
def watchtower():
    show_banner()
    print("  WATCHTOWER  ::  webcam & microphone access guard\n")

    if not (have("fuser") or have("lsof")):
        err("need 'fuser' or 'lsof' to inspect device holders.")
        info("install on Arch with:  sudo pacman -S psmisc lsof")
        pause()
        return

    print("    [1] Who is using the webcam right now?")
    print("    [2] Who is using the microphone right now?")
    print("    [0] Back")
    print()
    warn("A physical webcam sticker beats any software guard -- use one too.")
    choice = input("\n  watchtower> ").strip()

    devices = []
    if choice == "1":
        devices = [d for d in ("/dev/video0", "/dev/video1", "/dev/video2")
                   if os.path.exists(d)]
    elif choice == "2":
        # ALSA/PulseAudio capture devices
        devices = [d for d in ("/dev/snd/", ) if os.path.exists(d)]
    else:
        return

    if not devices:
        info("no matching device nodes present on this system.")
        pause()
        return

    found_any = False
    for dev in devices:
        if have("fuser"):
            res = run(["fuser", "-v", dev], capture=True)
            holders = (res.stderr or res.stdout or "").strip()
        else:
            res = run(["lsof", dev], capture=True)
            holders = (res.stdout or "").strip()
        if holders:
            found_any = True
            warn(f"{dev} is in use by:")
            print(holders)
    if not found_any:
        ok("no process is currently holding the camera/mic.")

    # Opt-in kill -- never automatic.
    print()
    if found_any and confirm("kill one of these processes?"):
        pid = input("    PID to kill: ").strip()
        if pid.isdigit() and confirm(f"terminate PID {pid}?"):
            run(["kill", pid])
            ok(f"sent TERM to {pid}")
    pause()


# ===========================================================================
# FEATURE 6: STATUS -- read-only security dashboard
# ===========================================================================
def status():
    show_banner()
    print("  STATUS  ::  read-only security dashboard\n")

    rows = []

    # Firewall (ufw)
    if have("ufw"):
        res = run(["sudo", "ufw", "status"], capture=True)
        active = "Status: active" in (res.stdout or "")
        rows.append(("Firewall (ufw)", "active" if active else "inactive", active))
    else:
        rows.append(("Firewall (ufw)", "ufw not installed", False))

    # Disk encryption
    if have("lsblk"):
        res = run(["lsblk", "-o", "FSTYPE"], capture=True)
        enc = "crypto_LUKS" in (res.stdout or "")
        rows.append(("Disk encryption (LUKS)", "present" if enc else "not detected", enc))

    # Active sandboxes
    if have("firejail"):
        res = run(["firejail", "--list"], capture=True)
        n = len([l for l in (res.stdout or "").splitlines() if l.strip()])
        rows.append(("Active sandboxes", str(n), n > 0))

    # VPN
    if have("wg"):
        res = run(["sudo", "wg", "show"], capture=True)
        up = bool((res.stdout or "").strip())
        rows.append(("WireGuard tunnel", "up" if up else "down", up))

    # Pending updates (Arch)
    if have("checkupdates"):
        res = run(["checkupdates"], capture=True)
        n = len([l for l in (res.stdout or "").splitlines() if l.strip()])
        rows.append(("Pending updates", str(n), n == 0))

    # Render
    if HAVE_RICH:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Check")
        table.add_column("State")
        for name, val, good in rows:
            style = "green" if good else "yellow"
            table.add_row(name, f"[{style}]{val}[/{style}]")
        _console.print(table)
    else:
        for name, val, good in rows:
            mark = (C.GREEN + "OK " if good else C.YELLOW + "-- ") + C.RESET
            print(f"    {mark} {name:<28} {val}")

    print()
    info("Dashboard is read-only. SHADE never auto-deletes files or shuts")
    info("down on a guess -- awareness first, your decision second.")
    pause()


# ===========================================================================
# MENU
# ===========================================================================
MENU = [
    ("1", "TRAPBOX", "run apps trapped in an isolated sandbox", trapbox),
    ("2", "DISKGUARD", "full-disk encryption status", diskguard),
    ("3", "TUNNEL", "your own WireGuard VPN up/down", tunnel),
    ("4", "SCAN", "check files for known malware", scan),
    ("5", "WATCHTOWER", "webcam & mic access guard", watchtower),
    ("6", "STATUS", "read-only security dashboard", status),
]


def main_menu():
    while True:
        show_banner()
        for key, name, desc, _ in MENU:
            if HAVE_RICH:
                _console.print(f"    [bold cyan]{key}[/bold cyan]  "
                               f"[bold]{name:<12}[/bold] [dim]{desc}[/dim]")
            else:
                print(f"    {C.CYAN}{key}{C.RESET}  {C.BOLD}{name:<12}{C.RESET}"
                      f"{C.GREY}{desc}{C.RESET}")
        print()
        print(f"    {'0'}  {'EXIT':<12}leave SHADE")
        choice = input("\n  shade> ").strip()

        if choice == "0":
            clear_screen()
            print("stay safe.\n")
            return
        for key, _, _, fn in MENU:
            if choice == key:
                try:
                    fn()
                except KeyboardInterrupt:
                    print()  # clean line, back to menu
                break


def main():
    if os.name == "nt":
        print("SHADE TOOLS targets Linux; run it on your Arch machine.")
        sys.exit(1)
    # Refuse to run as root: features elevate per-action instead.
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("Do not run SHADE as root. Run as your normal user;")
        print("individual actions will ask for sudo only when needed.")
        sys.exit(1)
    try:
        main_menu()
    except (KeyboardInterrupt, EOFError):
        clear_screen()
        print("stay safe.\n")


if __name__ == "__main__":
    main()

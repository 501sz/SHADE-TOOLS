# SHADE TOOLS

**A terminal security console for Linux.**
One command — `defense` — clears the screen, raises a banner, and gives you a
numbered menu of defensive tools: sandboxing, encryption status, VPN control,
malware scanning, webcam guarding, and a security dashboard.

```
   _____ _   _          _____  ______   _______ ____   ____  _       _____
  / ____| | | |   /\   |  __ \|  ____| |__   __/ __ \ / __ \| |     / ____|
 | (___ | |_| |  /  \  | |  | | |__       | | | |  | | |  | | |    | (___
  \___ \|  _  | / /\ \ | |  | |  __|      | | | |  | | |  | | |     \___ \
  ____) | | | |/ ____ \| |__| | |____     | | | |__| | |__| | |____ ____) |
 |_____/|_| |_/_/    \_\_____/|______|    |_|  \____/ \____/|______|_____/

  terminal security console  ::  defensive tools only
```

---

## Table of contents

- [What SHADE is](#what-shade-is)
- [What SHADE is not](#what-shade-is-not)
- [The design principle](#the-design-principle)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Design decisions, explained](#design-decisions-explained)
- [Threat model](#threat-model)
- [What SHADE deliberately refuses to do](#what-shade-deliberately-refuses-to-do)
- [Why it's open source](#why-its-open-source)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## What SHADE is

SHADE TOOLS is a **cockpit**, not an engine.

Linux already has excellent, battle-tested security tooling: Firejail and
bubblewrap for sandboxing, LUKS for full-disk encryption, WireGuard for private
tunnels, ClamAV for signature scanning, `lsof`/`fuser` for seeing who's holding
your webcam. The problem isn't that these tools don't exist. The problem is that
they're scattered across a dozen man pages, each with its own flags, and most
people never touch them because the friction is just high enough to lose to
inertia.

SHADE puts them behind one command and one menu. It **wraps** trusted,
peer-reviewed tools. It **reinvents none of them.**

That distinction is the whole project. SHADE contains no custom cryptography, no
homegrown detection heuristics, no clever tricks. If SHADE disappeared tomorrow,
everything it does could still be done by hand — it would just be slower, and you
would probably skip it. Removing that friction *is* the product.

## What SHADE is not

- **Not an antivirus.** It calls ClamAV. ClamAV catches known signatures and
  misses plenty. SHADE says so, in the tool, every time you scan.
- **Not an EDR.** It does not attempt behavioral threat detection, because doing
  that well is a research problem and doing it badly is worse than not doing it
  at all.
- **Not an offensive toolkit.** No exploitation, no cracking, no network attack
  tooling. Defensive only. This is not a phase and not negotiable.
- **Not a replacement for good habits.** A physical webcam sticker beats
  WATCHTOWER. Full-disk encryption beats any script. SHADE tells you this rather
  than pretending otherwise.

## The design principle

> **A defensive tool must never be more dangerous to its owner than the threat it
> defends against.**

This is the rule every feature was measured against, and it killed several ideas
that sounded exciting on paper:

- **A "panic wipe"** that copies your files to a USB stick and then deletes
  everything on the machine? *Cut.* The stick fails, or fills up, or gets yanked
  mid-transfer — and now your data is simply gone. The actual goal ("a stolen
  machine reveals nothing") is solved completely and safely by full-disk
  encryption. Power off. Done.
- **Auto-detecting "suspicious activity"**, then deleting the file and shutting
  down? *Cut.* Heuristics produce false positives constantly. That design
  destroys your own work whenever it guesses wrong. Real EDR products quarantine
  and alert; they do not auto-delete-and-halt, for exactly this reason.
- **Auto-connecting to "the best free VPN"?** *Cut.* Free VPNs frequently log and
  monetise traffic. A privacy tool that silently routes you through an unknown
  third party is not a privacy tool.

Each was replaced with the boring, correct mechanism that achieves the same
underlying goal without the footgun. That substitution *is* the tool.

---

## Features

| # | Name | What it does | Wraps |
|---|------|--------------|-------|
| 1 | **TRAPBOX** | Launch any app inside an isolated sandbox. Optional throwaway home (`--private`) so an untrusted file can't reach your real data. List and kill running sandboxes. | `firejail` |
| 2 | **DISKGUARD** | Reports whether LUKS full-disk encryption is active and guides you to set it up if not. **Read-only — never modifies your disks.** | `lsblk`, `cryptsetup` |
| 3 | **TUNNEL** | Brings *your own* WireGuard configuration up or down; shows status. | `wg-quick`, `wg` |
| 4 | **SCAN** | Scans a directory (default `~/Downloads`) for known malware signatures. | `clamscan` |
| 5 | **WATCHTOWER** | Shows which process is currently holding the webcam or microphone. Offers an **opt-in** kill — never automatic. | `fuser` / `lsof` |
| 6 | **STATUS** | Read-only dashboard: firewall state, disk encryption, active sandboxes, VPN status, pending updates. | several |

SHADE detects any tool that isn't installed and prints the exact command to
install it. You don't need everything up front — the console degrades gracefully
and tells you precisely what's missing.

---

## Installation

**Requirements:** Linux and Python 3.8+. That's it. SHADE has no mandatory Python
dependencies and renders on plain ANSI.

```bash
git clone https://github.com/YOURNAME/shade-tools.git
cd shade-tools

mkdir -p ~/.local/share/shade ~/.local/bin
cp shade.py ~/.local/share/shade/
chmod +x ~/.local/share/shade/shade.py
ln -sf ~/.local/share/shade/shade.py ~/.local/bin/defense
```

Ensure `~/.local/bin` is on your `PATH`:

```bash
fish_add_path ~/.local/bin                                    # fish
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc      # bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc       # zsh
```

Then, from anywhere:

```bash
defense
```

### Optional: nicer output

SHADE works fine without it, but will use
[`rich`](https://github.com/Textualize/rich) for colored tables if present:

```bash
sudo pacman -S python-rich     # Arch
pip install rich               # elsewhere
```

### The underlying tools

Install whichever features you intend to use:

```bash
# Arch
sudo pacman -S firejail wireguard-tools clamav psmisc lsof ufw util-linux

# Debian / Ubuntu
sudo apt install firejail wireguard-tools clamav psmisc lsof ufw util-linux
```

---

## Usage

Run `defense`. The screen clears, the banner appears, you pick a number.

**Trap an untrusted download in a box**
`1` → `2` (throwaway home) → name your PDF viewer. The app launches sandboxed
with an empty temporary home. Whatever that file tries to do, it does it to a box
that evaporates on close — not to your documents.

**Check whether your laptop is actually protected if stolen**
`2` — DISKGUARD reports whether LUKS is present. If it says no, you've just
learned something important, and the tool points you at the documentation to fix
it.

**See who's using your camera right now**
`5` → `1`. If a process is holding `/dev/video0`, you get its name and PID, and
the option — your choice, never automatic — to kill it.

**Morning health check**
`6` — one screen: firewall on? disk encrypted? VPN up? sandboxes running? updates
pending?

---

## Design decisions, explained

### SHADE refuses to run as root

The console runs as your normal user and **exits immediately if launched as
root.** Actions that genuinely need privilege (bringing up a WireGuard interface,
reading firewall state) prefix `sudo` for that single command.

*Why:* a long-lived interactive process running as root is a large, unnecessary
target. All software has bugs; you want SHADE's bugs to live in an unprivileged
process. Privilege should be requested narrowly, briefly, and visibly.

### Commands are argument lists, never shell strings

Every subprocess call passes a list (`["firejail", "--list"]`), never a string
handed to a shell. This structurally eliminates shell injection: a filename
containing a semicolon is just a filename, not a command.

### "Clear the screen" means clear the screen

SHADE clears the *visible terminal* to draw a clean banner. It does **not** wipe
your shell history or system logs.

*Why:* silently destroying a user's history is both surprising and, functionally,
anti-forensics — the behavior of malware, not of a tool asking for your trust.
Same clean look, none of the baggage.

### DISKGUARD is read-only

It reports encryption status and points you at documentation. It will never
invoke `cryptsetup` destructively, never repartition, never "helpfully" convert
anything.

*Why:* disk encryption setup is a deliberate, irreversible, backup-first
operation. Any tool that offers to do it from a menu in one keystroke is a tool
that will eventually eat someone's data.

### SCAN tells the truth about what it found

A clean result is reported as *"nothing known was found"* — never *"you're safe."*

*Why:* the most dangerous output a security tool can produce is unearned
confidence. Signature scanning has a real, well-documented ceiling, and a tool
that hides that ceiling is worse than no tool at all, because it changes the
user's behavior on the basis of a false belief.

---

## Threat model

SHADE targets the **single-user Linux desktop**, and it is deliberate about which
threats it does and does not address.

**Threats SHADE helps with**

| Threat | How |
|---|---|
| Malicious downloaded file (PDF, archive, document) | TRAPBOX opens it sandboxed, with a throwaway home |
| Untrusted or over-permissioned application | TRAPBOX confines it to a Firejail profile |
| Laptop lost, stolen, or seized | DISKGUARD verifies LUKS — a powered-off disk is unreadable ciphertext |
| Silent webcam or microphone access | WATCHTOWER surfaces the process holding the device |
| Known commodity malware | SCAN (ClamAV signatures) |
| Silent security drift (firewall off, updates unapplied) | STATUS makes it visible |
| Eavesdropping on hostile Wi-Fi | TUNNEL raises your trusted WireGuard endpoint |

**Threats SHADE does *not* protect against — stated plainly**

- **Kernel-level or root compromise.** If an attacker already has root, they can
  lie to every tool SHADE calls — including SHADE. No userspace console survives
  that. This is the tamper problem inherent to *all* host-based security tooling,
  not a flaw unique to this one.
- **Targeted, novel, or bespoke malware.** Signature scanning will not see it.
- **Firmware implants, hardware tampering, or evil-maid attacks against an
  unencrypted bootloader.** Mitigate with a UEFI password and Secure Boot —
  outside SHADE's reach.
- **You, running something dangerous on purpose.** Sandboxing helps. Nothing
  overrides a determined user's `sudo`.
- **A Firejail vulnerability or a bad profile.** Firejail is SUID-root and has a
  CVE history precisely because of that. It remains a large net win, but the
  trade is real and you deserve to know it. If this concerns you, use Flatpak
  (unprivileged bubblewrap) for everyday high-risk apps and reserve Firejail for
  one-off launches.

If a security tool won't tell you what it *can't* do, don't trust what it claims
it can.

---

## What SHADE deliberately refuses to do

These refusals are part of the design, not gaps in it.

- ❌ **No "panic wipe" or self-destruct.** Data destruction on a hotkey or a
  heuristic is a weapon pointed at its owner. Use full-disk encryption.
- ❌ **No auto-deletion of "suspicious" files.** False positives are guaranteed;
  irreversible responses to guesses are not acceptable.
- ❌ **No auto-shutdown.** Same reason.
- ❌ **No bundled "free VPN."** Free VPNs frequently log and sell traffic. Bring
  your own endpoint, or don't use the feature.
- ❌ **No shell-history or log wiping.** That is not a security feature. It is an
  anti-forensic one.
- ❌ **No offensive capability.** Not now, not in a later version.
- ❌ **No telemetry, analytics, or phone-home.** SHADE makes no network
  connections of its own. Ever.

---

## Why it's open source

SHADE asks for `sudo`. It launches sandboxes, kills processes, and controls your
VPN. A tool with that much reach has exactly one legitimate basis for trust:
**you can read what it does.**

Closed-source security software asks you to accept its behavior on faith. That is
the same faith-based posture as rolling your own cryptography instead of using
peer-reviewed standards, and it fails for the same reason. Every tool SHADE wraps
— Firejail, WireGuard, LUKS, ClamAV — is open for exactly this reason. SHADE
would be a hypocrite to be otherwise.

There is also no secret here worth keeping. SHADE's value is its *judgment* —
what it refuses to do, and how honestly it reports — not any algorithm. Read it.
It's one file. That's the point.

---

## Roadmap

Under consideration, roughly in order:

- [ ] **Config file** (`~/.config/shade/config.toml`) so TUNNEL and SCAN remember
      your paths.
- [ ] **WATCHTOWER as a background monitor** — a daemon that alerts on camera/mic
      access rather than only checking on demand. Still alert-only. Still no
      auto-kill.
- [ ] **TRAPBOX profile management** — inspect and diff Firejail profiles from the
      menu; warn when an app has *no* profile and is therefore only loosely
      confined.
- [ ] **Flatpak integration in TRAPBOX** — surface Flatseal-style permissions so
      you can revoke home access without leaving the console.
- [ ] **STATUS: Secure Boot / UEFI password detection** where readable from the OS.
- [ ] **`--json` mode** so STATUS can be scripted or run from cron.

Explicitly *not* on the roadmap: anything on the refusal list above.

---

## Contributing

Contributions are welcome, with one hard rule:

> **No feature may be more dangerous to the user than the threat it defends
> against.**

Pull requests adding destructive automation, offensive capability, telemetry,
obfuscation, or custom cryptography will be declined regardless of how well
they're implemented. Everything else — better profiles, more honest reporting,
cleaner UX, more platforms, bug fixes — is very welcome.

Reporting a security issue in SHADE itself? Open an issue describing the impact;
if it's sensitive, say so and we'll arrange a private channel.

---

## License

Licensed under the **GNU General Public License v3.0**.

You may use, study, modify, and redistribute SHADE. If you distribute a modified
version, **it must also be open source under the same license.** This keeps SHADE
and everything built from it auditable — which, for a security tool, is the
entire point.

See [LICENSE](LICENSE) for the full text.

---

## Acknowledgements

SHADE is a thin layer of judgment on top of other people's excellent work. The
real credit belongs to the maintainers of **Firejail**, **bubblewrap**,
**WireGuard**, **cryptsetup/LUKS**, **ClamAV**, and the wider Linux security
community. The good parts of this tool are theirs. The opinions are mine.

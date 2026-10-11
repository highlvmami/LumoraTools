<div align="center">

<img src="assets/logo.png" alt="LumoraTools" width="96">

# LumoraTools

**14 local Windows tools in one window: file organizing, search, cleanup, system monitoring, tasks and more. A single `.exe` with automatic updates.**

**[Download →](../../releases/latest)**

[Türkçe](README.md) · English

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/customtkinter-UI-1f6feb" alt="customtkinter">
  <img src="https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite&logoColor=white" alt="SQLite FTS5">
  <img src="https://img.shields.io/badge/PyInstaller-single%20exe-2b2b2b" alt="PyInstaller">
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/pytest-330%20tests-0A9EDC?logo=pytest&logoColor=white" alt="pytest">
</p>

</div>

A desktop toolkit made of small, useful tools. Pick a tool from the menu on the left; they all run in the same window with the same theme. Everything is local: no account, no cloud, your data stays on this computer. The UI is written in Python with customtkinter, the app ships as a single `.exe` and updates itself from GitHub Releases on startup.

> The app is not code-signed, so Windows SmartScreen may show a warning the first time you run it. The interface is in Turkish.

## Screenshots

<p align="center">
  <img src="docs/screenshots/ana-sayfa.jpg" alt="Home: tools grouped by category" width="100%">
</p>

<p align="center">
  <img src="docs/screenshots/dosya-duzenleyici.jpg" alt="File Organizer: preview of what moves where" width="49%">
  <img src="docs/screenshots/boyut-analizcisi.jpg" alt="Folder Size Analyzer" width="49%">
</p>

<p align="center">
  <img src="docs/screenshots/yapilacaklar.jpg" alt="To-do list" width="49%">
  <img src="docs/screenshots/sistem-bilgisi.jpg" alt="System Info" width="49%">
</p>

<p align="center">
  <img src="docs/screenshots/ayarlar.jpg" alt="Settings: 12 themes and menu layout" width="49%">
  <img src="docs/screenshots/rehberler.jpg" alt="Guides" width="49%">
</p>

<p align="center">
  <img src="docs/screenshots/tema-gun-batimi.jpg" alt="Sunset theme" width="49%">
  <img src="docs/screenshots/tema-gunduz.jpg" alt="Light theme" width="49%">
</p>

<p align="center"><sub>Home · File Organizer · Folder Size Analyzer · To-do · System Info · Settings · Guides · Sunset and Light themes. Screenshots use sample data.</sub></p>

## Tools

The menu is split into four collapsible categories; you can switch back to a flat list in Settings.

| Category | Tools |
|---|---|
| 📁 **Files** | Local Search · File Organizer · Folder Size Analyzer · Screenshots |
| 🧹 **Maintenance** | System Cleaner · Startup Programs · Uninstaller · Battery & Disk Health |
| 🖥 **System & network** | System Info · Process Manager · Network Tools |
| ✍ **Productivity** | Clipboard History · To-do · Time Tracker |

### Files
- **🔎 Local Search:** searches the *contents* of files in the folders you choose, instantly (SQLite FTS5). Text, code, `.docx` and `.pdf` are indexed; unchanged files are not re-read. Matches are highlighted and search ignores Turkish diacritics.
- **📁 File Organizer:** sorts a folder (e.g. Downloads) into subfolders by extension, by date, or both; an "as is" mode lists the folder tree. You preview first: you see where every file will go and select files individually or in bulk. Nothing is deleted, files are only moved; a name clash becomes `name (1).ext` and every run can be undone with **Undo**. The **Watch** tab files new arrivals automatically (it leaves in-progress downloads alone).
- **📊 Folder Size Analyzer:** shows what takes the most disk space as bars; click a bar to drill into the folder. The "Largest files" tab ranks the biggest files in the whole tree. It never deletes anything.
- **🖼 Screenshots:** files your screenshots folder into `Year\Month` or `Year\Month\Day`, places new ones automatically. Search by name, note, folder and date; narrow with a date filter; preview and add notes. Ctrl/Shift multi-select to delete (deleted files go to the Recycle Bin).

### Maintenance
- **🧹 System Cleaner:** lists temp files, crash dumps, partial downloads, browser/pip caches and the Recycle Bin with sizes; cleans only what you tick. It touches only defined folders, skips temp files newer than a day and links (junctions/symlinks), and moves partial downloads to the Recycle Bin instead of deleting them. The confirmation dialog spells out exactly what will be permanently deleted.
- **🚀 Startup Programs:** lists programs that run at Windows startup (registry and Startup folders); turn them off and on without deleting them (the StartupApproved flag Task Manager uses).
- **📦 Uninstaller:** lists installed programs with size and install date; removal is done by the program's **own uninstaller**, the tool deletes nothing itself.
- **🔋 Battery & Disk Health:** battery wear (capacity ratio, cycle count) and disk health status. Detailed SMART data needs administrator rights.

### System & network
- **💻 System Info:** CPU, memory, disk, network speed and battery with live charts; "Copy summary" gives a shareable summary without computer or user name.
- **📈 Process Manager:** processes by memory/CPU, grouping by program, guarded termination: critical Windows processes and the app itself cannot be killed.
- **🌐 Network Tools:** active connections and listening ports (and which program), ping, DNS lookup, single `host:port` check. No port scanning; inputs are validated.

### Productivity
- **📋 Clipboard History:** keeps copied text, images and files; search, pin, filter by date, double-click to copy back. The recording switch pauses capture (turn it off before copying a password).
- **✅ To-do:** due dates, priority, filters (Open / Today / Overdue / Done) and search.
- **⏱ Time Tracker:** shows how much time you spend in which program, per day. **Off by default**; only the program name and duration are stored, never window titles, addresses or keystrokes.

### The app itself
- **12 themes:** Night, Day, Ocean, Forest, Sunset, Coffee, Nord, Charcoal, AMOLED, Lavender, Candy, Paper, plus "System" which follows Windows. Contrast ratios of every theme are verified by tests.
- **Menu layout:** drag tools to reorder, hide with a switch (a hidden tool's background work stops too), group by category or use a flat list.
- **Guides:** a short how-to for every tool. **Contact:** opens a pre-filled GitHub page for requests, bugs and feedback; nothing is sent until you press send there.
- **What's new:** shown on the first launch after an update.

## Install

Download `AracMerkezi.exe` from [Releases](../../releases/latest) and run it. No installation needed.

The app checks for a new version on startup and updates itself (can be turned off in Settings). Updates are downloaded over https only and are not applied unless the SHA-256 digest matches. Data lives in `~/.aracmerkezi` (override with the `ARACMERKEZI_HOME` environment variable).

## Development

```bash
py -m pip install -e .[dev]
py -m aracmerkezi          # run the app
py -m pytest               # tests
py build.py                # dist/AracMerkezi.exe + dist/manifest.json
```

Some tests open real windows, so windows may flash on screen while they run.

New release: bump `__version__` in `src/aracmerkezi/__init__.py`, add notes to `changelog.py`, run `py build.py`, and attach the two files in `dist/` to a new GitHub release.

## Project layout

```
src/aracmerkezi/
  app.py             Main window: sidebar, categories, settings, update banner
  registry.py        Tool registry (ToolInfo, Guide, categories) and discovery
  themes.py, ui.py   12 themes and shared UI pieces
  updater.py         Safe updates from GitHub Releases
  changelog.py       "What's new" notes
  tools/             Each tool in its own package: organizer, search, diskusage, screenshots,
                     cleaner, startup, uninstall, sysinfo, processes, network, health,
                     clipboard, todo, timetrack
src/duzenle/         File organizing engine (planning, moving, undo)
tests/               330 tests
```

## Adding a tool

1. Create a package under `src/aracmerkezi/tools/`; in `__init__.py` define a `GUIDE` and `TOOL = ToolInfo(...)` (pick the menu category with `category`).
2. Hook up the page with `build=lambda parent, hub: PageClass(parent, hub)`; give `start`/`stop` if it needs background work.
3. Add the package name to `BUILTIN_TOOLS` in `registry.py` (needed for the single-file `.exe` build).
4. Write tests and add a note to `changelog.py`.

## Feedback

Use the in-app **Contact** page or the [Issues](../../issues) section for ideas, bug reports and feedback.

If you like the project, don't forget to leave a ⭐!

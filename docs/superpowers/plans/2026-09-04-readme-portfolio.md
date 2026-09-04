# README Portfolio Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current operational README with a concise PT-BR portfolio presentation that remains sufficient to install, configure, and test SessionBridge.

**Architecture:** Documentation-only change. `README.md` remains the public entry point and derives every command, tool name, and security statement from the existing implementation.

**Tech Stack:** GitHub Flavored Markdown, Python, MCP, Playwright, Windows PowerShell.

---

### Task 1: Rewrite Public README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Record current documentation problems**

Run:

```powershell
rtk rg -n "C:\\Users\\roni9|Em 2026|Publicação básica no GitHub|git remote add" README.md
```

Expected: matches for personal path, dated smoke result, and obsolete publication tutorial.

- [ ] **Step 2: Replace README with portfolio structure**

Write these sections in this exact order:

```text
# SessionBridge
one-sentence value proposition
architecture diagram
## Recursos
## Como funciona
## Início rápido
## Configuração no Codex
## Ferramentas MCP
## Testes
## Segurança e limitações
## Status
```

Content requirements:

- PT-BR prose; English commands and identifiers.
- Diagram: `Codex / MCP Client -> SessionBridge -> Playwright / CDP -> Chrome` with human interaction returning to the same Chrome session.
- Generic `git clone`, virtual environment, editable install, pytest, and smoke commands.
- Codex TOML uses `C:\\caminho\\para\\sessionbridge` rather than a personal path.
- List exactly `open_browser`, `get_browser_status`, `wait_for_human`, `continue_session`, `get_current_page`, and `close_browser`.
- State CDP loopback, dedicated profile, heuristic detection, bounded page text, and no CAPTCHA bypass.
- State MVP status without dated local execution output.
- Exclude Git publication tutorial.

- [ ] **Step 3: Verify content constraints**

Run:

```powershell
rtk rg -n "C:\\Users\\roni9|Em 2026|Publicação básica no GitHub|git remote add" README.md
```

Expected: no matches.

Run:

```powershell
rtk rg -n "open_browser|get_browser_status|wait_for_human|continue_session|get_current_page|close_browser|127\.0\.0\.1|\.chrome_profile" README.md
```

Expected: all six tools and both security invariants present.

- [ ] **Step 4: Verify project remains healthy**

Run:

```powershell
rtk python -m pytest -q
```

Expected: 87 tests pass; external `pytest-asyncio` warnings on Python 3.14 are allowed.

- [ ] **Step 5: Commit documentation change**

```powershell
git add README.md
git commit -m "docs: improve project README"
```

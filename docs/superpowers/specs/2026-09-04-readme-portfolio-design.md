# README Portfolio Design

## Objective

Replace the current long operational README with a concise Portuguese presentation suitable for GitHub portfolio visitors and developers evaluating the project.

## Audience

- Recruiters and technical reviewers who need to understand the project quickly.
- Developers who want to install and test the MCP server on Windows.

## Structure

1. Project title and one-sentence value proposition.
2. Compact architecture diagram: MCP client to SessionBridge to Chrome.
3. Key capabilities.
4. Human-in-the-loop workflow.
5. Windows quick start.
6. Generic Codex MCP configuration with a project-path placeholder.
7. Exact six-tool public surface.
8. Automated and real smoke-test commands.
9. Essential security constraints and MVP limitations.

## Content Rules

- Keep PT-BR explanation and English identifiers.
- Use short sections and scan-friendly lists.
- Do not expose personal filesystem paths.
- Do not include dated local smoke output.
- Do not include Git publication instructions in an already published repository.
- Do not claim CAPTCHA bypass or automatic challenge solving.
- Preserve accurate setup, tool names, CDP loopback behavior, dedicated profile behavior, and Python version guidance.

## Validation

- Compare documented commands and tool names with current files.
- Search README for personal path fragments and removed historical content.
- Render or inspect Markdown structure.
- Run existing automated tests to confirm documentation-only change does not coincide with broken code.

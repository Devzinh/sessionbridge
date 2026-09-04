# SessionBridge

Servidor MCP local para automação de navegador com intervenção humana e sessão persistente.

O SessionBridge conecta clientes compatíveis com MCP a uma janela visível do Chrome. Quando uma página exige login, CAPTCHA ou outra ação manual, a automação pausa, preserva a sessão e continua depois que o usuário conclui a etapa.

```text
Codex / MCP Client
        │
        │ MCP (stdio)
        ▼
   SessionBridge
        │
        │ Playwright + CDP
        ▼
 Chrome dedicado ◄──── interação humana
```

## Recursos

- Sessão persistente em perfil dedicado do Chrome.
- Conexão local via Chrome DevTools Protocol (CDP).
- Detecção heurística de Cloudflare, Turnstile e CAPTCHA.
- Espera automática pela conclusão da interação humana.
- Retomada do workflow na mesma página e sessão.
- Extração limitada de título, URL e texto visível.
- Interface independente do modelo ou cliente de IA.

## Como funciona

1. Cliente MCP chama `open_browser` com uma URL.
2. SessionBridge abre ou reutiliza Chrome dedicado.
3. Página é classificada como pronta ou dependente de interação manual.
4. Usuário resolve etapa diretamente na janela do navegador.
5. `wait_for_human` detecta mudança; workflow pode continuar.
6. `close_browser` desconecta automação sem encerrar Chrome.

Cookies, abas e autenticação permanecem no perfil dedicado entre execuções.

## Início rápido

### Requisitos

- Windows
- Python 3.11 a 3.13
- Google Chrome

### Instalação

```powershell
git clone https://github.com/Devzinh/sessionbridge.git
cd sessionbridge

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

### Executar servidor

```powershell
.\.venv\Scripts\python.exe server.py
```

Servidor usa transporte MCP `stdio`; terminal permanece aguardando cliente MCP.

## Configuração no Codex

Adicione servidor ao arquivo `%USERPROFILE%\.codex\config.toml`:

```toml
[mcp_servers.sessionbridge]
command = "C:\\path\\to\\sessionbridge\\.venv\\Scripts\\python.exe"
args = ["C:\\path\\to\\sessionbridge\\server.py"]
```

Substitua `C:\path\to\sessionbridge` pelo caminho real do clone e reinicie Codex.

Exemplo de solicitação:

> Abra o site, obtenha dados da página e aguarde caso seja necessária interação manual.

## Ferramentas MCP

| Ferramenta | Função |
| --- | --- |
| `open_browser(url)` | Abre URL HTTP(S) e retorna estado inicial. |
| `get_browser_status()` | Consulta conexão, página e necessidade de interação. |
| `wait_for_human(timeout_seconds)` | Aguarda página ficar pronta ou atingir timeout. |
| `continue_session()` | Verifica imediatamente se sessão pode continuar. |
| `get_current_page(max_length)` | Retorna título, URL e texto limitado da página. |
| `close_browser()` | Desconecta Playwright sem fechar Chrome. |

## Testes

Suíte automatizada não abre navegador:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Smoke test abre Chrome e acessa `https://example.com`:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

## Segurança e limitações

- CDP escuta somente em `127.0.0.1:9222`.
- Navegador usa perfil isolado em `.chrome_profile`.
- Endpoint CDP desconhecido é recusado para evitar acesso ao perfil errado.
- SessionBridge não resolve nem contorna CAPTCHA ou mecanismos anti-bot.
- Detecção de interação manual é heurística e pode não reconhecer prompts específicos.
- `get_current_page` envia texto da página ao cliente MCP; evite conteúdo sensível.
- MVP não oferece clique, preenchimento, screenshot ou JavaScript arbitrário como ferramentas.

## Status

MVP funcional para Windows, com integração MCP via `stdio`, sessão persistente e handoff humano pelo Chrome.

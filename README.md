# SessionBridge

SessionBridge é um servidor MCP local para automação assistida de uma janela visível do Chrome. Ele mantém uma sessão dedicada entre execuções, identifica estados que provavelmente exigem ação humana e permite continuar a automação depois dessa intervenção.

## Arquitetura

- `server.py`: interface MCP via `stdio` e registro das seis ferramentas.
- `tools/browser.py`: adaptadores MCP para a sessão compartilhada.
- `browser/session.py`: coordenação de navegação, estado, conteúdo e desconexão.
- `browser/launcher.py`: inicialização do navegador e perfil persistente.
- `browser/cdp.py`: conexão Playwright pelo Chrome DevTools Protocol (CDP).
- `browser/state.py`: classificação heurística da página.

O Playwright se conecta a uma instalação local do Chrome pelo CDP; não é necessário baixar um navegador com `playwright install`.

## Pré-requisitos no Windows

- Python 3.11 a 3.13 (faixa recomendada).
- Google Chrome instalado em um dos caminhos usuais do Windows.

No PowerShell, a partir da raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

Execute os testes automatizados, que usam doubles e não abrem o Chrome:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Execute o smoke test real (abre ou reutiliza o Chrome visível):

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

O smoke acessa `https://example.com`, exige uma página conectada e pronta, lê no máximo 500 caracteres e imprime somente um resumo seguro, sem cookies nem o texto da página.

Em 2026-09-04, um smoke real neste ambiente retornou `connected: true`, `ready: true`, URL `https://example.com/` e `content_length: 128`. Esse resultado comprova esta execução local, não todos os ambientes.

## Iniciar o servidor MCP

Para iniciar diretamente pelo transporte `stdio`:

```powershell
.\.venv\Scripts\python.exe server.py
```

O processo usa entrada e saída padrão para conversar com o cliente MCP; não é um servidor HTTP interativo.

## Configurar no Codex

Edite `%USERPROFILE%\.codex\config.toml` e use caminhos absolutos. Em strings TOML com aspas duplas, cada barra invertida precisa ser escapada:

```toml
[mcp_servers.sessionbridge]
command = "C:\\Users\\roni9\\Desktop\\Curso Da Sarah\\.venv\\Scripts\\python.exe"
args = ["C:\\Users\\roni9\\Desktop\\Curso Da Sarah\\server.py"]
```

Reinicie o Codex após salvar a configuração. Durante uma etapa manual, mantenha a janela dedicada do Chrome aberta.

## Ferramentas

O servidor expõe somente estas seis ferramentas:

- `open_browser(url)`: abre uma URL HTTP(S) absoluta e informa o estado inicial. Exemplo: `open_browser("https://example.com")`.
- `get_browser_status()`: consulta URL, título e estado da página atual. Exemplo: `get_browser_status()`.
- `wait_for_human(timeout_seconds)`: aguarda a conclusão de uma interação manual. Exemplo: `wait_for_human(120)`.
- `continue_session()`: verifica uma vez se a automação já pode continuar. Exemplo: `continue_session()`.
- `get_current_page(max_length)`: retorna URL, título e texto legível limitado. Exemplo: `get_current_page(2000)`.
- `close_browser()`: desconecta a automação. Exemplo: `close_browser()`.

## Fluxo com intervenção humana

1. Chame `open_browser` com uma URL válida.
2. Se `manual_interaction_required` for `true`, resolva CAPTCHA, login ou confirmação diretamente na janela visível.
3. Use `wait_for_human` para aguardar ou `continue_session` para verificar uma vez.
4. Quando `connected` e `ready` forem `true`, use `get_current_page` conforme necessário.
5. Ao terminar, chame `close_browser`.

## Segurança e limitações

- O navegador usa o perfil dedicado `.chrome_profile`; não use esse diretório como seu perfil principal.
- O CDP é exposto somente em `127.0.0.1`, na porta padrão `9222`. Ainda assim, qualquer processo local com acesso à porta pode controlar essa sessão.
- SessionBridge não resolve nem contorna CAPTCHA ou mecanismos anti-bot.
- A detecção de desafios é heurística. Um login desconhecido ou prompt específico do site pode exigir avaliação do chamador, inclusive pelo resultado limitado de `get_current_page`.
- `get_current_page` devolve texto da página ao cliente MCP; solicite apenas o tamanho necessário e evite páginas com dados sensíveis.
- `close_browser` desconecta o Playwright, mas não fecha o Chrome. Abas, cookies e login permanecem no perfil dedicado.
- O MVP controla uma sessão por processo e não oferece cliques, preenchimento de campos, screenshots nem execução arbitrária de JavaScript como ferramentas MCP.

## Solução de problemas

**A porta 9222 já está em uso:** feche o processo que ocupa a porta ou confirme que ele é a instância dedicada do Chrome iniciada pelo SessionBridge. Não conecte o projeto a um navegador desconhecido.

**Chrome não foi encontrado:** instale o Google Chrome em um caminho padrão do Windows. O launcher também reconhece alguns caminhos padrão do Brave e Edge, mas Chrome é o navegador recomendado.

**Chrome encerra ao iniciar ou o perfil está bloqueado:** feche outras instâncias que estejam usando `.chrome_profile` e execute novamente. Não abra o mesmo diretório de perfil com dois processos independentes.

**A conexão CDP falha:** confirme que `http://127.0.0.1:9222/json/version` responde na máquina local e que firewall ou política corporativa não bloqueiam a porta loopback.

## Publicação básica no GitHub

Antes de publicar, revise arquivos locais e dados do perfil. O `.gitignore` já exclui `.venv`, caches, screenshots e `.chrome_profile`. Em seguida, crie um repositório no GitHub, inicialize o Git localmente, adicione os arquivos do projeto, faça o primeiro commit e configure o remoto. Este projeto não declara licença nem pipeline de CI; adicione-os somente após escolher conscientemente as políticas adequadas.

```powershell
git init
git add .
git commit -m "Initial SessionBridge MVP"
git branch -M main
git remote add origin <URL_DO_REPOSITORIO>
git push -u origin main
```

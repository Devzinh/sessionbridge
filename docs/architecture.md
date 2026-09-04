# Arquitetura

SessionBridge separa interface MCP, coordenação de sessão e integração com navegador.

```text
Cliente MCP
    │ stdio
    ▼
server.py → tools/browser.py → browser/session.py
                                  ├── browser/cdp.py
                                  ├── browser/launcher.py
                                  └── browser/state.py
```

## Responsabilidades

- `server.py`: registra seis ferramentas no FastMCP e inicia `stdio`.
- `tools/browser.py`: adapta chamadas MCP à instância global de sessão.
- `browser/session.py`: valida URL, coordena navegação, espera humana, leitura e conexão.
- `browser/cdp.py`: conecta Playwright ao CDP e seleciona ou cria página.
- `browser/launcher.py`: encontra navegador, inicia perfil dedicado e confirma endpoint.
- `browser/state.py`: classifica página por título, seletores visíveis e texto.

## Invariantes

### Uma sessão por processo

Ferramentas compartilham singleton `SessionBridge`. Página e conexão continuam disponíveis entre chamadas do mesmo processo MCP.

### Perfil dedicado

Navegador usa `.chrome_profile`, separado do perfil padrão. Cookies, abas e autenticação persistem nesse diretório.

### Endpoint local identificado

CDP usa `127.0.0.1:9222`. Marcador no perfil associa porta ao caminho WebSocket do navegador iniciado pelo SessionBridge. Endpoint divergente é recusado.

### Handoff, não bypass

Classificador sinaliza provável bloqueio. Pessoa interage na janela real; SessionBridge aguarda e reavalia estado. Nenhum mecanismo resolve CAPTCHA automaticamente.

### Leitura limitada

`get_current_page` devolve título, URL e texto visível. Limite aceito: 1 a 100.000 caracteres; padrão: 4.000.

## Testes

Testes automatizados injetam páginas, elementos e conexões simuladas. `scripts/smoke_test.py` depende de navegador local.

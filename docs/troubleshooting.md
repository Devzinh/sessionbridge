# Solução de problemas

## Navegador não foi encontrado

SessionBridge procura Google Chrome, Brave e Microsoft Edge em caminhos comuns do Windows. Confirme instalação padrão de um deles.

## Porta 9222 já está em uso

SessionBridge recusa endpoint CDP que não corresponda ao perfil dedicado. Feche processo que ocupa porta ou navegador dedicado antigo.

## Chrome abre, mas conexão não fica pronta

Verifique se software de segurança bloqueia conexão local em `127.0.0.1:9222`. Feche janela dedicada e execute servidor novamente. Não aponte SessionBridge ao perfil principal.

## Interação humana não é detectada

Detecção usa títulos, seletores e textos conhecidos. Conclua etapa na janela e chame `continue_session()` para reavaliar estado.

## `wait_for_human` termina com timeout

Timeout não fecha navegador nem apaga perfil. Conclua interação e chame `continue_session()`, ou repita espera com prazo maior que zero.

## Conteúdo retornado está incompleto

`get_current_page` retorna texto visível limitado. Aumente `max_length` até 100.000. Conteúdo em iframe, canvas, mídia ou componente sem texto pode não aparecer.

## Validação

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

Segundo comando depende de navegador instalado e abre `https://example.com`.

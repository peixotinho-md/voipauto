# VoIP Screenshots

Automação em Python (Playwright) para logar em múltiplos painéis administrativos de PBX/VoIP — **Issabel** e **OpenSNEP** — e capturar screenshots padronizados do dashboard de cada servidor.

## O que ele faz

- Loga automaticamente em cada servidor configurado no `sites.json`
- Trata popups específicos de cada painel (modal "Registrar" do Issabel, tour de onboarding do OpenSNEP)
- Executa ações extras quando necessário (ex: clicar num painel lateral pra revelar informações de CPU/memória/disco antes do print)
- Esconde avisos flutuantes (ex: "License"/"Monitor" do Issabel) que atrapalham o print
- Salva o screenshot com nome padronizado: `dd-mm-aaaa_nome-do-servidor.png`

## Requisitos

- Python 3.9+
- [Playwright](https://playwright.dev/python/)

## Instalação

```bash
pip install playwright
playwright install chromium
```

## Configuração

1. Copie o modelo de configuração:
   ```bash
   cp sites.example.json sites.json
   ```
2. Edite `sites.json` com os dados reais de cada servidor (URL, usuário, senha).

   ⚠️ **`sites.json` contém credenciais e nunca deve ser commitado** — ele já está no `.gitignore`.

### Campos disponíveis por servidor

| Campo | Obrigatório | Descrição |
|---|---|---|
| `name` | sim | Nome do servidor (usado no nome do arquivo do screenshot) |
| `url` | sim | Endereço do painel |
| `username` / `password` | sim | Credenciais de login |
| `selectors` | sim | Seletores CSS dos campos de usuário, senha e botão de login |
| `screenshot_path` | sim | Pasta/arquivo onde salvar (o nome do arquivo é gerado automaticamente) |
| `viewport` | não | Resolução da janela, ex: `{"width": 1920, "height": 953}` |
| `wait_after_login` | não | Tempo de espera (ms) após o login |
| `wait_for_network` | não | Aguardar rede ociosa (`networkidle`) |
| `wait_for_selector` | não | Seletor CSS que indica que a página carregou |
| `post_login_click` | não | Seletor CSS de um elemento para clicar/hover após o login |
| `post_login_click_wait` | não | Tempo de espera (ms) após o clique pós-login |
| `post_login_click_settle_delay` | não | Delay fixo (ms) logo após o clique, antes de outras verificações |
| `post_login_click_wait_for_selector` | não | Seletor que confirma que o conteúdo pós-clique carregou |
| `hide_fixed_notifications` | não | `false` para não esconder elementos fixos (útil quando o próprio conteúdo desejado é `position: fixed`) |
| `full_page_screenshot` | não | `false` evita o `full_page`, que pode fechar menus abertos via hover |

Veja `sites.example.json` para um exemplo completo de Issabel e OpenSNEP.

## Uso

```bash
python3 screenshot.py
```

### Modo de depuração

Rodar com o navegador visível, mais devagar, e filtrando por um único servidor:

```bash
HEADLESS=false SLOWMO=500 SITE=nome-do-servidor python3 screenshot.py
```

| Variável | Descrição |
|---|---|
| `HEADLESS=false` | Abre o navegador visível em vez de rodar em segundo plano |
| `SLOWMO=500` | Adiciona um delay (ms) entre cada ação, facilita acompanhar |
| `SITE=nome` | Roda apenas o servidor com esse `name` no `sites.json` |

## Estrutura

```
.
├── screenshot.py          # Script principal (Python/Playwright)
├── sites.example.json     # Modelo de configuração (sem dados sensíveis)
├── sites.json             # Configuração real (git-ignored)
└── screenshots/           # Screenshots gerados (git-ignored)
```

## Segurança

- `sites.json` contém credenciais em texto puro e está no `.gitignore` — nunca remova essa entrada.
- Se em algum momento `sites.json` for commitado por engano, troque as senhas dos servidores afetados, já que o histórico do git preserva o conteúdo mesmo após remoção.

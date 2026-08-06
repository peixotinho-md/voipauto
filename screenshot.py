import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "sites.json"
SCREENSHOTS_DIR = SCRIPT_DIR / "screenshots"


async def setup_dialog_handler(page):
    """Configura handler para dialogs JavaScript (alert, confirm, prompt)"""
    async def handle_dialog(dialog):
        print(f"  [dialog] {dialog.type}: {dialog.message}")
        await dialog.dismiss()
    page.on("dialog", handle_dialog)


async def dismiss_popups(page):
    """Detecta o popup do Issabel e dá F5 (máximo 1 vez por carga de página)"""
    # Evita loop: só dá F5 uma vez por navegação
    if getattr(page, "_f5_done", False):
        return False
        
    try:
        issabel_modal = page.locator(".neo-modal-issabel-popup-content:visible").first
        if await issabel_modal.is_visible(timeout=1000):
            print("  [popup] Modal Issabel detectado, dando F5...")
            await page.keyboard.press("F5")
            page._f5_done = True  # Marca que já fez F5 nesta página
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            return True
    except Exception as e:
        print(f"  [popup] Erro: {e}")
    return False


async def dismiss_register_modal(page):
    """Detecta e fecha o popup 'Registrar' (Sign Up / Login) que aparece no painel."""
    closed = False
    try:
        # Localiza o modal pelo texto "Registrar" (título do popup)
        modal = page.locator("text=Registrar").first
        if not await modal.is_visible(timeout=1000):
            return False

        print("  [popup] Modal 'Registrar' detectado, tentando fechar...")

        # Tenta vários seletores comuns de botão de fechar (X)
        close_selectors = [
            "button.close",
            "[aria-label='Close']",
            "[aria-label='close']",
            ".modal-header .close",
            ".ui-dialog-titlebar-close",
            "button:has-text('×')",
            "span:has-text('×')",
            ".close-icon",
            "[class*='close']:visible",
        ]

        for sel in close_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=800):
                    await btn.click(timeout=2000)
                    print(f"  [popup] Fechado via seletor: {sel}")
                    closed = True
                    break
            except Exception:
                continue

        # Fallback: tecla Escape
        if not closed:
            await page.keyboard.press("Escape")
            print("  [popup] Tentativa de fechar via tecla Escape")
            closed = True

        # Confirma que sumiu; se não sumiu, tenta clicar fora do modal (no overlay)
        try:
            if await modal.is_visible(timeout=1000):
                await page.mouse.click(5, 5)  # clica em um canto fora do modal
                print("  [popup] Tentativa de fechar clicando fora do modal")
        except Exception:
            pass

        await page.wait_for_timeout(500)
        return closed

    except Exception as e:
        print(f"  [popup] Erro ao tentar fechar modal 'Registrar': {e}")
        return False


async def dismiss_intro_tour(page):
    """Fecha tours/tutoriais de onboarding (ex: intro.js) clicando em 'Skip'/'Pular'"""
    closed_any = False
    try:
        skip_selectors = [
            ".introjs-skipbutton",
            "button:has-text('Skip')",
            "a:has-text('Skip')",
            "button:has-text('Pular')",
            "a:has-text('Pular')",
            ".introjs-overlay ~ .introjs-tooltip .introjs-skipbutton",
        ]

        for sel in skip_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=800):
                    await btn.click(timeout=2000)
                    print(f"  [tour] Tutorial fechado via: {sel}")
                    closed_any = True
                    break
            except Exception:
                continue

        # Fallback: Escape (intro.js geralmente responde a Escape)
        if not closed_any:
            try:
                tooltip = page.locator(".introjs-tooltip").first
                if await tooltip.is_visible(timeout=800):
                    await page.keyboard.press("Escape")
                    print("  [tour] Tentativa de fechar tour via Escape")
                    closed_any = True
            except Exception:
                pass

        if closed_any:
            await page.wait_for_timeout(500)

        return closed_any
    except Exception as e:
        print(f"  [tour] Erro ao tentar fechar tour: {e}")
        return False


async def hide_ui_chrome(page):
    """Esconde os avisos fixos (License/Monitor) antes do screenshot, mantendo a sidebar"""
    try:
        # Esconde qualquer elemento fixo perto do topo (avisos flutuantes tipo
        # "Issabel Network - License" / "Monitor"), sem depender de saber a classe exata
        hidden_count = await page.evaluate("""
            () => {
                let count = 0;
                document.querySelectorAll('body *').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    if (style.position === 'fixed' && rect.top < 200 && rect.width > 50 && rect.height > 20) {
                        el.style.setProperty('display', 'none', 'important');
                        count++;
                    }
                });
                return count;
            }
        """)

        await page.wait_for_timeout(300)
        print(f"  [ui] {hidden_count} aviso(s) fixo(s) escondido(s)")
    except Exception as e:
        print(f"  [ui] Erro ao ocultar avisos: {e}")


async def wait_for_page_ready(page, site):
    """Aguarda a página carregar completamente"""
    wait_time = site.get("wait_after_login", 5000)
    wait_for_selector = site.get("wait_for_selector")
    wait_for_network = site.get("wait_for_network", True)

    if wait_for_network:
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
            print("  [wait] networkidle atingido")
        except:
            print("  [wait] timeout networkidle, continuando...")

    if wait_for_selector:
        try:
            await page.wait_for_selector(wait_for_selector, timeout=30000)
            print(f"  [wait] Seletor '{wait_for_selector}' encontrado")
        except:
            print(f"  [wait] Seletor '{wait_for_selector}' não encontrado")

    # Verifica popups periodicamente durante a espera
    for _ in range(wait_time // 1000):
        await page.wait_for_timeout(1000)
        await dismiss_popups(page)
        await dismiss_register_modal(page)
        await dismiss_intro_tour(page)

    print(f"  [wait] Aguardados {wait_time}ms extras")


async def login_and_screenshot(site, browser):
    viewport = site.get("viewport", {"width": 1280, "height": 720})
    page = await browser.new_page(viewport=viewport)
    name = site["name"]

    try:
        # Handler para dialogs JS (alert, confirm, prompt)
        await setup_dialog_handler(page)

        print(f"[{name}] Acessando {site['url']}...")
        await page.goto(site["url"], wait_until="domcontentloaded", timeout=60000)

        # Verifica popups após carregar a página de login
        await dismiss_popups(page)
        await dismiss_register_modal(page)
        await dismiss_intro_tour(page)

        print(f"[{name}] Preenchendo credenciais...")
        await page.fill(site["selectors"]["username"], site["username"])
        await page.fill(site["selectors"]["password"], site["password"])

        print(f"[{name}] Clicando em login...")
        page._f5_done = False  # Reseta flag para nova navegação
        await page.click(site["selectors"]["submit"])

        await page.wait_for_load_state("domcontentloaded")

        # Verifica popups após login
        await dismiss_popups(page)
        await dismiss_register_modal(page)
        await dismiss_intro_tour(page)

        # Clique opcional em uma área específica após o login (ex: abrir um painel/relatório)
        post_login_click = site.get("post_login_click")
        post_login_click_coords = site.get("post_login_click_coords")

        if post_login_click or post_login_click_coords:
            try:
                if post_login_click_coords:
                    viewport = page.viewport_size or {"width": 1280, "height": 720}
                    x = viewport["width"] * (post_login_click_coords.get("x_percent", 50) / 100)
                    y = viewport["height"] * (post_login_click_coords.get("y_percent", 50) / 100)
                    print(f"[{name}] Clicando em coordenada relativa: {x:.0f},{y:.0f} "
                          f"({post_login_click_coords.get('x_percent')}%, {post_login_click_coords.get('y_percent')}%)")
                    await page.mouse.click(x, y)
                else:
                    print(f"[{name}] Movendo o mouse fisicamente até: {post_login_click}")
                    box = await page.locator(post_login_click).first.bounding_box()

                    if box:
                        cx = box["x"] + box["width"] / 2
                        cy = box["y"] + box["height"] / 2

                        # Começa de um canto neutro e move em vários passos até o
                        # elemento, simulando um mouse físico real (não "teleporte")
                        await page.mouse.move(0, 0)
                        await page.mouse.move(cx, cy, steps=30)
                        await page.wait_for_timeout(800)  # dwell - tempo parado em cima

                        await page.mouse.down()
                        await page.wait_for_timeout(100)
                        await page.mouse.up()
                        print(f"  [click] Movimento + clique em ({cx:.0f}, {cy:.0f})")
                    else:
                        print(f"  [click] Elemento '{post_login_click}' não encontrado, "
                              f"caindo para hover/click padrão")
                        await page.hover(post_login_click, timeout=15000)
                        await page.wait_for_timeout(500)
                        await page.click(post_login_click, timeout=15000, force=True)

                    # Reforço: dispara os eventos via JS direto no elemento (cobre casos
                    # de handlers jQuery .hover()/.mouseenter() que o clique "físico"
                    # do Playwright às vezes não ativa)
                    try:
                        dispatched = await page.evaluate("""
                            (sel) => {
                                const el = document.querySelector(sel);
                                if (!el) return false;
                                const evts = ['mouseover', 'mouseenter', 'mousedown', 'mouseup', 'click'];
                                for (const type of evts) {
                                    el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                                }
                                return true;
                            }
                        """, post_login_click)
                        print(f"  [click] Eventos JS disparados via dispatchEvent: {dispatched}")
                    except Exception as e:
                        print(f"  [click] Erro ao disparar eventos JS: {e}")

                # Delay fixo logo após o clique, dando tempo da animação/painel abrir
                # antes de qualquer outra verificação (networkidle pode resolver
                # instantaneamente mesmo com o painel ainda abrindo via CSS/JS)
                click_settle_delay = site.get("post_login_click_settle_delay", 5000)
                print(f"  [click] Aguardando {click_settle_delay}ms para o painel abrir...")
                await page.wait_for_timeout(click_settle_delay)

                wait_after_click = site.get("post_login_click_wait", 5000)

                # Espera a navegação/carregamento de rede, se aplicável
                try:
                    await page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    print("  [click] timeout networkidle após clique, continuando...")

                # Espera por um seletor específico que indique que a informação carregou
                post_click_selector = site.get("post_login_click_wait_for_selector")
                if post_click_selector:
                    try:
                        await page.wait_for_selector(post_click_selector, timeout=30000)
                        print(f"  [click] Seletor '{post_click_selector}' encontrado após clique")
                    except Exception:
                        print(f"  [click] Seletor '{post_click_selector}' não encontrado após clique")

                await page.wait_for_timeout(wait_after_click)
                await dismiss_popups(page)
                await dismiss_register_modal(page)
                await dismiss_intro_tour(page)

            except Exception as e:
                target = post_login_click_coords if post_login_click_coords else post_login_click
                print(f"[{name}] Erro ao clicar em '{target}': {e}")

        # Aguarda página pronta
        await wait_for_page_ready(page, site)

        # Verificação final de popups antes do screenshot
        await dismiss_popups(page)
        await dismiss_register_modal(page)
        await dismiss_intro_tour(page)

        # Esconde avisos fixos (License/Monitor) - desligado se o site define
        # "hide_fixed_notifications": false (ex: quando o clique pós-login abre
        # um painel que também é position:fixed e precisa continuar visível)
        if site.get("hide_fixed_notifications", True):
            await hide_ui_chrome(page)

        # Nome do arquivo: dd-mm-aaaa_nome-do-servidor.png
        timestamp = datetime.now().strftime("%d-%m-%Y")
        filename = f"{timestamp}_{name}.png"

        # Usa a pasta definida em screenshot_path (se houver) e troca só o nome do arquivo
        if "screenshot_path" in site:
            screenshot_dir = (SCRIPT_DIR / site["screenshot_path"]).resolve().parent
        else:
            screenshot_dir = SCREENSHOTS_DIR

        screenshot_path = (screenshot_dir / filename).resolve()
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        # full_page=True redimensiona a página internamente pra capturar tudo de
        # uma vez - isso pode disparar um "resize" que fecha menus/painéis abertos
        # via hover. Desative com "full_page_screenshot": false no site quando
        # o conteúdo já cabe na viewport.
        full_page = site.get("full_page_screenshot", True)
        await page.screenshot(path=str(screenshot_path), full_page=full_page)
        print(f"[{name}] Screenshot salvo em: {screenshot_path}")

    except Exception as e:
        print(f"[{name}] Erro: {e}")
    finally:
        await page.close()


async def main():
    if not Path(CONFIG_FILE).exists():
        print(f"Arquivo {CONFIG_FILE} não encontrado!")
        return

    config = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
    Path(SCREENSHOTS_DIR).mkdir(exist_ok=True)

    # Modo visível para debug: HEADLESS=false python3 screenshot.py
    # Opcional: SLOWMO=500 (ms de pausa entre ações, facilita acompanhar)
    headless = os.environ.get("HEADLESS", "true").lower() != "false"
    slow_mo = int(os.environ.get("SLOWMO", "0"))

    if not headless:
        print(">>> Rodando em modo VISÍVEL (headless=False)")
        if slow_mo:
            print(f">>> Slow motion: {slow_mo}ms entre ações")

    # Filtra para rodar só 1 site específico durante debug: SITE=snep1 python3 screenshot.py
    only_site = os.environ.get("SITE")
    sites_to_run = config["sites"]
    if only_site:
        sites_to_run = [s for s in sites_to_run if s["name"] == only_site]
        print(f">>> Rodando apenas o site: {only_site}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=["--ignore-certificate-errors"]
        )
        for site in sites_to_run:
            await login_and_screenshot(site, browser)
        await browser.close()

    print("Todos os sites processados!")


if __name__ == "__main__":
    asyncio.run(main())
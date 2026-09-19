"""Internal `frame://` scheme + New Tab page (theme-aware, modern).

New Tab page cards come from **bookmarks** (user-curated), not history.
"""
from __future__ import annotations

import html as html_mod
from urllib.parse import urlparse

from PyQt6.QtCore import QBuffer, QIODevice, QUrl
from PyQt6.QtWebEngineCore import (
    QWebEngineUrlRequestJob,
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
)

from .core import SCHEME, SEARCH_ENGINES
from .theme import THEMES


def register_scheme() -> None:
    scheme = QWebEngineUrlScheme(SCHEME)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.ViewSourceAllowed
    )
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    QWebEngineUrlScheme.registerScheme(scheme)


# ══════════════════════════════════════════════════════════════════════
#  New Tab page CSS
# ══════════════════════════════════════════════════════════════════════
def _newtab_css(theme: str) -> str:
    c = THEMES.get(theme, THEMES["dark"])
    is_light = theme == "light"

    if is_light:
        page_bg = (
            "radial-gradient(1200px 700px at 50% -20%, #ffffff 0%, "
            f"{c['bg']} 45%, #e4e7ea 100%)"
        )
        card_bg = "rgba(255, 255, 255, 0.72)"
        card_border = "rgba(0, 0, 0, 0.06)"
        card_hover = "#ffffff"
        input_bg = "#ffffff"
        shadow = "0 4px 24px -10px rgba(0, 0, 0, 0.12)"
        glow = "rgba(26, 115, 232, 0.22)"
        accent_2 = "#0d5bcf"
        fav_text = "#ffffff"
    else:
        page_bg = (
            "radial-gradient(1200px 700px at 50% -20%, #2b3a55 0%, "
            "#1a1c20 55%, #0f1012 100%)"
        )
        card_bg = "rgba(255, 255, 255, 0.045)"
        card_border = "rgba(255, 255, 255, 0.08)"
        card_hover = "rgba(255, 255, 255, 0.09)"
        input_bg = "rgba(255, 255, 255, 0.05)"
        shadow = "0 4px 24px -10px rgba(0, 0, 0, 0.55)"
        glow = "rgba(138, 180, 248, 0.32)"
        accent_2 = "#5b8def"
        fav_text = "#17181a"

    return f"""
    :root {{
        --bg: {c['bg']};
        --bg-light: {c['bg_light']};
        --text: {c['text']};
        --muted: {c['muted']};
        --accent: {c['accent']};
        --accent-2: {accent_2};
        --border: {c['border']};
        --card-bg: {card_bg};
        --card-border: {card_border};
        --card-hover: {card_hover};
        --input-bg: {input_bg};
        --shadow: {shadow};
        --glow: {glow};
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    html, body {{ height: 100%; }}

    body {{
        min-height: 100vh;
        background: {page_bg};
        color: var(--text);
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 34px;
        padding: 56px 24px;
        -webkit-font-smoothing: antialiased;
    }}

    .logo {{
        font-size: 56px;
        font-weight: 800;
        letter-spacing: -2.5px;
        color: var(--text);
        animation: fadeDown 0.5s cubic-bezier(0.16, 1, 0.3, 1) backwards;
        user-select: none;
    }}
    .logo .dot {{ color: var(--accent); }}

    form {{
        width: min(640px, 92vw);
        animation: fadeDown 0.55s 0.05s cubic-bezier(0.16, 1, 0.3, 1) backwards;
    }}

    input[type=text] {{
        width: 100%;
        padding: 17px 26px;
        font-size: 15px;
        font-family: inherit;
        border-radius: 30px;
        border: 1px solid var(--border);
        background: var(--input-bg);
        color: var(--text);
        outline: none;
        transition: border-color 0.2s ease,
                    box-shadow 0.2s ease,
                    transform 0.2s ease;
        box-shadow: var(--shadow);
    }}

    input[type=text]::placeholder {{ color: var(--muted); }}

    input[type=text]:focus {{
        border-color: var(--accent);
        box-shadow: 0 0 0 4px var(--glow), var(--shadow);
        transform: translateY(-1px);
    }}

    .grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        width: min(640px, 92vw);
    }}

    @media (max-width: 640px) {{
        .grid {{ grid-template-columns: repeat(2, 1fr); }}
        .logo {{ font-size: 42px; letter-spacing: -2px; }}
        body {{ gap: 26px; padding: 32px 16px; }}
    }}

    .card {{
        text-decoration: none;
        color: var(--text);
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 18px 12px 14px 12px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        transition: transform 0.18s cubic-bezier(0.34, 1.56, 0.64, 1),
                    background 0.18s ease,
                    border-color 0.18s ease,
                    box-shadow 0.18s ease;
        animation: fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) backwards;
        animation-delay: calc(var(--i, 0) * 45ms + 0.12s);
        cursor: pointer;
    }}

    .card:hover {{
        background: var(--card-hover);
        border-color: var(--accent);
        transform: translateY(-4px);
        box-shadow: 0 14px 32px -12px var(--glow);
    }}

    .card:active {{ transform: translateY(-2px); }}

    .fav {{
        width: 48px;
        height: 48px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
        color: {fav_text};
        font-weight: 700;
        font-size: 20px;
        letter-spacing: -0.5px;
        box-shadow: 0 6px 16px -6px var(--glow);
        transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}

    .card:hover .fav {{ transform: scale(1.08) rotate(-3deg); }}

    .t {{
        font-size: 12.5px;
        font-weight: 600;
        text-align: center;
        color: var(--text);
        width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        letter-spacing: -0.1px;
    }}

    .host {{
        font-size: 11px;
        color: var(--muted);
        width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        text-align: center;
        margin-top: -4px;
    }}

    .empty {{
        width: min(640px, 92vw);
        text-align: center;
        color: var(--muted);
        font-size: 13.5px;
        line-height: 1.65;
        animation: fadeUp 0.5s 0.15s cubic-bezier(0.16, 1, 0.3, 1) backwards;
    }}

    .empty strong {{ color: var(--text); font-weight: 600; }}

    .empty kbd {{
        display: inline-block;
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 5px;
        padding: 1px 6px;
        font-size: 11px;
        font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
        color: var(--text);
        margin: 0 2px;
    }}

    .hint {{
        color: var(--muted);
        font-size: 11.5px;
        opacity: 0.72;
        animation: fadeUp 0.55s 0.3s cubic-bezier(0.16, 1, 0.3, 1) backwards;
        text-align: center;
    }}

    .hint kbd {{
        font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
        font-size: 11px;
        background: transparent;
        border: none;
        color: var(--muted);
    }}

    @keyframes fadeUp {{
        from {{ opacity: 0; transform: translateY(14px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}

    @keyframes fadeDown {{
        from {{ opacity: 0; transform: translateY(-12px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        .logo, form, .card, .empty, .hint {{ animation: none !important; }}
        .card, .fav {{ transition: none !important; }}
    }}
    """


# ══════════════════════════════════════════════════════════════════════
#  New Tab page helpers
# ══════════════════════════════════════════════════════════════════════
def _host_of(url: str) -> str:
    try:
        h = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    if h.startswith("www."):
        h = h[4:]
    if ":" in h:
        h = h.split(":", 1)[0]
    return h


def _short_title(site: dict) -> str:
    title = (site.get("title") or "").strip()
    if not title:
        title = _host_of(site["url"]) or site["url"]
    return title[:26]


def _initial(site: dict) -> str:
    base = (site.get("title") or "").strip() or _host_of(site["url"]) or "?"
    return base[:1].upper() or "?"


def render_newtab(store) -> str:
    theme = store.settings.get("theme", "dark")
    engine_name = store.settings.get("search_engine", "Google")
    engine = SEARCH_ENGINES.get(engine_name, SEARCH_ENGINES["Google"])

    sites = list(store.bookmarks)[:8]

    if sites:
        cards_html = []
        for i, bm in enumerate(sites):
            url = html_mod.escape(bm["url"], quote=True)
            title = html_mod.escape(_short_title(bm))
            host = html_mod.escape(_host_of(bm["url"]))
            initial = html_mod.escape(_initial(bm))
            cards_html.append(
                f'<a class="card" href="{url}" style="--i:{i}" '
                f'title="{html_mod.escape(bm["title"] or bm["url"], quote=True)}\n{url}">'
                f'<div class="fav">{initial}</div>'
                f'<div class="t">{title}</div>'
                + (f'<div class="host">{host}</div>' if host else "")
                + "</a>"
            )
        grid = f'<div class="grid">{"".join(cards_html)}</div>'
    else:
        grid = (
            '<div class="empty">'
            "No bookmarks yet.<br>"
            "Add one with <kbd>Ctrl</kbd>+<kbd>D</kbd> on sites you visit "
            "often &mdash; they will appear here."
            "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New Tab</title>
<style>{_newtab_css(theme)}</style>
</head>
<body>
  <div class="logo">Frame<span class="dot">.</span></div>
  <form action="{engine['action']}" method="get">
    <input type="text" name="{engine['param']}"
           placeholder="Search with {html_mod.escape(engine_name)} or type a URL"
           autofocus autocomplete="off" spellcheck="false">
  </form>
  {grid}
  <p class="hint">
    <kbd>Ctrl+T</kbd> new tab
    &nbsp;·&nbsp;
    <kbd>Ctrl+L</kbd> address bar
    &nbsp;·&nbsp;
    <kbd>Ctrl+D</kbd> bookmark
    &nbsp;·&nbsp;
    <kbd>Ctrl+J</kbd> downloads
  </p>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════
#  frame://version page
# ══════════════════════════════════════════════════════════════════════
def render_version(store) -> str:
    """frame://version — app + Chromium version + active flags.

    Chromium version diambil via `navigator.userAgent` di JS karena
    QtWebEngine tidak expose API Python untuk itu.
    """
    import os
    import platform
    import sys

    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR

    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    flag_list = sorted(f for f in flags.split() if f.startswith("--"))
    theme = store.settings.get("theme", "dark")
    c = THEMES.get(theme, THEMES["dark"])

    flag_rows = "".join(
        f"<tr><td><code>{html_mod.escape(f)}</code></td></tr>"
        for f in flag_list
    ) or "<tr><td><em>none</em></td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Frame · Version</title>
<style>
  body {{
    font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
    background: {c['bg']}; color: {c['text']};
    max-width: 720px; margin: 0 auto; padding: 48px 24px;
    line-height: 1.55;
  }}
  h1 {{ font-size: 24px; margin: 0 0 24px 0; letter-spacing: -0.5px; }}
  h1 span {{ color: {c['accent']}; }}
  h2 {{
    font-size: 13px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: {c['muted']};
    margin: 28px 0 10px 0;
  }}
  table {{
    width: 100%; border-collapse: collapse;
    background: {c['bg_light']}; border: 1px solid {c['border']};
    border-radius: 10px; overflow: hidden;
  }}
  td {{
    padding: 9px 14px; border-bottom: 1px solid {c['border']};
    font-size: 13px; vertical-align: top;
  }}
  tr:last-child td {{ border-bottom: none; }}
  td:first-child {{ width: 40%; color: {c['muted']}; }}
  code {{
    font-family: ui-monospace, Menlo, Consolas, monospace;
    font-size: 12px;
    background: {c['bg']}; padding: 2px 6px; border-radius: 4px;
    word-break: break-all;
  }}
  .hint {{ color: {c['muted']}; font-size: 12px; margin-top: 24px; }}
</style>
</head>
<body>
  <h1>Frame<span>.</span> version</h1>

  <h2>Application</h2>
  <table>
    <tr><td>Python</td><td>{sys.version.split()[0]}</td></tr>
    <tr><td>Platform</td><td>{platform.system()} {platform.release()}</td></tr>
    <tr><td>Qt</td><td>{QT_VERSION_STR}</td></tr>
    <tr><td>PyQt6</td><td>{PYQT_VERSION_STR}</td></tr>
  </table>

  <h2>Chromium (from user agent)</h2>
  <table>
    <tr><td>Version</td><td><span id="chrome-ver">&hellip;</span></td></tr>
    <tr><td>Full user agent</td><td><code id="ua">&hellip;</code></td></tr>
  </table>

  <h2>Chromium flags (active)</h2>
  <table>{flag_rows}</table>

  <script>
    (function() {{
      var ua = navigator.userAgent;
      var uaEl = document.getElementById('ua');
      if (uaEl) uaEl.textContent = ua;
      var m = ua.match(/Chrom(e|ium)\\/([\\d.]+)/);
      var verEl = document.getElementById('chrome-ver');
      if (verEl && m && m[2]) verEl.textContent = m[2];
    }})();
  </script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════
#  Scheme handler
# ══════════════════════════════════════════════════════════════════════
class InternalSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:
        host = job.requestUrl().host()
        if host == "newtab":
            body = render_newtab(self.store)
        elif host == "version":
            body = render_version(self.store)
        else:
            body = (
                "<html><body style='font-family:sans-serif;padding:48px;'>"
                "<h2>404</h2>"
                "<p>Internal page not found.</p></body></html>"
            )
        buf = QBuffer(job)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        buf.write(body.encode("utf-8"))
        buf.close()
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(b"text/html", buf)
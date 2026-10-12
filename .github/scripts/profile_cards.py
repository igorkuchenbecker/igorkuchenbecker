"""Gera os cards SVG do perfil (estatísticas, linguagens, atividade, troféus e projetos).

Roda no GitHub Actions com o GITHUB_TOKEN do próprio workflow, sem depender de
serviços externos. Uso: python profile_cards.py <usuario> <pasta_saida>
"""

import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

# ── Paleta ──────────────────────────────────────────────────────────────
BG = "#0D0D0D"
BORDER = "#2E1065"
TITLE = "#A855F7"
ACCENT = "#7C3AED"
TEXT = "#D4D4D8"
MUTED = "#A1A1AA"
LIGHT = "#E9D5FF"
DEEP = "#3B0764"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', Consolas, monospace"

# Repositórios fixados nos cards (ordem de exibição)
PINNED = [
    "gdap",
    "jarvis",
    "Analise-de-Entregas",
    "intrusion-detec-sys",
    "pishing-detec",
    "linux-system-manager",
]

# Fora do cálculo de linguagens: notebooks inflam o tamanho e o moon-browser
# é baseado no código do Firefox (não reflete o que foi escrito por mim).
LANG_EXCLUDE = {"Jupyter Notebook", "HTML", "CSS"}
REPO_EXCLUDE_FROM_LANGS = {"moon-browser"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        name description url stargazerCount forkCount
        primaryLanguage { name }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(login: str) -> dict:
    token = os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if payload.get("errors"):
        print("Avisos da API:", payload["errors"], file=sys.stderr)
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise SystemExit("Não foi possível ler os dados do usuário.")
    return user


# ── Helpers ─────────────────────────────────────────────────────────────
def frame(w: int, h: int, body: str, title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<style>
  .t {{ font: 600 17px {FONT}; fill: {TITLE}; }}
  .l {{ font: 400 13px {FONT}; fill: {TEXT}; }}
  .m {{ font: 400 12px {FONT}; fill: {MUTED}; }}
  .v {{ font: 700 14px {MONO}; fill: {LIGHT}; }}
  .fade {{ opacity: 0; animation: f .6s ease forwards; }}
  @keyframes f {{ to {{ opacity: 1; }} }}
</style>
<rect x="0.5" y="0.5" rx="10" width="{w - 1}" height="{h - 1}" fill="{BG}" stroke="{BORDER}"/>
{body}
</svg>
"""


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def wrap(text: str, width: int, lines: int) -> list[str]:
    words, out, cur = (text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}".strip()
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: width - 1].rstrip() + "…"
    return out


# ── Cards ───────────────────────────────────────────────────────────────
def stats_card(u: dict) -> str:
    repos = u["repositories"]["nodes"]
    cc = u["contributionsCollection"]
    rows = [
        ("Contribuições no último ano", cc["contributionCalendar"]["totalContributions"]),
        ("Commits no último ano", cc["totalCommitContributions"]),
        ("Pull requests", (u.get("pullRequests") or {}).get("totalCount", 0)),
        ("Issues", (u.get("issues") or {}).get("totalCount", 0)),
        ("Repositórios públicos", u["repositories"]["totalCount"]),
        ("Estrelas recebidas", sum(r["stargazerCount"] for r in repos)),
    ]
    body = ['<text x="25" y="36" class="t">Estatísticas no GitHub</text>']
    for i, (label, val) in enumerate(rows):
        y = 70 + i * 22
        body.append(
            f'<g class="fade" style="animation-delay:{i * 120}ms">'
            f'<circle cx="31" cy="{y - 4}" r="3.5" fill="{ACCENT}"/>'
            f'<text x="45" y="{y}" class="l">{label}</text>'
            f'<text x="440" y="{y}" class="v" text-anchor="end">{fmt(val)}</text></g>'
        )
    return frame(465, 200, "\n".join(body), "Estatísticas no GitHub")


def languages(u: dict) -> list[tuple[str, float]]:
    totals: dict[str, int] = {}
    for r in u["repositories"]["nodes"]:
        if r["name"] in REPO_EXCLUDE_FROM_LANGS:
            continue
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name not in LANG_EXCLUDE:
                totals[name] = totals.get(name, 0) + e["size"]
    total = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    return [(n, s * 100 / total) for n, s in top]


def langs_card(u: dict) -> str:
    langs = languages(u)
    shades = ["#A855F7", "#9333EA", "#7C3AED", "#6D28D9", "#5B21B6", "#4C1D95"]
    body = ['<text x="25" y="36" class="t">Linguagens mais usadas</text>']
    x, bar_w = 25.0, 300
    body.append(f'<rect x="25" y="52" width="{bar_w}" height="8" rx="4" fill="#1A1A1A"/>')
    for i, (name, pct) in enumerate(langs):
        w = bar_w * pct / 100
        body.append(f'<rect x="{x:.1f}" y="52" width="{max(w, 0.5):.1f}" height="8" fill="{shades[i]}"/>')
        x += w
    body.append(
        f'<rect x="25" y="52" width="{bar_w}" height="8" rx="4" fill="none" stroke="{BG}" stroke-width="2"/>'
    )
    for i, (name, pct) in enumerate(langs):
        col, row = i % 2, i // 2
        cx, cy = 30 + col * 155, 88 + row * 28
        body.append(
            f'<g class="fade" style="animation-delay:{i * 100}ms">'
            f'<circle cx="{cx}" cy="{cy - 4}" r="5" fill="{shades[i]}"/>'
            f'<text x="{cx + 12}" y="{cy}" class="l">{escape(name)}</text>'
            f'<text x="{cx + 140}" y="{cy}" class="m" text-anchor="end">{pct:.1f}%</text></g>'
        )
    return frame(350, 200, "\n".join(body), "Linguagens mais usadas")


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def activity_card(u: dict) -> str:
    weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"][-52:]
    counts = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    starts = [dt.date.fromisoformat(w["contributionDays"][0]["date"]) for w in weeks]
    w, h = 900, 300
    left, right, top, bottom = 55, 25, 60, 50
    pw, ph = w - left - right, h - top - bottom
    peak = max(4, -(-max(counts + [0]) // 4) * 4)
    step = pw / max(len(counts) - 1, 1)
    pts = [(left + i * step, top + ph - c / peak * ph) for i, c in enumerate(counts)]

    body = [
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{TITLE}" stop-opacity=".45"/>'
        f'<stop offset="1" stop-color="{DEEP}" stop-opacity="0"/></linearGradient></defs>',
        '<text x="25" y="36" class="t">Contribuições por semana · último ano</text>',
    ]
    for k in range(5):
        y = top + ph * k / 4
        val = round(peak * (4 - k) / 4)
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{w - right}" y2="{y:.1f}" stroke="#1F1F1F"/>')
        body.append(f'<text x="{left - 10}" y="{y + 4:.1f}" class="m" text-anchor="end">{val}</text>')
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{left},{top + ph} {line} {pts[-1][0]:.1f},{top + ph}"
    body.append(f'<polygon points="{area}" fill="url(#g)"/>')
    body.append(
        f'<polyline points="{line}" fill="none" stroke="{TITLE}" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for (x, y), c in zip(pts, counts):
        if c:
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{LIGHT}"/>')
    last_month = None
    for i, d in enumerate(starts):
        if d.month != last_month and 0 < i < len(starts) - 2:
            body.append(
                f'<text x="{pts[i][0]:.1f}" y="{h - 20}" class="m" text-anchor="middle">{MESES[d.month - 1]}</text>'
            )
        last_month = d.month
    return frame(w, h, "\n".join(body), "Contribuições por semana")


TROPHY = (
    "M-14,-18 h28 v6 a14,14 0 0 1 -11,13.7 v5.3 h6 v5 h-18 v-5 h6 v-5.3 "
    "a14,14 0 0 1 -11,-13.7 z M-14,-14 h-6 a6,6 0 0 0 6,8 z M14,-14 h6 a6,6 0 0 1 -6,8 z"
)


def rank(value: int, thresholds: list[int]) -> tuple[str, int]:
    names = ["C", "B", "A", "S"]
    level = sum(value >= t for t in thresholds)
    return (names[level - 1], level) if level else ("–", 0)


def trophies_card(u: dict) -> str:
    repos = u["repositories"]["nodes"]
    cc = u["contributionsCollection"]
    items = [
        ("Commits", cc["totalCommitContributions"], [1, 50, 200, 500]),
        ("Contribuições", cc["contributionCalendar"]["totalContributions"], [1, 50, 200, 500]),
        ("Repositórios", u["repositories"]["totalCount"], [1, 5, 10, 25]),
        ("Linguagens", len(languages(u)) + 0, [1, 3, 5, 6]),
        ("Estrelas", sum(r["stargazerCount"] for r in repos), [1, 5, 20, 50]),
        ("Pull requests", (u.get("pullRequests") or {}).get("totalCount", 0), [1, 5, 20, 50]),
    ]
    fills = {0: "#27272A", 1: "#4C1D95", 2: "#6D28D9", 3: "#9333EA", 4: "#C084FC"}
    cw, gap = 128, 10
    w = len(items) * cw + (len(items) - 1) * gap + 30
    body = []
    for i, (label, val, th) in enumerate(items):
        letter, lvl = rank(val, th)
        x = 15 + i * (cw + gap)
        body.append(
            f'<g class="fade" style="animation-delay:{i * 110}ms" transform="translate({x},15)">'
            f'<rect width="{cw}" height="130" rx="8" fill="#141414" stroke="{BORDER}"/>'
            f'<g transform="translate({cw / 2},48)"><path d="{TROPHY}" fill="{fills[lvl]}"/></g>'
            f'<rect x="{cw - 34}" y="8" width="26" height="18" rx="9" fill="{BG}" stroke="{fills[lvl] if lvl else BORDER}"/>'
            f'<text x="{cw - 21}" y="21" text-anchor="middle" style="font:700 11px {MONO};fill:{LIGHT if lvl else MUTED}">{letter}</text>'
            f'<text x="{cw / 2}" y="92" class="l" text-anchor="middle">{label}</text>'
            f'<text x="{cw / 2}" y="113" class="v" text-anchor="middle">{fmt(val)}</text></g>'
        )
    return frame(w, 160, "\n".join(body), "Troféus")


def pin_card(repo: dict) -> str:
    lines = wrap(repo.get("description") or "Sem descrição.", 54, 2)
    lang = (repo.get("primaryLanguage") or {}).get("name", "")
    body = [
        f'<g transform="translate(25,33)"><path fill="{TITLE}" d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.71 1.71.75.75 0 0 1-1.07 1.05A2.5 2.5 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.71A2.5 2.5 0 0 1 4.5 9h8Z" transform="translate(0,-12)"/></g>',
        f'<text x="47" y="34" class="t" style="font-size:15px">{escape(repo["name"])}</text>',
    ]
    for i, ln in enumerate(lines):
        body.append(f'<text x="25" y="{62 + i * 18}" class="m" style="font-size:12.5px">{escape(ln)}</text>')
    meta = [f'<circle cx="31" cy="111" r="5" fill="{ACCENT}"/><text x="42" y="115" class="m">{escape(lang)}</text>']
    meta.append(f'<text x="375" y="115" class="m" text-anchor="end">★ {repo["stargazerCount"]}   ⑂ {repo["forkCount"]}</text>')
    body += meta
    return frame(400, 135, "\n".join(body), repo["name"])


def main() -> None:
    login, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    u = fetch(login)
    files = {
        "stats.svg": stats_card(u),
        "langs.svg": langs_card(u),
        "activity.svg": activity_card(u),
        "trophies.svg": trophies_card(u),
    }
    by_name = {r["name"]: r for r in u["repositories"]["nodes"]}
    for name in PINNED:
        if name in by_name:
            files[f"pin-{name}.svg"] = pin_card(by_name[name])
    for fname, svg in files.items():
        with open(os.path.join(out, fname), "w", encoding="utf-8") as f:
            f.write(svg)
        print("gerado:", fname)


if __name__ == "__main__":
    main()

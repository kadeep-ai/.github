#!/usr/bin/env python3
"""Draw every image on github.com/kadeep-ai, once for each GitHub theme.

    pip install -r scripts/requirements.txt
    python3 scripts/build.py               # writes profile/assets/{dark,light}/*.svg
    python3 scripts/build.py hero gate     # only some of them

The type is Geist and Geist Mono (SIL OFL 1.1, scripts/fonts/OFL.txt), subset and embedded
in each SVG so it renders the same everywhere. Motion is CSS only and stops for anyone who
asks their system for reduced motion: every animated image then shows its finished frame.

Sources, all KaDeep AI's own:
  release-ready-report-*.webp   KaDeep Studio Pro 4.0, from docs.kadeep.ai
  logos/*                       as shown on kadeep.ai; each mark belongs to its owner
"""
from __future__ import annotations

import base64
import io
import logging
import math
import re
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image

logging.getLogger("fontTools").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
SRC = ROOT / "scripts" / "source"
OUT = ROOT / "profile" / "assets"

W = 1280

# --------------------------------------------------------------------------- theme

THEMES = {
    "dark": dict(
        bg="#0d1117", surface="#151b23", surface2="#1d242e", line="#2a313b", line2="#3d444d",
        ink="#f0f6fc", muted="#9198a1", faint="#6e7681",
        blue="#4c9cf0", ok="#3fb950", warn="#d29922", bad="#f85149", bad_bg="#2d1517", bad_line="#6e2a2b",
        btn="#f0f6fc", btn_ink="#0d1117", glow="#2f81f7", glow_op=0.20, shadow_op=0.55,
    ),
    "light": dict(
        bg="#ffffff", surface="#f6f8fa", surface2="#eef1f4", line="#dfe4ea", line2="#c9d1d9",
        ink="#1f2328", muted="#59636e", faint="#818b98",
        blue="#1a6fd1", ok="#1a7f37", warn="#bf8700", bad="#cf222e", bad_bg="#fff1f0", bad_line="#ffcecb",
        btn="#0a0a0a", btn_ink="#ffffff", glow="#3b82f6", glow_op=0.13, shadow_op=0.16,
    ),
}
TILE = "#0A0A0A"          # KaDeep Studio's tile: black in both themes
TERM = dict(bg="#0a0a0a", bar="#161616", ink="#ededed", muted="#8a8a8a", ok="#22c55e", bad="#ef4444")

# family, weight, size, tracking (em)
ROLES = {
    "display": ("Geist", 600, 104, -0.042),
    "h2": ("Geist", 600, 60, -0.034),
    "title": ("Geist", 600, 38, -0.024),
    "name": ("Geist", 600, 30, -0.016),
    "lede": ("Geist", 400, 30, -0.008),
    "body": ("Geist", 400, 23, -0.004),
    "bodym": ("Geist", 500, 23, -0.006),
    "small": ("Geist", 400, 19, 0.0),
    "label": ("Geist", 500, 15, 0.08),
    "btn": ("Geist", 500, 21, -0.008),
    "mono": ("GeistMono", 400, 17, 0.0),
    "monob": ("GeistMono", 600, 17, 0.0),
}
FALLBACK = {
    "Geist": "Geist,-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif",
    "GeistMono": "'Geist Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace",
}

# --------------------------------------------------------------------------- fonts


@lru_cache(maxsize=None)
def static_font_bytes(family: str, weight: int) -> bytes:
    vf = TTFont(FONTS / f"{family}-VF.ttf", recalcTimestamp=False)
    font = instancer.instantiateVariableFont(vf, {"wght": weight})
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


@lru_cache(maxsize=None)
def metrics(family: str, weight: int):
    font = TTFont(io.BytesIO(static_font_bytes(family, weight)))
    return font.getBestCmap(), font["hmtx"].metrics, font["head"].unitsPerEm


def measure(text: str, role: str, size: float | None = None) -> float:
    family, weight, rsize, tracking = ROLES[role]
    size = size or rsize
    cmap, hmtx, upm = metrics(family, weight)
    adv = sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in text)
    return adv * size / upm + tracking * size * len(text)


def woff2_b64(family: str, weight: int, chars: str) -> str:
    font = TTFont(io.BytesIO(static_font_bytes(family, weight)), recalcTimestamp=False)
    font["head"].modified = font["head"].created      # no build time inside, so rebuilds are byte-identical
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk", "tnum"]
    opts.name_IDs = []
    opts.hinting = False
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text=chars + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def wrap(text: str, role: str, width: float, size: float | None = None) -> list[str]:
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, role, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------- svg


class Svg:
    """A small SVG writer that records which glyphs each font needs."""

    def __init__(self, w: int, h: int, theme: str, title: str):
        self.w, self.h, self.theme, self.title = w, h, theme, title
        self.c = THEMES[theme]
        self.defs: list[str] = []
        self.css: list[str] = []
        self.body: list[str] = []
        self.glyphs: dict[tuple[str, int], set[str]] = defaultdict(set)

    def add(self, s: str):
        self.body.append(s)

    def text(self, x, y, s, role="body", fill=None, anchor="start", size=None, opacity=None, extra=""):
        family, weight, rsize, tracking = ROLES[role]
        size = size or rsize
        self.glyphs[(family, weight)].update(s)
        fam = f"'{family}{weight}',{FALLBACK[family]}"
        attrs = [f'x="{x:g}"', f'y="{y:g}"', f'font-family="{fam}"', f'font-size="{size:g}"',
                 f'font-weight="{weight}"', f'fill="{fill or self.c["ink"]}"']
        if tracking:
            attrs.append(f'letter-spacing="{tracking * size:.2f}"')
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if opacity is not None:
            attrs.append(f'opacity="{opacity}"')
        self.add(f"<text {' '.join(attrs)} {extra}>{escape(s)}</text>")

    def runs(self, x, y, parts, role="body", size=None, anchor="start", extra=""):
        """One line of differently coloured runs: parts = [(text, fill), ...]."""
        family, weight, rsize, tracking = ROLES[role]
        size = size or rsize
        fam = f"'{family}{weight}',{FALLBACK[family]}"
        spans = []
        for s, fill in parts:
            self.glyphs[(family, weight)].update(s)
            spans.append(f'<tspan fill="{fill}">{escape(s)}</tspan>')
        ls = f' letter-spacing="{tracking * size:.2f}"' if tracking else ""
        ta = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text x="{x:g}" y="{y:g}" font-family="{fam}" font-size="{size:g}" '
                 f'font-weight="{weight}"{ls}{ta} xml:space="preserve" {extra}>{"".join(spans)}</text>')

    def paragraph(self, x, y, s, role, width, leading, fill=None, size=None, anchor="start"):
        lines = wrap(s, role, width, size)
        for i, line in enumerate(lines):
            self.text(x, y + i * leading, line, role, fill=fill, size=size, anchor=anchor)
        return y + (len(lines) - 1) * leading

    def dots(self, pts, r, fill, opacity=1.0, cls=""):
        """Many dots of one radius as one path of zero-length round-capped segments."""
        if not pts:
            return
        d = "".join(f"M{x:g} {y:g}h0" for x, y in pts)
        c = f' class="{cls}"' if cls else ""
        op = f' opacity="{opacity:g}"' if opacity < 1 else ""
        self.add(f'<path{c} d="{d}" fill="none" stroke="{fill}" stroke-width="{2 * r:g}" '
                 f'stroke-linecap="round"{op}/>')

    def render(self) -> str:
        faces = []
        for (family, weight), chars in sorted(self.glyphs.items()):
            data = woff2_b64(family, weight, "".join(sorted(chars)))
            faces.append(f"@font-face{{font-family:'{family}{weight}';font-weight:{weight};"
                         f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")
        style = "".join(faces + self.css)
        motion = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">\n'
            f"<title>{escape(self.title)}</title>\n<style>{style}{motion}</style>\n"
            f'<defs>{"".join(self.defs)}</defs>\n' + "\n".join(self.body) + "\n</svg>\n"
        )

    def save(self, name: str):
        path = OUT / self.theme / f"{name}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.render()
        path.write_text(data)
        print(f"  {self.theme:5s} {name:16s} {len(data) / 1024:7.1f} KB")


def keyframes(name: str, stops: list[tuple[float, str]]) -> str:
    """@keyframes from (percent, declarations) pairs."""
    return f"@keyframes {name}{{" + "".join(f"{p:g}%{{{d}}}" for p, d in stops) + "}"


def appear(svg: Svg, cls: str, at: float, cycle: float, until: float = 96, base="opacity:1"):
    """Hidden until `at`% of the loop, shown until `until`%. Shown for good when motion is off."""
    svg.css.append(keyframes(cls, [(0, "opacity:0"), (max(at - 0.01, 0), "opacity:0"), (at, "opacity:1"),
                                   (until, "opacity:1"), (min(until + 2, 100), "opacity:0"), (100, "opacity:0")]))
    svg.css.append(f".{cls}{{animation:{cls} {cycle}s step-end infinite}}")


# --------------------------------------------------------------------------- images and marks


def webp_b64(im: Image.Image, width: int, quality=84) -> tuple[str, int, int]:
    h = round(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    return base64.b64encode(buf.getvalue()).decode(), width, h


@lru_cache(maxsize=None)
def png_b64(path: str, px: int, tint: str | None = None) -> str:
    """A raster mark cropped to what it draws, optionally recoloured to one flat tint."""
    im = Image.open(path).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    im = im.resize((px, round(im.height * px / im.width)), Image.LANCZOS)
    if tint:
        flat = Image.new("RGBA", im.size, tint)
        flat.putalpha(im.getchannel("A"))
        im = flat
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


@lru_cache(maxsize=None)
def ks_points() -> tuple:
    src = (SRC / "ks-mark.svg").read_text()
    return tuple((float(a), float(b)) for a, b in re.findall(r'cx="([\d.]+)" cy="([\d.]+)"', src))


def mark_ks(svg: Svg, x, y, size, border=True):
    """KaDeep Studio: KS in white dots on a black tile, black in both themes."""
    s = 0.70 * size / 1228
    ox = x + (size - 1228 * s) / 2 - 11 * s
    oy = y + (size - 778 * s) / 2 - 11 * s
    stroke = f' stroke="{svg.c["line2"]}" stroke-width="1"' if border and svg.theme == "dark" else ""
    svg.add(f'<rect x="{x:g}" y="{y:g}" width="{size:g}" height="{size:g}" rx="{0.224 * size:.2f}" '
            f'fill="{TILE}"{stroke}/>')
    svg.dots([(ox + u * s, oy + v * s) for u, v in ks_points()], 42 * s, "#FFFFFF")
    return size


def mark_kadeep_ai(svg: Svg, x, y, size):
    """KaDeep AI: the folded blue K, as on kadeep.ai."""
    svg.add(f'<image x="{x:g}" y="{y:g}" width="{size:g}" height="{size:g}" preserveAspectRatio="xMidYMid meet" '
            f'href="data:image/png;base64,{png_b64(str(SRC / "kadeep-ai-mark.png"), round(size * 3))}"/>')
    return size


@lru_cache(maxsize=None)
def logo_svg_parts(name: str):
    src = (SRC / "logos" / f"{name}.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()]
    inner = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)
    inner = re.sub(r"<defs>.*?</defs>", "", inner, flags=re.S)
    inner = re.sub(r'\s(fill|stroke)="[^"]*"', "", inner)
    inner = re.sub(r'\sid="[^"]*"', "", inner)
    return vb, inner


def logo(svg: Svg, name: str, x, y, h, fill):
    """A partner mark drawn in one flat colour, `h` tall, from (x, y). Returns its width."""
    if name == "gemini":
        w = h
        svg.add(f'<image x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
                f'href="data:image/png;base64,{png_b64(str(SRC / "logos" / "gemini.png"), round(h * 3), fill)}"/>')
        return w
    (vx, vy, vw, vh), inner = logo_svg_parts(name)
    s = h / max(vw, vh)
    w = vw * s
    svg.add(f'<g fill="{fill}" transform="translate({x - vx * s:g} {y + (h - vh * s) / 2 - vy * s:g}) '
            f'scale({s:g})">{inner}</g>')
    return w


MONO_LOGOS = {"openai-mark", "linear", "github", "cursor"}


def logo_color(svg: Svg, name: str, x, y, h):
    """A partner mark in its own colours, or in ink where the mark is black."""
    if name in MONO_LOGOS:
        return logo(svg, name, x, y, h, svg.c["ink"])
    if name.endswith("gemini"):
        svg.add(f'<image x="{x:g}" y="{y:g}" width="{h:g}" height="{h:g}" '
                f'href="data:image/png;base64,{png_b64(str(SRC / "logos" / "gemini.png"), round(h * 3))}"/>')
        return h
    src = (SRC / "logos" / f"{name}.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()]
    inner = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)
    root_fill = re.search(r'<svg[^>]*\sfill="([^"]+)"', src)
    fill = f' fill="{root_fill.group(1)}"' if root_fill else ""
    w = h * vb[2] / vb[3] if vb[2] < vb[3] else h
    hh = h if vb[2] < vb[3] else h * vb[3] / vb[2]
    svg.add(f'<svg x="{x:g}" y="{y + (h - hh) / 2:g}" width="{w:g}" height="{hh:g}" viewBox="{" ".join(map(str, vb))}"{fill}>'
            f'{inner}</svg>')
    return w


def lockup(svg: Svg, cx, y):
    """[KS] KaDeep™ Studio Pro, and under it: a product of [K] KaDeep AI. Centred on cx."""
    c = svg.c
    tile, gap = 64, 18
    a, tm, b = "KaDeep", "™", " Studio Pro"
    size = 36
    w1 = measure(a, "name", size) + measure(tm, "name", 15) + 1 + measure(b, "name", size)
    total = tile + gap + w1
    x = cx - total / 2
    mark_ks(svg, x, y, tile)
    tx = x + tile + gap
    base = y + 30
    svg.text(tx, base, a, "name", size=size)
    tx += measure(a, "name", size) + 1
    svg.text(tx, base - 16, tm, "name", size=15)
    tx += measure(tm, "name", 15) + measure(" ", "name", size)
    svg.text(tx, base, b.strip(), "name", size=size)
    # second line
    sub, co = "a product of", "KaDeep AI"
    k = 20
    sx = x + tile + gap
    svg.text(sx, y + 59, sub, "small", fill=c["muted"], size=19)
    sx += measure(sub, "small", 19) + 8
    mark_kadeep_ai(svg, sx, y + 43, k)
    svg.text(sx + k + 6, y + 59, co, "bodym", size=19)


def window_shadow(svg: Svg, fid: str):
    op = svg.c["shadow_op"]
    svg.defs.append(
        f'<filter id="{fid}" x="-10%" y="-10%" width="120%" height="130%">'
        f'<feGaussianBlur in="SourceAlpha" stdDeviation="22"/><feOffset dy="18"/>'
        f'<feComponentTransfer><feFuncA type="linear" slope="{op}"/></feComponentTransfer>'
        f'<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>')


# --------------------------------------------------------------------------- hero

SHOT_BOX = (34, 34, 1766, 1160)      # the window inside the docs screenshot (it has a transparent margin)
VERDICT = (371, 465, 1262, 1078)     # the "Not ready" card, in screenshot pixels


def hero(theme: str):
    svg = Svg(W, 0, theme, "")
    c = svg.c
    head = "Know what is ready"
    word, dot = "ship", "."
    sw, sx0 = 1160, 60                       # the product window
    im = Image.open(SRC / f"release-ready-report-manage-{theme}.webp").convert("RGBA").crop(SHOT_BOX)
    data, iw, ih = webp_b64(im, 1700, quality=82)
    sh = sw * ih / iw
    y_lock, y1, y2, y_lede = 0, 214, 334, 420
    y_win = 492
    H = round(y_win + sh + 70)
    svg.h = H
    svg.title = ("KaDeep Studio Pro, a product of KaDeep AI. Know what is ready to ship. Faster releases. Lower "
                 "cost-to-quality. Less risk. Below, KaDeep Studio Pro's release report: the release is not "
                 "ready, with the reasons, the evidence and six sign-offs.")

    # a soft light behind the window
    svg.defs.append(f'<radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="{c["glow"]}" '
                    f'stop-opacity="{c["glow_op"]}"/><stop offset="1" stop-color="{c["glow"]}" stop-opacity="0"/>'
                    '</radialGradient>')
    svg.add(f'<ellipse cx="{W / 2}" cy="{y_win + 120}" rx="{W * 0.56:g}" ry="300" fill="url(#glow)"/>')

    lockup(svg, W / 2, y_lock)

    # the headline: line one, then "to [ship]." with the word typed into a pill
    svg.text(W / 2, y1, head, "display", anchor="middle")
    pre = "to "
    size = ROLES["display"][2]
    w_pre, w_word, w_dot = measure(pre, "display"), measure(word, "display"), measure(dot, "display")
    pad = 26
    total = w_pre + pad + w_word + pad + 14 + w_dot
    x = W / 2 - total / 2
    svg.text(x, y2, pre.strip(), "display")
    px = x + w_pre
    pill_w = pad + w_word + pad + 14
    svg.add(f'<rect x="{px:g}" y="{y2 - 86:g}" width="{pill_w:g}" height="{112}" rx="24" fill="{c["btn"]}"/>')
    # one letter at a time, then the caret blinks after the word
    cycle = 14.0
    lx = px + pad
    for i, ch in enumerate(word):
        appear(svg, f"l{i}", 8 + i * 3.2, cycle, until=97.5)
        svg.text(lx, y2, ch, "display", fill=c["btn_ink"], extra=f'class="l{i}"')
        lx += measure(ch, "display")
    # caret: follows each letter as it lands, then blinks
    stops = [(0, f"transform:translateX({-w_word:.1f}px)")]
    acc = 0.0
    for i, ch in enumerate(word):
        acc += measure(ch, "display")
        stops.append((8 + i * 3.2, f"transform:translateX({acc - w_word:.1f}px)"))
    stops.append((97.5, f"transform:translateX({-w_word:.1f}px)"))
    svg.css.append(keyframes("caret", stops) + ".caret{animation:caret %gs step-end infinite}" % cycle)
    svg.css.append("@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}.blink{animation:blink 1.05s step-end infinite}")
    svg.add(f'<g class="caret"><rect class="blink" x="{px + pad + w_word + 6:g}" y="{y2 - 70:g}" width="7" '
            f'height="84" rx="2" fill="{c["btn_ink"]}"/></g>')
    svg.text(px + pill_w + 6, y2, dot, "display")

    svg.text(W / 2, y_lede, "Faster releases. Lower cost-to-quality. Less risk.", "lede", fill=c["muted"],
             anchor="middle")

    # the product, with a pulse on its verdict
    window_shadow(svg, "shadow")
    svg.defs.append(f'<clipPath id="win"><rect x="{sx0}" y="{y_win}" width="{sw}" height="{sh:.1f}" rx="16"/></clipPath>')
    svg.add(f'<g filter="url(#shadow)"><rect x="{sx0}" y="{y_win}" width="{sw}" height="{sh:.1f}" rx="16" fill="{c["bg"]}"/></g>')
    svg.add(f'<g clip-path="url(#win)"><image x="{sx0}" y="{y_win}" width="{sw}" height="{sh:.1f}" '
            f'href="data:image/webp;base64,{data}"/></g>')
    svg.add(f'<rect x="{sx0 + 0.5}" y="{y_win + 0.5}" width="{sw - 1}" height="{sh - 1:.1f}" rx="16" fill="none" '
            f'stroke="{c["line2"]}" stroke-opacity=".6"/>')
    s = sw / (SHOT_BOX[2] - SHOT_BOX[0])
    vx0, vy0 = sx0 + (VERDICT[0] - SHOT_BOX[0]) * s, y_win + (VERDICT[1] - SHOT_BOX[1]) * s
    vw, vh = (VERDICT[2] - VERDICT[0]) * s, (VERDICT[3] - VERDICT[1]) * s
    svg.css.append("@keyframes pulse{0%,100%{opacity:0;stroke-width:2px}40%{opacity:.85;stroke-width:5px}"
                   "70%{opacity:0;stroke-width:10px}}.pulse{opacity:0;animation:pulse 3.4s ease-out infinite}")
    svg.add(f'<rect class="pulse" x="{vx0:.1f}" y="{vy0:.1f}" width="{vw:.1f}" height="{vh:.1f}" rx="9" fill="none" '
            f'stroke="{c["bad"]}"/>')
    svg.save("hero")


# --------------------------------------------------------------------------- buttons


def icon_play(svg, cx, cy, r, fill, ink):
    svg.add(f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{fill}"/>'
            f'<path d="M{cx - r * 0.28:.2f} {cy - r * 0.40:.2f}L{cx + r * 0.46:.2f} {cy:.2f}L{cx - r * 0.28:.2f} '
            f'{cy + r * 0.40:.2f}Z" fill="{ink}"/>')


def icon_arrow(svg, cx, cy, r, fill, ink):
    a = r * 0.36
    svg.add(f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{fill}"/>'
            f'<path d="M{cx - a:.2f} {cy + a:.2f}L{cx + a:.2f} {cy - a:.2f}M{cx - a * 0.55:.2f} {cy - a:.2f}H{cx + a:.2f}'
            f'V{cy + a * 0.55:.2f}" fill="none" stroke="{ink}" stroke-width="{r * 0.17:.2f}" stroke-linecap="round" '
            'stroke-linejoin="round"/>')


def button(name: str, label: str, kind: str, lead=None, alt=None, play=False):
    """A centred link button. kind: 'primary' (filled) or 'secondary' (outlined).
    lead: a mark drawn before the label. Every button ends in a round arrow, like kadeep.ai's."""
    def build(theme):
        h, pad, margin = 60, 26, 8
        r = 17
        lead_w = 30 if lead else 0
        a, tm, b = label.partition("™")
        tw = measure(a, "btn") + (measure("™", "btn", 11) + 1 + measure(" ", "btn") + measure(b.strip(), "btn") if tm else 0)
        w = pad + (lead_w + 12 if lead else 0) + tw + 14 + 2 * r + 12
        svg = Svg(math.ceil(w + 2 * margin), h + 2, theme, alt or label)
        c = svg.c
        x0, y0 = margin, 1
        if kind == "primary":
            fill, ink, cfill, cink = c["btn"], c["btn_ink"], c["btn_ink"], c["btn"]
            svg.defs.append('<linearGradient id="sheen" x1="0" x2="0" y1="0" y2="1"><stop offset="0" '
                            'stop-color="#fff" stop-opacity=".16"/><stop offset=".55" stop-color="#fff" '
                            'stop-opacity="0"/></linearGradient>')
            svg.add(f'<rect x="{x0}" y="{y0}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{fill}"/>')
            if theme == "light":
                svg.add(f'<rect x="{x0}" y="{y0}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="url(#sheen)"/>')
        else:
            fill, ink, cfill, cink = c["bg"], c["ink"], c["btn"], c["btn_ink"]
            svg.add(f'<rect x="{x0 + 0.75}" y="{y0 + 0.75}" width="{w - 1.5:.1f}" height="{h - 1.5}" rx="{h / 2 - 0.75}" '
                    f'fill="{c["surface"]}" stroke="{c["line2"]}" stroke-width="1.5"/>')
        x = x0 + pad
        if lead:
            lead(svg, x, y0 + (h - lead_w) / 2, lead_w)
            x += lead_w + 12
        svg.text(x, y0 + h / 2 + 7.5, a, "btn", fill=ink)
        if tm:
            tx_ = x + measure(a, "btn") + 1
            svg.text(tx_, y0 + h / 2 - 2, "™", "btn", fill=ink, size=11)
            svg.text(tx_ + measure("™", "btn", 11) + measure(" ", "btn"), y0 + h / 2 + 7.5, b.strip(), "btn", fill=ink)
        x += tw + 14
        (icon_play if play else icon_arrow)(svg, x + r, y0 + h / 2, r, cfill, cink)
        svg.save(f"btn-{name}")
    return build


def chip(name: str, label: str, mark):
    """A small logo link for the footer."""
    def build(theme):
        h, pad, margin, mw = 44, 16, 6, 22
        w = pad + mw + 10 + measure(label, "small", 18) + pad
        svg = Svg(math.ceil(w + 2 * margin), h + 2, theme, label)
        c = svg.c
        svg.add(f'<rect x="{margin + 0.75}" y="1.75" width="{w - 1.5:.1f}" height="{h - 1.5}" rx="{h / 2 - 0.75}" '
                f'fill="{c["bg"]}" stroke="{c["line"]}" stroke-width="1.5"/>')
        mark(svg, margin + pad, 1 + (h - mw) / 2, mw)
        svg.text(margin + pad + mw + 10, 1 + h / 2 + 6.5, label, "small", size=18, fill=c["ink"])
        svg.save(f"chip-{name}")
    return build


def m_kadeep(svg, x, y, s):
    mark_kadeep_ai(svg, x, y, s)


def m_ks(svg, x, y, s):
    mark_ks(svg, x, y, s)


def m_github(svg, x, y, s):
    logo(svg, "github", x, y, s, svg.c["ink"])


def m_docs(svg, x, y, s):
    c = svg.c
    svg.add(f'<g fill="none" stroke="{c["ink"]}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round">'
            f'<path d="M{x + s * .2:g} {y + s * .1:g}h{s * .42:g}l{s * .2:g} {s * .2:g}v{s * .6:g}h-{s * .62:g}z"/>'
            f'<path d="M{x + s * .34:g} {y + s * .52:g}h{s * .32:g}M{x + s * .34:g} {y + s * .7:g}h{s * .24:g}"/></g>')


def m_linkedin(svg, x, y, s):
    k = s / 24
    c = svg.c
    svg.add(f'<g transform="translate({x:g} {y:g}) scale({k:g})"><rect width="24" height="24" rx="4" fill="{c["ink"]}"/>'
            f'<g fill="{c["bg"]}"><circle cx="6.1" cy="6.2" r="1.9"/><rect x="4.4" y="9.3" width="3.4" height="10.3"/>'
            '<path d="M10 9.3h3.25v1.5h.05c.45-.85 1.56-1.75 3.2-1.75 3.43 0 4.06 2.26 4.06 5.2v6h-3.38v-5.3'
            'c0-1.27-.02-2.9-1.77-2.9-1.76 0-2.03 1.38-2.03 2.8v5.4H10Z"/></g></g>')


def m_youtube(svg, x, y, s):
    c = svg.c
    svg.add(f'<rect x="{x:g}" y="{y + s * .16:g}" width="{s:g}" height="{s * .68:g}" rx="{s * .18:g}" fill="{c["ink"]}"/>'
            f'<path d="M{x + s * .4:g} {y + s * .34:g}L{x + s * .68:g} {y + s * .5:g}L{x + s * .4:g} {y + s * .66:g}Z" '
            f'fill="{c["bg"]}"/>')


# --------------------------------------------------------------------------- icons


def check_icon(svg, cx, cy, r, color, cls=""):
    c = f' class="{cls}"' if cls else ""
    svg.add(f'<g{c}><circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{color}" stroke-width="1.8"/>'
            f'<path d="M{cx - r * .42:.2f} {cy + r * .02:.2f}l{r * .3:.2f} {r * .3:.2f}l{r * .56:.2f} -{r * .62:.2f}" '
            f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>')


def cross_icon(svg, cx, cy, r, color, cls="", solid=True):
    c = f' class="{cls}"' if cls else ""
    a = r * 0.36
    svg.add(f'<g{c}><circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{color}"/>'
            f'<path d="M{cx - a:.2f} {cy - a:.2f}L{cx + a:.2f} {cy + a:.2f}M{cx + a:.2f} {cy - a:.2f}L{cx - a:.2f} {cy + a:.2f}" '
            f'stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></g>')


def pending_icon(svg, cx, cy, r, color):
    svg.add(f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{color}" stroke-width="1.6" '
            'stroke-dasharray="2.5 3.2"/>')


# --------------------------------------------------------------------------- every surface, every market, every release

LED_FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "-": ["....", "....", "....", "####", "....", "....", "...."],
    ".": [".", ".", ".", ".", ".", ".", "#"],
    " ": ["..", "..", "..", "..", "..", "..", ".."],
}


def led_cells(text: str):
    cells, col = [], 0
    for ch in text:
        glyph = LED_FONT[ch]
        cells += [(col + i, r) for r, row in enumerate(glyph) for i, v in enumerate(row) if v == "#"]
        col += len(glyph[0]) + 1
    return cells, col - 1


def every(theme: str):
    svg = Svg(W, 0, theme, "")
    c = svg.c
    svg.title = ("Every surface. Every market. Every release. An LED sign in KaDeep Studio's dots, each word "
                 "blinking in turn: blue, orange, then green. Web, mobile and desktop: the agent walks the live "
                 "product in the browser, on phones and in desktop apps. Every language you sell, checked on the live "
                 "screen. Release-ready, on demand: every build gets the same walk, with the evidence behind the "
                 "verdict.")
    # the sign
    sh = 360
    svg.defs.append(f'<clipPath id="sign"><rect width="{W}" height="{sh}" rx="24"/></clipPath>')
    svg.add(f'<g clip-path="url(#sign)"><rect width="{W}" height="{sh}" fill="{TILE}"/>')
    lines = ("EVERY SURFACE.", "EVERY MARKET.", "EVERY RELEASE.")
    pitch, gap_rows = 9.6, 4
    widths = [led_cells(t)[1] for t in lines]
    block_w = max(widths) * pitch
    block_h = (7 * 3 + gap_rows * 2) * pitch
    tx, ty = (W - block_w) / 2, (sh - block_h) / 2
    ox, oy = tx % pitch, ty % pitch
    svg.defs.append(f'<pattern id="led" patternUnits="userSpaceOnUse" x="{ox:.2f}" y="{oy:.2f}" width="{pitch:g}" '
                    f'height="{pitch:g}"><circle cx="{pitch / 2:g}" cy="{pitch / 2:g}" r="{pitch * .36:.2f}" '
                    'fill="#FFFFFF" fill-opacity="0.085"/></pattern>')
    svg.add(f'<rect width="{W}" height="{sh}" fill="url(#led)"/>')
    cycle = 6.6
    svg.css.append("@keyframes lit{0%{opacity:0}5%{opacity:1}29%{opacity:1}35%{opacity:0}100%{opacity:0}}"
                   f".lit{{opacity:0;animation:lit {cycle}s ease-in-out infinite}}")
    lead_cols = led_cells("EVERY ")[1] + 1
    colors = ("#3D8BFF", "#FF6A2B", "#2FE07A")     # surface blue, market orange, release green
    for k, (text, color) in enumerate(zip(lines, colors)):
        cells, _ = led_cells(text)
        pos = lambda cs: [(tx + (i + .5) * pitch, ty + (k * (7 + gap_rows) + r + .5) * pitch) for i, r in cs]
        head = [p for p in cells if p[0] < lead_cols]
        word = [p for p in cells if p[0] >= lead_cols]
        svg.dots(pos(head), pitch * .4, "#FFFFFF", .45)
        svg.dots(pos(word), pitch * .4, "#FFFFFF")
        svg.add(f'<g class="lit" style="animation-delay:{k * cycle / 3:.2f}s">')
        svg.dots(pos(word), pitch * .42, color)
        svg.add("</g>")
    svg.add("</g>")
    if theme == "dark":
        svg.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{sh - 1}" rx="24" fill="none" stroke="{c["line"]}"/>')

    # three columns
    cols = [
        ("Web, mobile and desktop.", "The agent walks the live product in the browser, on phones and in "
                                     "desktop apps."),
        ("Every language you sell.", "Each locale is checked on the live screen, so a market opens only when it "
                                     "really works."),
        ("Release-ready, on demand.", "Every build gets the same walk, with the steps, screenshots and video "
                                      "behind the verdict."),
    ]
    y = sh + 72
    colw = (W - 2 * 48) / 3
    for i, (head, body) in enumerate(cols):
        x = i * (colw + 48)
        svg.text(x, y, head, "bodym", size=25)
        svg.paragraph(x, y + 40, body, "body", colw - 16, 34, fill=c["muted"])

    svg.h = round(y + 40 + 2 * 34 + 14)
    svg.save("every")


# --------------------------------------------------------------------------- the readiness board

BOARD_ROWS = ["Sign up", "Search", "Checkout", "Account"]
BOARD_COLS = [("Web", 0), ("iOS", 0), ("Android", 0), ("Desktop", 0), ("German", 1), ("Japanese", 1), ("Arabic", 1)]
BOARD_FAIL = (2, 1)       # Checkout on iOS: one test fails
BOARD_WARN = (2, 6)       # Checkout in Arabic: at risk
BOARD_CYCLE = 13.0


def board(theme: str):
    """Every test is a dot: journeys by surface and market fill in, and the board reads HOLD."""
    svg = Svg(W, 0, theme, "")
    c = svg.c
    svg.title = ("A decision. Not a report. Every journey, every surface, one answer. An illustrative readiness "
                 "board drawn in dots: sign up, search, checkout and account, across web, iOS, Android, desktop, "
                 "German, Japanese and Arabic. Checkout fails on iOS and is at risk in Arabic, so the recommendation "
                 "is HOLD. Your release owner makes the call: proceed, hold or accept the risk.")
    svg.text(0, 64, "A decision. Not a report.", "h2")
    svg.text(0, 136, "Every journey, every surface, one answer.", "h2", fill=c["muted"])
    top, H_card = 196, 620
    svg.h = top + H_card + 2
    svg.add(f'<rect x="0.75" y="{top + 0.75}" width="{W - 1.5}" height="{H_card - 1.5}" rx="24" fill="{c["surface"]}" '
            f'stroke="{c["line"]}" stroke-width="1.5"/>')
    cyc = BOARD_CYCLE
    timing: dict = {}

    def cls_at(t, until=96):
        key = (round(t, 1), until)
        if key not in timing:
            name = f"t{len(timing)}"
            appear(svg, name, key[0], cyc, until=until)
            timing[key] = name
        return timing[key]

    # the grid: one cell per journey and surface or market, twelve tests per cell
    x0, lab_w = 56, 150
    cw, ch, gx, gy, split = 70, 82, 12, 14, 26
    gx0 = x0 + lab_w
    col_x = [gx0 + i * (cw + gx) + grp * split for i, (_, grp) in enumerate(BOARD_COLS)]
    hy = top + 96
    svg.text(col_x[0], hy - 34, "SURFACES", "label", fill=c["faint"])
    svg.text(col_x[4], hy - 34, "MARKETS", "label", fill=c["faint"])
    for (name, _), x in zip(BOARD_COLS, col_x):
        svg.text(x + cw / 2, hy, name, "small", size=16, fill=c["muted"], anchor="middle")
    gy0 = hy + 22
    pitch, dr = 14, 4.1
    t_last = 0.0
    for r, row in enumerate(BOARD_ROWS):
        y = gy0 + r * (ch + gy)
        svg.text(x0, y + ch / 2 + 7, row, "bodym", size=20)
        for ci, x in enumerate(col_x):
            state = "fail" if (r, ci) == BOARD_FAIL else "warn" if (r, ci) == BOARD_WARN else "ok"
            svg.add(f'<rect x="{x + .5}" y="{y + .5}" width="{cw - 1}" height="{ch - 1}" rx="12" fill="{c["bg"]}" '
                    f'stroke="{c["line"]}"/>')
            pts = [(x + cw / 2 + (i - 1.5) * pitch, y + ch / 2 + (j - 1) * pitch) for j in range(3) for i in range(4)]
            svg.dots(pts, dr, c["line2"], 0.55)
            base = 3 + ci * 4.0 + r * 2.6
            for j in range(3):
                t = base + j * 1.4
                t_last = max(t_last, t)
                row_pts = pts[j * 4:(j + 1) * 4]
                k = cls_at(t)
                if state == "fail" and j == 2:
                    svg.dots(row_pts[:3], dr, c["ok"], cls=k)
                    svg.dots(row_pts[3:], dr + .6, c["bad"], cls=k)
                elif state == "warn" and j == 2:
                    svg.dots(row_pts[:2], dr, c["ok"], cls=k)
                    svg.dots(row_pts[2:], dr + .3, c["warn"], cls=k)
                else:
                    svg.dots(row_pts, dr, c["ok"], cls=k)
            if state != "ok":
                col = c["bad"] if state == "fail" else c["warn"]
                svg.add(f'<rect class="{cls_at(base + 2 * 1.4)}" x="{x + 1}" y="{y + 1}" width="{cw - 2}" '
                        f'height="{ch - 2}" rx="11.5" fill="none" stroke="{col}" stroke-width="2"/>')
    # legend
    ly = gy0 + 4 * (ch + gy) + 26
    lx = gx0
    for col, word in ((c["ok"], "Ready"), (c["warn"], "At risk"), (c["bad"], "Not ready"), (c["line2"], "Not run yet")):
        svg.dots([(lx + 6, ly - 6)], 5, col)
        svg.text(lx + 20, ly, word, "small", size=16, fill=c["muted"])
        lx += 20 + measure(word, "small", 16) + 28

    # the recommendation
    px = 846
    svg.add(f'<line x1="{px - 30}" x2="{px - 30}" y1="{top + 40}" y2="{top + H_card - 40}" stroke="{c["line"]}"/>')
    svg.text(px, top + 62, "RECOMMENDATION", "label", fill=c["faint"])
    t_v = t_last + 5
    cells, _ = led_cells("HOLD")
    p = 13
    vy = top + 88
    hold = [(px + (i + .5) * p, vy + (r_ + .5) * p) for i, r_ in cells]
    svg.dots(hold, p * .42, c["line2"], .5)
    svg.add(f'<g class="{cls_at(t_v)}">')
    svg.dots(hold, p * .42, c["bad"])
    svg.add("</g>")
    reasons = [
        (c["bad"], "Checkout on iOS", "The saved card isn’t selected, so Pay stays disabled."),
        (c["warn"], "Checkout in Arabic", "The page still reads left to right."),
        (c["ok"], "Everything else", "Ready, with evidence for every step."),
    ]
    ry = vy + 7 * p + 62
    for i, (col, head, body) in enumerate(reasons):
        svg.add(f'<g class="{cls_at(t_v + 4 + i * 3)}">')
        svg.dots([(px + 6, ry - 7)], 5.5, col)
        svg.text(px + 22, ry, head, "bodym", size=20)
        svg.paragraph(px + 22, ry + 28, body, "body", 330, 26, fill=c["muted"], size=17)
        svg.add("</g>")
        ry += 92
    # the call stays with a person
    by = top + H_card - 112
    svg.add(f'<g class="{cls_at(t_v + 14)}">')
    svg.text(px, by, "Your release owner makes the call.", "small", size=17, fill=c["muted"])
    bx = px
    for word, on in (("Proceed", False), ("Hold", True), ("Accept the risk", False)):
        w = measure(word, "bodym", 17) + 32
        if on:
            svg.add(f'<rect x="{bx}" y="{by + 18}" width="{w:.1f}" height="38" rx="19" fill="{c["btn"]}"/>')
        else:
            svg.add(f'<rect x="{bx + .75}" y="{by + 18.75}" width="{w - 1.5:.1f}" height="36.5" rx="18.25" '
                    f'fill="{c["bg"]}" stroke="{c["line2"]}" stroke-width="1.5"/>')
        svg.text(bx + 16, by + 43, word, "bodym", size=17, fill=c["btn_ink"] if on else c["ink"])
        bx += w + 10
    svg.add("</g>")
    svg.text(W - 40, top + 62, "Illustrative", "small", size=15, fill=c["faint"], anchor="end")
    svg.save("board")


# --------------------------------------------------------------------------- your model, your tools

MODELS = [("claude", "Claude"), ("openai-mark", "OpenAI"), ("gemini", "Gemini"), ("cursor", "Cursor")]
TOOLS = [("jira", "Jira"), ("slack", "Slack"), ("linear", "Linear"), ("github", "GitHub")]


def hub(theme: str):
    svg = Svg(W, 0, theme, "")
    c = svg.c
    svg.title = ("Your model. Your tools. Bring your key. Keep your workflow. KaDeep Studio runs on the model key you already pay for, or the coding "
                 "agent already on your machine: Claude, OpenAI, Gemini, Cursor and more. It files what it finds where your team already works: Jira, Slack, Linear, "
                 "GitHub and more. Dots flow from each model into the KaDeep Studio tile and out to each tool.")
    svg.text(0, 64, "Your model. Your tools.", "h2")
    svg.text(0, 136, "Bring your key. Keep your workflow.", "h2", fill=c["muted"])
    top, H = 210, 500
    svg.h = top + H
    cx, cy, ts = W / 2, top + H / 2 - 20, 150
    cardw, cardh = 220, 76

    def card(x, y, name, word):
        svg.add(f'<rect x="{x + .75}" y="{y + .75}" width="{cardw - 1.5}" height="{cardh - 1.5}" rx="18" '
                f'fill="{c["surface"]}" stroke="{c["line"]}" stroke-width="1.5"/>')
        logo_color(svg, name, x + 24, y + (cardh - 34) / 2, 34)
        svg.text(x + 74, y + cardh / 2 + 8, word, "bodym", size=23)

    svg.css.append("@keyframes flow{to{stroke-dashoffset:-40}}.flow{animation:flow 1.1s linear infinite}"
                   "@keyframes ring{0%{opacity:.6;transform:scale(1)}100%{opacity:0;transform:scale(1.4)}}"
                   ".ring{opacity:0;transform-box:fill-box;transform-origin:center;animation:ring 2.4s ease-out infinite}")

    def wire(x1, y1, x2, y2, delay):
        mx = (x1 + x2) / 2
        d = f"M{x1:g} {y1:g}C{mx:g} {y1:g} {mx:g} {y2:g} {x2:g} {y2:g}"
        svg.add(f'<path d="{d}" fill="none" stroke="{c["line"]}" stroke-width="2"/>')
        svg.add(f'<path class="flow" style="animation-delay:{delay:.2f}s" d="{d}" fill="none" stroke="{c["blue"]}" '
                'stroke-width="5" stroke-linecap="round" stroke-dasharray="0 20"/>')

    lx = 24
    ys = [cy + (i - 1.5) * 96 - cardh / 2 for i in range(4)]
    for i, y in enumerate(ys):
        wire(lx + cardw, y + cardh / 2, cx - ts / 2 - 6, cy + (i - 1.5) * 22, -i * .37)
    rx = W - 24 - cardw
    ys2 = [cy + (i - 1.5) * 96 - cardh / 2 for i in range(4)]
    for i, y in enumerate(ys2):
        wire(cx + ts / 2 + 6, cy + (i - 1.5) * 22, rx, y + cardh / 2, -i * .29)
    for (n, w), y in zip(MODELS, ys):
        card(lx, y, n, w)
    for (n, w), y in zip(TOOLS, ys2):
        card(rx, y, n, w)
    svg.text(lx + cardw / 2, ys2[0] - 26, "YOUR MODEL OR AGENT", "label", fill=c["faint"], anchor="middle")
    svg.text(lx + cardw / 2, ys[-1] + cardh + 40, "and more", "small", size=18, fill=c["muted"], anchor="middle")
    svg.text(rx + cardw / 2, ys2[0] - 26, "WHERE YOUR TEAM WORKS", "label", fill=c["faint"], anchor="middle")
    svg.text(rx + cardw / 2, ys2[-1] + cardh + 40, "and more", "small", size=18, fill=c["muted"], anchor="middle")

    svg.add(f'<rect class="ring" x="{cx - ts / 2}" y="{cy - ts / 2}" width="{ts}" height="{ts}" rx="{0.224 * ts:.1f}" '
            f'fill="none" stroke="{c["blue"]}" stroke-width="2"/>')
    mark_ks(svg, cx - ts / 2, cy - ts / 2, ts)
    svg.text(cx, cy + ts / 2 + 44, "KaDeep Studio", "bodym", size=23, anchor="middle")
    svg.save("hub")


# --------------------------------------------------------------------------- release gate

GATE_CYCLE = 13.0


def gate(theme: str):
    svg = Svg(W, 0, theme, "")
    c = svg.c
    svg.title = ("In your pipeline, too. A go or no-go on every pull request. KaDeep Release Gate is open source "
                 "under Apache-2.0: run npx kadeep. Beside it, a terminal: twelve smoke tests pass, one checkout test "
                 "fails with a defect, and the verdict reads NO-GO in red dots.")
    svg.text(0, 64, "In your pipeline, too.", "h2")
    svg.text(0, 136, "A go or no-go on every pull request.", "h2", fill=c["muted"])
    top = 196
    H_card = 560
    svg.h = top + H_card + 2
    svg.add(f'<rect x="0.75" y="{top + 0.75}" width="{W - 1.5}" height="{H_card - 1.5}" rx="24" fill="{c["surface"]}" '
            f'stroke="{c["line"]}" stroke-width="1.5"/>')

    x = 56
    y = top + 82
    mark_ks(svg, x, y - 32, 42)
    svg.text(x + 56, y - 2, "KaDeep Release Gate", "name", size=28)
    svg.text(x, y + 46, "Open source  ·  Apache-2.0", "small", fill=c["muted"])
    end = svg.paragraph(x, y + 110, "Add one step to your pipeline. KaDeep Studio runs the checks your policy names "
                        "for that commit, and the build passes or stops with the reasons.", "body", 440, 35)
    svg.paragraph(x, end + 58, "GitHub Actions, GitLab CI, CircleCI, Jenkins and more. Claude Code and Cursor can "
                  "run it too.", "body", 440, 35, fill=c["muted"])
    # the command
    cmd_y = top + H_card - 116
    cw = 250
    svg.add(f'<rect x="{x}" y="{cmd_y}" width="{cw}" height="56" rx="14" fill="{c["bg"]}" stroke="{c["line2"]}"/>')
    svg.runs(x + 22, cmd_y + 35, [("$ ", c["faint"]), ("npx kadeep", c["ink"])], "mono", size=21)

    # the terminal, black in both themes
    tx, ty, tw = 560, top + 48, 664
    th = H_card - 96
    window_shadow(svg, "tshadow")
    svg.defs.append(f'<clipPath id="term"><rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="14"/></clipPath>')
    svg.add(f'<g filter="url(#tshadow)"><rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="14" fill="{TERM["bg"]}"/></g>')
    svg.add(f'<g clip-path="url(#term)"><rect x="{tx}" y="{ty}" width="{tw}" height="38" fill="{TERM["bar"]}"/></g>')
    for k in range(3):
        svg.add(f'<circle cx="{tx + 22 + k * 20}" cy="{ty + 19}" r="6" fill="#3a3a3a"/>')
    svg.text(tx + tw / 2, ty + 25, "npx releasegate", "mono", size=14, fill=TERM["muted"], anchor="middle")
    svg.add(f'<rect x="{tx + .5}" y="{ty + .5}" width="{tw - 1}" height="{th - 1}" rx="14" fill="none" '
            f'stroke="{"#2a2a2a" if theme == "dark" else "#0a0a0a"}"/>')

    mx = tx + 28
    fs = 16
    lh = 27
    yy = ty + 76
    svg.runs(mx, yy, [("KaDeep Release Gate 0.3.0", TERM["ink"]), (" · Engineering release confidence.", TERM["muted"])],
             "monob", size=fs)
    svg.text(mx, yy + lh, "commit 8c3f2d1 on feature/checkout · PR #214 · enforce", "mono", size=fs, fill=TERM["muted"])

    # smoke: twelve dots, then the line
    t0, dt = 6, 1.6
    yy += lh * 2 + 8
    dot_x = mx + 4
    svg.text(mx, yy, "Smoke", "mono", size=fs, fill=TERM["ink"])
    for i in range(12):
        appear(svg, f"d{i}", t0 + i * dt, GATE_CYCLE)
        svg.dots([(mx + 150 + i * 16, yy - 5)], 5, TERM["ok"], cls=f"d{i}")
    t_smoke = t0 + 12 * dt
    appear(svg, "sm", t_smoke, GATE_CYCLE)
    svg.text(mx + 150 + 12 * 16 + 14, yy, "12/12  2m 41s", "mono", size=fs, fill=TERM["muted"], extra='class="sm"')

    yy += lh + 4
    svg.text(mx, yy, "Checkout", "mono", size=fs, fill=TERM["ink"])
    t1 = t_smoke + 4
    for i in range(4):
        appear(svg, f"e{i}", t1 + i * 2.4, GATE_CYCLE)
        svg.dots([(mx + 150 + i * 16, yy - 5)], 5, TERM["bad"] if i == 3 else TERM["ok"], cls=f"e{i}")
    t_co = t1 + 4 * 2.4
    appear(svg, "co", t_co, GATE_CYCLE)
    svg.text(mx + 150 + 4 * 16 + 14, yy, "3/4  1m 05s", "mono", size=fs, fill=TERM["muted"], extra='class="co"')
    yy += lh + 4
    svg.runs(mx + 20, yy, [("Pay by card ", TERM["ink"]), ("DEFECT", TERM["bad"]),
                           (" Expected “Order placed”", TERM["muted"])], "mono", size=fs, extra='class="co"')

    # the verdict in big dots
    t_v = t_co + 8
    appear(svg, "nogo", t_v, GATE_CYCLE)
    cells, cols = led_cells("NO-GO")
    p = 12.5
    vy0 = yy + 36
    svg.add('<g class="nogo">')
    svg.dots([(mx + (i + .5) * p, vy0 + (r + .5) * p) for i, r in cells], p * .38, TERM["bad"])
    svg.add("</g>")
    svg.text(mx, vy0 + 7 * p + 40, "1/2 required checks passed · 3m 47s", "mono", size=fs, fill=TERM["ink"],
             extra='class="nogo"')
    svg.save("gate")


# --------------------------------------------------------------------------- close

CLOSE_LINE = "Bring your next release. Leave knowing whether it ships."


def close(theme: str):
    svg = Svg(W, 330, theme, f"On your product. Not a deck. {CLOSE_LINE} ISO/IEC 27001:2022 and ISO 9001:2015 certified. Passkeys, SCIM and a searchable audit log.")
    c = svg.c
    svg.text(W / 2, 86, "On your product.", "display", size=88, anchor="middle")
    svg.text(W / 2, 184, "Not a deck.", "display", size=88, anchor="middle", fill=c["muted"])
    svg.text(W / 2, 252, CLOSE_LINE, "lede", size=28,
             anchor="middle", fill=c["ink"])
    svg.text(W / 2, 306, "ISO/IEC 27001:2022 and ISO 9001:2015 certified. Passkeys, SCIM and a searchable audit log.",
             "small", size=19, anchor="middle", fill=c["muted"])
    svg.save("close")


# --------------------------------------------------------------------------- main

BUILDERS = {
    "hero": hero,
    "btn-sample": button("sample", "Watch a sample run", "primary", play=True,
                         alt="Watch a sample run: a real KaDeep Studio check, no sign-in"),
    "btn-launch": button("launch", "Launch KaDeep™ Studio Pro", "secondary", lead=m_ks,
                         alt="Launch KaDeep Studio Pro"),
    "btn-walkthrough": button("walkthrough", "Book a walkthrough", "secondary", alt="Book a walkthrough"),
    "board": board,
    "every": every,
    "hub": hub,
    "gate": gate,
    "btn-repo": button("repo", "kadeep-ai/kadeep-cli", "secondary", lead=m_github,
                       alt="kadeep-ai/kadeep-cli on GitHub"),
    "close": close,
    "btn-book": button("book", "Book a walkthrough", "primary", alt="Book a walkthrough"),
    "btn-open": button("open", "Open Studio", "secondary", lead=m_ks, alt="Open KaDeep Studio"),
    "chip-site": chip("site", "kadeep.ai", m_kadeep),
    "chip-docs": chip("docs", "Docs", m_docs),
    "chip-linkedin": chip("linkedin", "LinkedIn", m_linkedin),
    "chip-youtube": chip("youtube", "YouTube", m_youtube),
}


def main(argv):
    names = argv or list(BUILDERS)
    for theme in THEMES:
        for name in names:
            BUILDERS[name](theme)


if __name__ == "__main__":
    main(sys.argv[1:])

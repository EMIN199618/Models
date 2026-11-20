import math, sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

F = "fonts/"  # CinzelVar.ttf + CormVar.ttf (Google Fonts, OFL)
OUT = "./"
cinzel = instantiateVariableFont(TTFont(F+"CinzelVar.ttf"), {"wght": 440})
corm = instantiateVariableFont(TTFont(F+"CormVar.ttf"), {"wght": 500})

def text_path(font, text, size, x, y, tracking=0.0, anchor="middle"):
    """Return (svg path d, width). y = baseline. tracking in em."""
    gs = font.getGlyphSet(); cmap = font.getBestCmap(); upm = font["head"].unitsPerEm
    s = size/upm
    names = [cmap[ord(c)] for c in text]
    adv = [font["hmtx"][n][0]*s for n in names]
    w = sum(adv) + tracking*size*(len(text)-1)
    cx = {"middle": x - w/2, "start": x, "end": x - w}[anchor]
    pen = SVGPathPen(gs)
    for n, a in zip(names, adv):
        tp = TransformPen(pen, (s, 0, 0, -s, cx, y))
        gs[n].draw(tp); cx += a + tracking*size
    return pen.getCommands(), w

def glyph_bounds(font, ch, size):
    gs = font.getGlyphSet(); n = font.getBestCmap()[ord(ch)]; s = size/font["head"].unitsPerEm
    bp = BoundsPen(gs); gs[n].draw(bp); b = bp.bounds
    return [v*s for v in b], font["hmtx"][n][0]*s

GOLD = """<linearGradient id="gold" x1="0" y1="0" x2="1" y2="1" gradientUnits="objectBoundingBox">
  <stop offset="0" stop-color="#8A6A2E"/><stop offset=".28" stop-color="#E9D08F"/>
  <stop offset=".5" stop-color="#B48D3E"/><stop offset=".72" stop-color="#F4E4AE"/>
  <stop offset="1" stop-color="#93702F"/></linearGradient>"""

def star_frame(cx, cy, r, sw):
    """Eight-pointed star: two squares rotated 45deg, plus inner octagon ring."""
    out = []
    for rot in (0, 45):
        pts = []
        for k in range(4):
            a = math.radians(rot + 45 + 90*k)
            pts.append(f"{cx + r*math.cos(a):.2f},{cy + r*math.sin(a):.2f}")
        out.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="url(#goldU)" stroke-width="{sw}" stroke-linejoin="miter"/>')
    return "\n".join(out)

def monogram(cx, cy, size):
    (bx0, by0, bx1, by1), _ = glyph_bounds(corm, "B", size)
    (px0, py0, px1, py1), _ = glyph_bounds(corm, "P", size)
    gap = size*0.04
    total = (bx1-bx0) + gap + (px1-px0)
    base = cy + (by1-by0)/2
    x = cx - total/2
    dB, _ = text_path(corm, "B", size, x - bx0, base, anchor="start")
    dP, _ = text_path(corm, "P", size, x + (bx1-bx0) + gap - px0, base, anchor="start")
    return dB, dP

def emblem(cx, cy, R, bg):
    sw = R*0.018
    parts = [star_frame(cx, cy, R, sw)]
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{R*0.70:.2f}" fill="none" stroke="url(#goldU)" stroke-width="{sw*0.7:.2f}"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{R*0.66:.2f}" fill="none" stroke="url(#goldU)" stroke-width="{sw*0.35:.2f}"/>')
    dB, dP = monogram(cx, cy, R*0.62)
    # knock-out stroke so the overlap reads as interlaced
    parts.append(f'<path d="{dB}" fill="url(#gold)"/>')
    parts.append(f'<path d="{dP}" fill="url(#gold)"/>')
    return "\n".join(parts)

def wordmark(cx, y, size, rule=True):
    d, w = text_path(cinzel, "BAKI PRIVÉ", size, cx, y, tracking=0.22)
    out = [f'<path d="{d}" fill="url(#goldH)"/>']
    if rule:
        ry = y + size*0.55
        out.append(f'<line x1="{cx-w*0.32:.1f}" y1="{ry:.1f}" x2="{cx-size*0.35:.1f}" y2="{ry:.1f}" stroke="#C9A75A" stroke-width="{size*0.025:.2f}"/>')
        out.append(f'<line x1="{cx+size*0.35:.1f}" y1="{ry:.1f}" x2="{cx+w*0.32:.1f}" y2="{ry:.1f}" stroke="#C9A75A" stroke-width="{size*0.025:.2f}"/>')
        s = size*0.12
        out.append(f'<rect x="{cx-s/2:.2f}" y="{ry-s/2:.2f}" width="{s:.2f}" height="{s:.2f}" transform="rotate(45 {cx} {ry:.2f})" fill="#E2C67F"/>')
    return "\n".join(out), w

def svg(w, h, body, bg, title):
    defs = GOLD + GOLD.replace('id="gold"', 'id="goldU"').replace('gradientUnits="objectBoundingBox"', f'gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{w}" y2="{h}"').replace('x1="0" y1="0" x2="1" y2="1" ', '') \
        + GOLD.replace('id="gold"', 'id="goldH"').replace('x2="1" y2="1"', 'x2="1" y2="0"')
    if bg is None or not bg.startswith("#"): rect = ""
    else: rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{title}">\n<title>{title}</title>\n<defs>{defs}</defs>\n{rect}\n{body}\n</svg>\n'

def flat(s, color):
    for g in ("url(#gold)", "url(#goldU)", "url(#goldH)"): s = s.replace(g, color)
    return s

DARK = "#0C0B0A"; IVORY = "#F6F1E7"
variants = {}
# primary stacked
W, H = 1200, 1200
body = emblem(600, 470, 300, DARK) + "\n" + wordmark(600, 965, 92)[0]
variants["baki-prive-primary-dark.svg"] = svg(W, H, body, DARK, "Bakı Privé")
body_l = emblem(600, 470, 300, IVORY) + "\n" + wordmark(600, 965, 92)[0]
variants["baki-prive-primary-light.svg"] = svg(W, H, body_l, IVORY, "Bakı Privé").replace("#E9D08F","#B8913F").replace("#F4E4AE","#C9A24E").replace("#B48D3E","#8E6A26").replace("#8A6A2E","#6E5120").replace("#93702F","#755622").replace("#C9A75A","#9C7A36").replace("#E2C67F","#9C7A36")
# horizontal
d, ww = text_path(cinzel, "BAKI PRIVÉ", 84, 500, 240 + 84*0.35, tracking=0.22, anchor="start")
W2, H2 = int(500 + ww + 110), 480
hbody = emblem(250, 240, 175, DARK) + f'\n<path d="{d}" fill="url(#goldH)"/>' \
    + f'\n<line x1="502" y1="{240+84*0.35+38:.0f}" x2="{500+ww:.0f}" y2="{240+84*0.35+38:.0f}" stroke="#C9A75A" stroke-width="1.6"/>'
variants["baki-prive-horizontal-dark.svg"] = svg(W2, H2, hbody, DARK, "Bakı Privé")
# monogram / app icon
variants["baki-prive-monogram.svg"] = svg(512, 512, emblem(256, 256, 220, DARK), DARK, "Bakı Privé monogram")
# single-colour versions (print, embossing, foil)
variants["baki-prive-mono-black.svg"] = flat(svg(1200, 1200, emblem(600,470,300,"#FFFFFF")+"\n"+wordmark(600,965,92)[0], "#FFFFFF", "Bakı Privé"), "#111111")
variants["baki-prive-mono-white.svg"] = flat(svg(1200, 1200, emblem(600,470,300,"#000000")+"\n"+wordmark(600,965,92)[0], "#000000", "Bakı Privé"), "#FFFFFF")
for k, v in variants.items():
    open(OUT+k, "w").write(v)
print("ok", list(variants))

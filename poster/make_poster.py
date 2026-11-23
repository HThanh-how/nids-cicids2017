# Generates poster.html (A0 portrait, 841 x 1189 mm). Light "analytics dashboard" variant:
# soft gradient page, rounded white cards, KPI strip, IBM Plex Sans. Two data colours only
# (blue = random split, vermilion = day-disjoint / failure); teal is a tiny "ok" hint (not used for data).
# Inline SVG + inline base64 IBM Plex Sans (poster/fonts/*.woff2), no JS, no network.
# Every number and sentence is copied from the editorial poster; only the design changed.
#
#   py make_poster_dash.py          -> poster.html
#   py make_poster_dash.py --all    -> + SOICT2026_9222_poster_A0.pdf / .pptx (Chrome + pdftocairo + python-pptx)
import base64, html, math, pathlib, subprocess, sys, tempfile

import segno

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'poster.html'
PDF = HERE / 'SOICT2026_9222_poster_A0.pdf'
PPTX = HERE / 'SOICT2026_9222_poster_A0.pptx'
FONT_DIR = HERE / 'fonts'
FONT_FILES = [('IBM Plex Sans', 'ibm-plex-sans', (400, 500, 600, 700))]

INK, GREY, RULE = '#17202a', '#566271', '#dbe3ee'
BLUE, VERM, TEAL = '#1f5a8f', '#d4471a', '#2a9d8f'
GRID = '#d3dce9'     # gridlines on the soft plot panel
MID = '#aab3ba'      # neutral marks
e = html.escape


# ---------------------------------------------------------------- svg helpers
def svg(w, h, body, label, extra=''):
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{e(label)}" {extra}>{body}</svg>')


def t(x, y, s, size=34, fill=INK, anchor='start', weight=400, serif=False, extra=''):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" {extra}>{e(s)}</text>')


def rect(x, y, w, h, fill, extra=''):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" {extra}/>'


def bar(x, y, w, h, fill, r=12):
    """bar with rounded top corners"""
    r = min(r, h / 2, w / 2)
    return (f'<path d="M{x:.1f} {y + h:.1f} L{x:.1f} {y + r:.1f} Q{x:.1f} {y:.1f} {x + r:.1f} {y:.1f} '
            f'L{x + w - r:.1f} {y:.1f} Q{x + w:.1f} {y:.1f} {x + w:.1f} {y + r:.1f} L{x + w:.1f} {y + h:.1f} Z" fill="{fill}"/>')


def line(x1, y1, x2, y2, c=GRID, sw=2, dash=''):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{sw}"{d}/>'


def arrow_down(x, y1, y2, c, sw=6, head=30):
    return (line(x, y1, x, y2 - 4, c, sw) +
            f'<path d="M{x - head*0.62:.1f} {y2 - head:.1f} L{x:.1f} {y2:.1f} L{x + head*0.62:.1f} {y2 - head:.1f}" '
            f'fill="none" stroke="{c}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')


def arrow_h(x, y, w, c, sw=5, head=16):
    return (line(x, y, x + w - 2, y, c, sw) +
            f'<path d="M{x + w - head:.1f} {y - head*0.8:.1f} L{x + w:.1f} {y:.1f} L{x + w - head:.1f} {y + head*0.8:.1f}" '
            f'fill="none" stroke="{c}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')


def pcol(y, ytop, ybot):
    """colour of the soft plot-panel gradient (#e4edf8 -> #fbfcff) at height y, for text halos"""
    f = max(0, min(1, (y - ytop) / (ybot - ytop)))
    a, b = (0xe4, 0xed, 0xf8), (0xfb, 0xfc, 0xff)
    return '#%02x%02x%02x' % tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


def sw_(s, size):
    return len(s) * 0.56 * size


def AR(c='currentColor'):
    return (f'<svg class="ar" viewBox="0 0 100 50" aria-hidden="true"><path d="M2 25H94M70 5L96 25L70 45" fill="none" '
            f'stroke="{c}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>')


# gradients referenced by url(#..) from every inline svg (one shared hidden defs block)
DEFS = f'''<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<linearGradient id="gB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f78b4"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>
<linearGradient id="gV" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e8613a"/><stop offset="1" stop-color="{VERM}"/></linearGradient>
<linearGradient id="gP" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e4edf8"/><stop offset="1" stop-color="#fbfcff"/></linearGradient>
</defs></svg>'''


# ---------------------------------------------------------------- HERO: recall random vs day-disjoint
def recall_chart():
    W, H = 2034, 882
    models = [('LogReg', .9100, .4975, '0.1010', '0.0592'), ('RF', .9937, .3109, '0.0076', '0.0029'),
              ('XGBoost', .9935, .3164, '0.0073', '0.0030'), ('MLP', .9857, .3467, '0.0359', '0.0211')]
    ph = 540
    x0, y0 = 130, 180 + ph
    bw, gap = 160, 34
    xr = W - 8
    pitch = (xr - x0) / 4
    gw = 2 * bw + gap
    b = [f'<rect x="{x0}" y="100" width="{xr - x0}" height="{y0 - 100}" rx="22" fill="url(#gP)"/>']
    for k in (.25, .5, .75, 1):
        yy = y0 - ph * k
        b.append(line(x0, yy, xr, yy, GRID, 2))
        b.append(t(x0 - 22, yy + 12, f'{k:.2f}', 34, GREY, 'end'))
    b.append(line(x0, y0, xr, y0, INK, 2.5))
    b.append(t(x0 - 22, y0 + 12, '0.00', 34, GREY, 'end'))
    b.append(t(x0 - 22, 68, 'recall', 36, GREY, 'end'))
    # legend row = direct series labels, kept clear of every bar and value
    b.append(rect(x0, 38, 34, 34, 'url(#gB)', 'rx="9"'))
    b.append(t(x0 + 50, 68, 'random split', 46, BLUE, 'start', 600))
    b.append(rect(x0 + 420, 38, 34, 34, 'url(#gV)', 'rx="9"'))
    b.append(t(x0 + 470, 68, 'day-disjoint split', 46, VERM, 'start', 600))
    gx = [x0 + i * pitch + (pitch - gw) / 2 for i in range(4)]
    for i, (m, r, d, f1, f2) in enumerate(models):
        xa = gx[i]
        xb = xa + bw + gap
        hr, hd = ph * r, ph * d
        b.append(bar(xa, y0 - hr, bw, hr, 'url(#gB)'))
        halo = lambda yy: f'paint-order="stroke" stroke="{pcol(yy, 100, y0)}" stroke-width="12" stroke-linejoin="round"'
        b.append(t(xa + bw / 2, y0 - hr - 18, f'{r:.4f}', 58, BLUE, 'middle', 700, extra=halo(y0 - hr - 40)))
        b.append(bar(xb, y0 - hd, bw, hd, 'url(#gV)'))
        b.append(t(xb + bw / 2, y0 - hd - 18, f'{d:.4f}', 58, VERM, 'middle', 700, extra=halo(y0 - hd - 40)))
        cx = (xa + xb + bw) / 2
        b.append(t(cx, y0 + 70, m, 50, INK, 'middle', 600))
        s1, s2 = f'FPR {f1}', f2
        wtot = sw_(s1, 36) + 70 + sw_(s2, 36)
        sx = cx - wtot / 2
        b.append(t(sx, y0 + 128, s1, 36, GREY))
        b.append(arrow_h(sx + sw_(s1, 36) + 14, y0 + 116, 42, GREY, 3.5, 12))
        b.append(t(sx + sw_(s1, 36) + 70, y0 + 128, s2, 36, GREY))
    # the one annotation: 0.99 -> 0.32 (XGBoost)
    xa, xb = gx[2], gx[2] + bw + gap
    ytop = y0 - ph * .9935
    cxv = xb + bw / 2
    b.append(line(xa + bw + 6, ytop, cxv + 44, ytop, VERM, 2.5, '10 8'))
    ay = ytop + 60
    sz = 50
    wnum = 3 * .6 * sz + .27 * sz
    tw = 2 * wnum + 74
    x = cxv - tw / 2 + 44
    b.append(t(x, ay + 50, '0.99', sz, VERM, 'start', 700))
    b.append(arrow_h(x + wnum + 14, ay + 28, 46, VERM, 5, 15))
    b.append(t(x + wnum + 74, ay + 50, '0.32', sz, VERM, 'start', 700))
    b.append(arrow_down(cxv + 44, ay + 84, y0 - ph * .3164 - 92, VERM, 6, 30))
    return svg(W, H, ''.join(b), 'Attack recall under both protocols, four models')


# ---------------------------------------------------------------- slope chart: macro-F1 ranking (enlarged)
def slope():
    W, H = 890, 462
    data = [('XGBoost', .9879, .6887), ('RF', .9874, .6852), ('MLP', .9491, .6928), ('LogReg', .8515, .7433)]
    xl, xr, top, bot = 352, 560, 110, 352
    lo, hi = .64, 1.0

    def Y(v):
        return bot - (v - lo) / (hi - lo) * (bot - top)

    def spread(items, gap=42):
        items = sorted(items, key=lambda a: a[1])
        out, last = {}, -1e9
        for k, y in items:
            y = max(y, last + gap)
            out[k] = y
            last = y
        return out

    ly = spread([(m, Y(a)) for m, a, d in data])
    ry = spread([(m, Y(d)) for m, a, d in data])
    b = [f'<rect x="0" y="62" width="{W}" height="{H - 70}" rx="20" fill="url(#gP)"/>']
    b += [t(xl, 44, 'random', 38, BLUE, 'middle', 600), t(xr, 44, 'day-disjoint', 38, VERM, 'middle', 600)]
    b.append(line(xl, 76, xl, bot + 14, '#c3cfdf', 2) + line(xr, 76, xr, bot + 14, '#c3cfdf', 2))
    for m, a, d in data:
        hot = m == 'LogReg'
        c = INK if hot else MID
        b.append(f'<line x1="{xl}" y1="{Y(a):.1f}" x2="{xr}" y2="{Y(d):.1f}" stroke="{c}" stroke-width="{6 if hot else 4}" stroke-linecap="round"/>')
        r = 12 if hot else 9
        # leader from the point to the (spread) label
        pa, pd = Y(a), Y(d)
        b.append(f'<path d="M{xl - 14} {pa:.1f} L{xl - 30} {pa:.1f} L{xl - 42} {ly[m]:.1f} L{xl - 52} {ly[m]:.1f}" fill="none" stroke="{MID}" stroke-width="2.5"/>')
        b.append(f'<path d="M{xr + 14} {pd:.1f} L{xr + 30} {pd:.1f} L{xr + 42} {ry[m]:.1f} L{xr + 52} {ry[m]:.1f}" fill="none" stroke="{MID}" stroke-width="2.5"/>')
        b.append(f'<circle cx="{xl}" cy="{pa:.1f}" r="{r}" fill="{BLUE}" stroke="#fff" stroke-width="3"/><circle cx="{xr}" cy="{pd:.1f}" r="{r}" fill="{VERM}" stroke="#fff" stroke-width="3"/>')
        w_ = 600 if hot else 400
        col = INK if hot else GREY
        b.append(t(xl - 60, ly[m] + 12, f'{m} {a:.4f}', 34, col, 'end', w_))
        b.append(t(xr + 60, ry[m] + 12, f'{d:.4f} {m}', 34, col, 'start', w_))
    return svg(W, H, ''.join(b), 'Macro-F1 ranking inversion')


# ---------------------------------------------------------------- significance: interval around zero
def interval():
    W, H = 890, 462
    lo, hi = -.0004, .0014
    xa, xb = 96, 806

    def X(v):
        return xa + (v - lo) / (hi - lo) * (xb - xa)
    ya = 330
    b = [f'<rect x="0" y="8" width="{W}" height="{H - 8}" rx="20" fill="url(#gP)"/>', line(xa, ya, xb, ya, INK, 2.5)]
    for v, s in ((-.0004, '−0.0004'), (0, '0'), (.0004, '0.0004'), (.0008, '0.0008'), (.0012, '0.0012')):
        b.append(line(X(v), ya, X(v), ya + 12, INK, 2.5))
        b.append(t(X(v), ya + 50, s, 34, GREY, 'middle'))
    b.append(line(X(0), 66, X(0), ya, GREY, 2.5, '10 9'))
    b.append(t(X(0) + 16, 92, 'no difference', 36, GREY))
    yi = 198
    b.append(rect(X(-.0002), yi - 14, X(.0011) - X(-.0002), 28, '#c9d6e6', 'rx="14"'))
    b.append(line(X(-.0002), yi, X(.0011), yi, INK, 9))
    for v in (-.0002, .0011):
        b.append(line(X(v), yi - 26, X(v), yi + 26, INK, 6))
    b.append(t(X(-.0002) + 24, yi - 48, '−0.0002', 38, INK, 'end', 600))
    b.append(t(X(.0011), yi - 48, '0.0011', 38, INK, 'middle', 600))
    b.append(f'<circle cx="{X(.00044):.1f}" cy="{yi}" r="20" fill="{INK}" stroke="#fff" stroke-width="6"/>')
    b.append(t(X(.00044), yi + 100, '0.00044', 56, INK, 'middle', 700))
    b.append(t(xa - 40, H - 26, 'XGBoost − RF, macro-F1 · 95 % interval', 34, GREY))
    return svg(W, H, ''.join(b), 'XGBoost minus Random Forest macro-F1 with 95 percent interval')


# ---------------------------------------------------------------- precision at prevalence
def ppv():
    W, H = 890, 462
    groups = [('1 in 100', .580, .515, '0.580', '0.515'), ('1 in 1,000', .120, .095, '0.120', '0.095'),
              ('1 in 10,000', .0135, .0104, '0.0135', '0.0104')]
    x0, y0, ph = 80, 360, 270
    sc = ph / .6
    b = [f'<rect x="{x0}" y="{y0 - ph - 30}" width="{W - x0}" height="{ph + 30}" rx="20" fill="url(#gP)"/>']
    for k in (.2, .4, .6):
        yy = y0 - sc * k
        b.append(line(x0, yy, W, yy, GRID, 2))
        b.append(t(x0 - 14, yy + 12, f'{k:.1f}', 34, GREY, 'end'))
    b.append(line(x0, y0, W, y0, INK, 2.5))
    b.append(t(x0 - 14, y0 + 12, '0.0', 34, GREY, 'end'))
    # direct series labels, once, top right (empty region above the short bars)
    b.append(rect(W - 290, 8, 30, 30, 'url(#gB)', 'rx="8"'))
    b.append(t(W - 244, 38, 'random', 38, BLUE, 'start', 600))
    b.append(rect(W - 290, 56, 30, 30, 'url(#gV)', 'rx="8"'))
    b.append(t(W - 244, 86, 'day-disjoint', 38, VERM, 'start', 600))
    gw = (W - x0) / 3
    bw = 112
    for i, (lab, r, d, rs, ds) in enumerate(groups):
        x = x0 + i * gw + (gw - 2 * bw - 8) / 2
        for j, (v, c, s) in enumerate(((r, 'url(#gB)', rs), (d, 'url(#gV)', ds))):
            hh = max(sc * v, 5)
            bx = x + j * (bw + 8)
            col = BLUE if j == 0 else VERM
            stag = 44 if (i == 2 and j == 1) else 0     # tiny bars: stagger the two value labels
            b.append(bar(bx, y0 - hh, bw, hh, c, 8))
            b.append(t(bx + bw / 2, y0 - hh - 12 - stag, s, 34, col, 'middle', 600))
        b.append(t(x + bw + 4, y0 + 56, lab, 38, INK, 'middle', 600))
    return svg(W, H, ''.join(b), 'XGBoost precision at operational prevalence')


# ---------------------------------------------------------------- serving: log meter + stage bar
def logmeter():
    W, H = 1100, 316
    x0, x1 = 50, 1040
    ya = 250

    def X(v):
        return x0 + (math.log10(v) - 2) / 4 * (x1 - x0)
    b = [line(x0, ya, x1, ya, INK, 2.5)]
    for v, s in ((100, '100'), (1e3, '1k'), (1e4, '10k'), (1e5, '100k'), (1e6, '1M')):
        b.append(line(X(v), ya, X(v), ya + 12, INK, 2.5))
        b.append(t(X(v), ya + 52, s, 34, GREY, 'middle'))
    b.append(line(X(404), ya, X(950000), ya, VERM, 8))          # the gap
    xp, xb_, xm = X(950000), X(34662), X(404)
    b.append(line(xp, 112, xp, ya, GREY, 2.5))
    b.append(f'<text x="{xp + 14:.1f}" y="62" font-size="50" font-weight="700" fill="{INK}" text-anchor="end">9.5×10<tspan font-size="32" dy="-20">5</tspan><tspan dy="20" font-size="42"> flows/s</tspan></text>')
    b.append(t(xp + 14, 104, 'predicted from model cost', 34, GREY, 'end'))
    b.append(line(xb_, 190, xb_, ya, MID, 2.5))
    b.append(t(xb_, 150, '34,662 flows/s', 38, INK, 'middle', 600))
    b.append(t(xb_, 184, 'batch of 256', 34, GREY, 'middle'))
    b.append(line(xm, 190, xm, ya, INK, 3))
    b.append(t(0, 150, '404 requests/s', 44, INK, 'start', 700))
    b.append(t(0, 184, 'measured, best config', 34, GREY, 'start'))
    b.append(f'<circle cx="{xm:.1f}" cy="{ya}" r="13" fill="{INK}"/><circle cx="{xp:.1f}" cy="{ya}" r="13" fill="#fff" stroke="{INK}" stroke-width="4"/>')
    return svg(W, H, ''.join(b), 'Throughput on a log scale: measured versus predicted')


def stagebar():
    W = 878
    tot = 2.93
    parts = [('1.04', 1.04, INK, '#fff', ['model call', '+ scaling']), ('0.81', .81, '#7d8791', '#fff', ['web', 'framework']),
             ('1.08', 1.08, '#cfd7e1', INK, ['transport,', 'ASGI + client'])]
    b = [t(0, 44, 'one request = 2.93 ms', 44, INK, 'start', 700)]
    x = 0
    for s, v, c, tc, lab in parts:
        w = v / tot * W
        b.append(rect(x, 68, w - 6, 88, c, 'rx="14"'))
        b.append(t(x + (w - 6) / 2, 130, s, 46, tc, 'middle', 700))
        for k, ln in enumerate(lab):
            b.append(t(x + 4, 188 + k * 38, ln, 34, GREY))
        x += w
    return svg(W, 228, ''.join(b), 'Where one request spends 2.93 ms')


# ---------------------------------------------------------------- QR codes (dark on white, quiet zone kept)
def qr(url):
    q = segno.make(url, error='m')
    n = q.symbol_size(border=4)[0]
    s = q.svg_inline(scale=1, border=4, dark='#000000', light='#ffffff')
    return s.replace('<svg ', f'<svg viewBox="0 0 {n} {n}" shape-rendering="crispEdges" role="img" aria-label="QR code for {e(url)}" ', 1) \
            .replace(f'width="{n}" height="{n}"', '', 1)


# ---------------------------------------------------------------- trap timeline (HTML)
def stripes():
    W, H, pitch, sw = 2942, 38, 22, 10
    n = W // pitch
    x_, out = 12345, []
    for i in range(n):
        x_ = (x_ * 1103515245 + 12345) & 0x7fffffff
        c = BLUE if (x_ >> 16) % 10 < 3 else '#c3ccd8'
        out.append(f'<rect x="{i*pitch + 3}" y="0" width="{sw}" height="{H}" rx="3" fill="{c}"/>')
    return svg(W, H, ''.join(out), 'Random split: train and test samples interleaved in time',
               'preserveAspectRatio="none" style="width:100%;height:38px"')


DAYS = [('Mon', 300, ['Benign only']), ('Tue', 500, ['FTP-Patator', 'SSH-Patator']),
        ('Wed', 880, ['DoS Hulk', 'GoldenEye', 'slowloris', 'Slowhttptest', 'Heartbleed']),
        ('Thu', 520, ['Web brute f.', 'Web XSS', 'Web SQLi', 'Infiltration']),
        ('Fri', 418, ['Botnet', 'Port scan', 'DDoS'])]


def trap_diagram():
    def cell(d, w, fams):
        return f'<div class="day" style="flex:{w} 1 0"><b>{d}</b><span>{" · ".join(e(f) for f in fams)}</span></div>'
    train = ''.join(cell(*d) for d in DAYS[:3])
    test = ''.join(cell(*d) for d in DAYS[3:])
    return f'''<div class="tl">
 <div class="lab"><b class="bl">random split</b><span>train (grey) and test (blue) interleaved</span></div>
 <div class="bar">{stripes()}</div>
 <div class="lab" style="margin-top:6px"><b class="vm">day-disjoint</b><span>each attack family on one day only</span></div>
 <div class="blks"><div class="blk tr" style="flex:1680 1 0"><i>Train</i>{train}</div><div class="blk te" style="flex:938 1 0"><i>Test</i>{test}</div></div>
</div>'''


GUIDE = [
    ('G1', 'report a split that shares no attack family beside the random one, and the gap'),
    ('G2', 'fit scaling, selection and oversampling inside each training split'),
    ('G3', 'per-family recall with test counts, leave-one-family-out'),
    ('G4', 'seeds, intervals, paired tests'),
    ('G5', 'rank at a stated operating point or threshold-free'),
    ('G6', 'state prevalence and translate error rates to the intended link'),
    ('G7', 'document feature alignment for cross-dataset claims'),
    ('G8', 'measure the served endpoint by stage; <span class="hot">never</span> convert an amortised model cost into a throughput.'),
]


def guide():
    def item(k, v):
        return f'<div class="gi"><span class="gc">{k}</span><span class="gt">{v if "<span" in v else e(v)}</span></div>'
    return '<div class="gg"><div>' + ''.join(item(*g) for g in GUIDE[:4]) + '</div><div>' + ''.join(item(*g) for g in GUIDE[4:]) + '</div></div>'


def font_css():
    out = []
    for fam, stem, weights in FONT_FILES:
        for w in weights:
            f = FONT_DIR / f'{stem}-latin-{w}-normal.woff2'
            if not f.exists():  # fetch once from the fontsource CDN
                import urllib.request
                FONT_DIR.mkdir(exist_ok=True)
                urllib.request.urlretrieve(f'https://cdn.jsdelivr.net/npm/@fontsource/{stem}/files/{f.name}', f)
            b64 = base64.b64encode(f.read_bytes()).decode()
            out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:normal;"
                       f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return '\n'.join(out)


SANS = "'IBM Plex Sans','Segoe UI',Arial,sans-serif"
CARD_BG = 'linear-gradient(180deg,#ffffff 0%,#f4f7fc 100%)'
SHADOW = '0 6px 24px rgba(20,40,80,.08)'

CSS = f'''
@page {{ size: 841mm 1189mm; margin: 0 }}
* {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact }}
html,body {{ margin:0; padding:0; background:#eef3fa }}
body {{ width:841mm; height:1189mm; overflow:hidden; font-family:{SANS}; color:{INK}; font-weight:400;
  font-variant-numeric: tabular-nums lining-nums; font-feature-settings:'tnum' 1,'lnum' 1 }}
svg text {{ font-family:{SANS}; font-variant-numeric:tabular-nums lining-nums; font-feature-settings:'tnum' 1,'lnum' 1 }}
.poster {{ width:3178px; height:4494px; position:relative; display:flex; flex-direction:column;
  background:linear-gradient(180deg,#f3f6fb 0%,#e9eff8 100%);
  padding:34px 70px 30px 70px; overflow:hidden; justify-content:space-between }}
.bl {{ color:{BLUE} }} .vm {{ color:{VERM} }} .hot {{ color:{VERM}; font-weight:700 }} .gr {{ color:{GREY} }}
svg {{ display:block }}
svg.ar {{ display:inline-block; height:.46em; width:.92em; vertical-align:.04em; margin:0 .1em }}
sup {{ font-size:.55em; line-height:0 }}
b {{ font-weight:600 }}

.card {{ position:relative; flex:none; background:{CARD_BG}; border:2px solid {RULE}; border-radius:28px;
  box-shadow:{SHADOW}; padding:24px 48px 28px }}
.hd {{ display:flex; align-items:center; gap:24px }}
.np {{ flex:none; min-width:64px; height:64px; padding:0 16px; border-radius:18px; background:{INK}; color:#fff;
  font-size:38px; font-weight:600; display:flex; align-items:center; justify-content:center; letter-spacing:.02em }}
h2 {{ margin:0; font-size:68px; line-height:1.1; font-weight:600; letter-spacing:-.01em; white-space:nowrap }}
.body {{ font-size:40px; line-height:1.32; margin:0 }}

/* header */
header {{ flex:none; display:grid; grid-template-columns:1fr 900px; gap:40px; align-items:end; padding:0 8px }}
.kick {{ margin:0 0 12px; display:flex; align-items:center; gap:18px; font-size:36px; font-weight:500; color:{GREY} }}
.kick i {{ font-style:normal; font-weight:600; color:#fff; background:{BLUE}; border-radius:999px; padding:6px 24px; letter-spacing:.06em }}
h1 {{ font-size:108px; line-height:1.04; margin:0; font-weight:700; letter-spacing:-.02em }}
.sub {{ font-size:46px; color:{GREY}; margin:10px 0 0 }}
.hr .au {{ font-size:44px; margin:0; font-weight:600; line-height:1.25 }}
.hr .af {{ font-size:34px; color:{GREY}; margin:14px 0 0; line-height:1.3 }}

/* KPI strip */
.kpi {{ flex:none; display:grid; grid-template-columns:1.34fr 1fr 1fr 1fr; gap:30px }}
.tile {{ position:relative; overflow:hidden; background:{CARD_BG}; border:2px solid {RULE}; border-radius:28px; box-shadow:{SHADOW};
  padding:32px 44px 22px }}
.tile::before {{ content:''; position:absolute; left:0; right:0; top:0; height:12px; background:var(--c) }}
.tile .l {{ font-size:34px; font-weight:500; letter-spacing:.07em; text-transform:uppercase; color:{GREY}; margin:0 }}
.tile .v {{ font-size:108px; font-weight:600; line-height:1.08; white-space:nowrap; display:flex; align-items:center; margin:6px 0 4px; letter-spacing:-.02em }}
.tile .v svg {{ width:78px; height:39px; margin:0 14px; flex:none; color:{INK} }}
.tile .v .a {{ color:{BLUE} }} .tile .v .z {{ color:{VERM} }}
.tile .c {{ font-size:37px; line-height:1.24; margin:0; color:{INK} }}

/* 1 trap */
.trap .top {{ display:flex; align-items:center; gap:60px }}
.trap .top .body {{ flex:1 }}
.tl {{ display:flex; flex-direction:column; gap:6px; margin-top:12px }}
.tl .lab {{ display:flex; align-items:baseline; gap:22px }}
.tl .lab b {{ font-size:40px; font-weight:600; line-height:1.1 }}
.tl .lab span {{ font-size:34px; color:{GREY}; line-height:1.15 }}
.blks {{ display:flex; gap:0 }}
.blk {{ display:flex; position:relative; border-top:8px solid {MID}; padding-top:50px; border-radius:6px }}
.blk.te {{ border-top-color:{VERM} }}
.blk i {{ position:absolute; top:8px; left:0; font-style:normal; font-size:32px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:{GREY} }}
.blk.te i {{ color:{VERM} }}
.day {{ padding:0 18px 0 20px; display:flex; flex-direction:column; gap:4px }}
.blk.tr .day:first-of-type {{ padding-left:0 }}
.day + .day {{ border-left:2px solid {RULE} }}
.day b {{ font-size:40px; line-height:1.1 }}
.day span {{ font-size:32px; line-height:1.22; color:{GREY} }}

/* 2 hero */
.dom .row {{ display:flex; gap:48px; margin-top:10px; align-items:stretch }}
.fig {{ flex:none; width:2034px }}
.side {{ flex:1; display:flex; flex-direction:column; gap:20px }}
.st {{ border:2px solid #e1e8f2; background:linear-gradient(180deg,#f7f9fd,#eef3fa); border-radius:22px; padding:22px 34px; flex:1;
  display:flex; flex-direction:column; justify-content:center }}
.st.first {{ background:linear-gradient(180deg,#fdf1ec,#fbe7df); border-color:#f3d3c7 }}
.st .k {{ font-size:66px; font-weight:700; color:{VERM}; line-height:1.05; margin:0 }}
.st .d {{ font-size:42px; line-height:1.25; margin:10px 0 0 }}
.st small {{ display:block; white-space:nowrap; font-size:36px; font-weight:500; color:{GREY}; line-height:1.2; margin-bottom:8px }}
.st .n {{ font-weight:700; font-size:84px; line-height:1; white-space:nowrap; display:flex; align-items:center; letter-spacing:-.02em }}
.st .n svg {{ width:64px; height:32px; margin:0 12px; flex:none; color:{GREY} }}
.st .n.m {{ color:{VERM} }}

/* 3 proofs */
.proofs {{ display:grid; grid-template-columns:repeat(3,1fr); gap:32px; flex:none }}
.pn {{ display:flex; flex-direction:column; padding:24px 44px 28px }}
.pn h2 {{ font-size:62px }}
.stat {{ display:flex; align-items:center; gap:26px; margin:6px 0 8px; height:96px }}
.stat .v {{ font-weight:700; font-size:100px; line-height:1; white-space:nowrap; display:flex; align-items:center; letter-spacing:-.02em }}
.stat .v svg {{ width:90px; height:45px; margin:0 12px }}
.stat .u {{ font-size:34px; line-height:1.22; color:{GREY} }}
.pn .ch {{ margin:0 }}
.pn .body {{ margin-top:16px }}

/* 4 serving */
.serve .row {{ display:grid; grid-template-columns:760px 1196px 1fr; gap:0; margin-top:14px; align-items:center }}
.serve .row > div {{ padding:0 48px; border-left:2px solid {RULE} }}
.serve .row > div:first-child {{ padding-left:0; border-left:0 }} .serve .row > div:last-child {{ padding-right:0 }}
.ratio .v {{ font-size:178px; font-weight:700; line-height:.98; color:{VERM}; margin:0 0 10px; white-space:nowrap; letter-spacing:-.03em }}
.rep {{ margin-top:18px }}

/* 5 guidelines */
.gg {{ display:grid; grid-template-columns:1.1fr 1fr; column-gap:44px; margin-top:12px; align-items:start }}
.gg > div {{ display:flex; flex-direction:column }}
.gi {{ display:flex; gap:20px; align-items:flex-start; padding:8px 0 9px; border-bottom:2px solid #e4eaf3 }}
.gg > div .gi:last-child {{ border-bottom:0 }}
.gc {{ flex:none; width:80px; height:52px; margin-top:2px; border-radius:16px; background:{INK}; color:#fff; font-weight:600; font-size:32px;
  display:flex; align-items:center; justify-content:center }}
.gg > div:nth-child(2) .gc {{ background:#5b6775 }}
.gt {{ font-size:40px; line-height:1.3 }}

/* footer */
footer {{ flex:none; display:grid; grid-template-columns:830px 1fr 830px; gap:0; align-items:center; padding:18px 48px }}
.q {{ display:flex; align-items:center; gap:30px }}
.q svg {{ width:176px; height:176px; flex:none; border-radius:12px; border:2px solid {RULE} }}
.q .t {{ font-size:40px; line-height:1.2; font-weight:600 }}
.q .t u {{ display:block; text-decoration:none; font-size:32px; color:{GREY}; font-weight:400; overflow-wrap:anywhere; margin-top:8px; line-height:1.2 }}
.fc {{ padding:0 40px }}
.fc .lim {{ font-size:34px; line-height:1.3; color:{GREY}; margin:0 0 10px }}
.fc .lim b {{ color:{INK}; font-weight:600 }}
.fc .wr {{ font-size:36px; font-weight:600; margin:0 }}
@media screen {{ body {{ overflow:auto; height:auto }} }}
'''


def page():
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SOICT 2026 poster · How Optimistic Is Your Intrusion-Detection Benchmark? (dashboard)</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{font_css()}</style><style>{CSS}</style></head>
<body>{DEFS}<div class="poster">
<header>
 <div>
  <p class="kick"><i>SOICT 2026</i>paper 9222</p>
  <h1>How Optimistic Is Your<br>Intrusion-Detection Benchmark?</h1>
  <p class="sub">Leakage-resistant evaluation and measured serving cost</p>
 </div>
 <div class="hr">
  <p class="au">Huy-Thanh Pham<sup>1,2</sup><br>Anh Truong<sup>*,1,2</sup></p>
  <p class="af"><sup>1</sup> Ho Chi Minh City University of Technology (HCMUT)<br><sup>2</sup> Vietnam National University Ho Chi Minh City<br>* anhtt@hcmut.edu.vn</p>
 </div>
</header>

<div class="kpi">
 <div class="tile" style="--c:{BLUE}"><p class="l">XGBoost attack recall, CICIDS2017</p>
  <div class="v"><span class="a">0.99</span>{AR(INK)}<span class="z">0.32</span></div>
  <p class="c">when only the split changes: from a random split to a split that shares no attack family</p></div>
 <div class="tile" style="--c:{VERM}"><p class="l">Serving gap</p>
  <div class="v vm">2,300×</div>
  <p class="c">model-cost prediction vs the measured endpoint</p></div>
 <div class="tile" style="--c:{VERM}"><p class="l">False alerts</p>
  <div class="v vm">7 of 8</div>
  <p class="c">alerts false at 1 attack in 1,000</p></div>
 <div class="tile" style="--c:#8a96a5"><p class="l">XGBoost − RF, macro-F1</p>
  <div class="v">0.00044</div>
  <p class="c">difference, p = 0.13: not significant</p></div>
</div>

<section class="card trap"><div class="top"><div class="hd"><span class="np">1</span><h2>The trap</h2></div>
  <p class="body">A random split scatters every attack episode across train and test, so the model is tested on traffic it has already seen. Day-disjoint: train Mon–Wed, test Thu–Fri, every test attack a <b>family never seen</b>.</p></div>
 {trap_diagram()}
</section>

<section class="card dom"><div class="hd"><span class="np">2</span><h2>Recall collapses when only the split changes</h2></div>
 <div class="row">
  <div class="fig">{recall_chart()}</div>
  <div class="side">
   <div class="st first"><p class="k">Silent failure</p><p class="d">false-positive rate even improves</p></div>
   <div class="st"><small>XGBoost false-positive rate</small><div class="n">0.0073{AR('currentColor')}0.0030</div></div>
   <div class="st"><small>missed attack flows</small><div class="n m">185{AR('currentColor')}36,506</div></div>
   <div class="st"><small>XGBoost macro-F1</small><div class="n">0.9879{AR('currentColor')}0.6887</div></div>
  </div>
 </div>
</section>

<div class="proofs">
 <section class="card pn"><div class="hd"><span class="np">3a</span><h2>Ranking flips</h2></div>
  <div class="stat"><div class="v">last{AR(INK)}first</div><div class="u">LogReg<br>by macro-F1</div></div>
  <div class="ch">{slope()}</div>
  <p class="body">Less selective wins: FPR 0.0592 vs 0.0030. ROC-AUC reverses it: 0.6448 vs 0.8526.</p></section>
 <section class="card pn"><div class="hd"><span class="np">3b</span><h2>Best model?</h2></div>
  <div class="stat"><div class="v">p = 0.13</div><div class="u">XGBoost vs RF<br>not significant</div></div>
  <div class="ch">{interval()}</div>
  <p class="body">Paired t-test p = 0.13, Wilcoxon p = 0.19 (5 seeds): two tiers, no winner.</p></section>
 <section class="card pn"><div class="hd"><span class="np">3c</span><h2>Real precision</h2></div>
  <div class="stat"><div class="v vm">7 of 8</div><div class="u">alerts false at<br>1 attack in 1,000</div></div>
  <div class="ch">{ppv()}</div>
  <p class="body">XGBoost, best case (random split): precision 0.120, 7,257 false alerts per million flows.</p></section>
</div>

<section class="card serve"><div class="hd"><span class="np">4</span><h2>Serving cost, measured</h2></div>
 <div class="row">
  <div class="ratio"><div class="v">2,300×</div><p class="body">model cost predicts 9.5×10<sup>5</sup> flows/s; the endpoint sustains <b>404</b> requests/s</p></div>
  <div>{logmeter()}</div>
  <div>{stagebar()}<p class="body rep">Kill 1 of 4 replicas under load: <b>35</b> of ~8,000 requests lost, recovered in <b>3.13 s</b>.</p></div>
 </div>
</section>

<section class="card guide"><div class="hd"><span class="np">5</span><h2>Evaluate your NIDS this way</h2></div>
 {guide()}
</section>

<footer class="card">
 <div class="q">{qr('https://github.com/HThanh-how/nids-cicids2017')}<div class="t">Code, manifests, raw results<u>github.com/HThanh-how/nids-cicids2017</u></div></div>
 <div class="fc"><p class="lim"><b>Limits.</b> CICIDS2017 has documented labelling defects: absolute scores are not field accuracy. Two corpora, four conventional models, one serving host.</p>
  <p class="wr">Huy-Thanh Pham, Anh Truong · SOICT 2026, paper 9222</p></div>
 <div class="q" style="justify-content:flex-end">{qr('https://hthanh-how.github.io/nids-cicids2017/')}<div class="t">Slides<u>hthanh-how.github.io/nids-cicids2017</u></div></div>
</footer>
</div></body></html>'''


def build_all():
    chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    with tempfile.TemporaryDirectory() as td:
        prof = pathlib.Path(td) / 'prof'
        subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--user-data-dir={prof}',
                        f'--print-to-pdf={PDF}', OUT.as_uri()], check=True, timeout=300)
        r = subprocess.run(['pdfinfo', str(PDF)], capture_output=True, text=True).stdout
        print([l for l in r.splitlines() if l.startswith(('Pages', 'Page size'))])
        base = pathlib.Path(td) / 'p'
        subprocess.run(['pdftocairo', '-jpeg', '-jpegopt', 'quality=88', '-r', '100', '-singlefile', str(PDF), str(base)], check=True)
        jpg = base.with_suffix('.jpg')
        from pptx import Presentation
        from pptx.util import Mm
        prs = Presentation()
        prs.slide_width, prs.slide_height = Mm(841), Mm(1189)
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.shapes.add_picture(str(jpg), 0, 0, prs.slide_width, prs.slide_height)
        prs.save(PPTX)
    print('wrote', PDF.name, PPTX.name)


OUT.write_text(page(), encoding='utf-8')
print('wrote', OUT, OUT.stat().st_size)
if '--all' in sys.argv:
    build_all()

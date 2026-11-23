# Generates poster.html (A0 portrait, 841 x 1189 mm, light print theme, inline SVG, no JS, no network).
# Every number below is copied from the paper (Source/main.tex and Source/tables/*.tex).
# Visual design only: values, claims and wording are unchanged from the previous version.
import html, math, pathlib

import segno

OUT = pathlib.Path(__file__).with_name('poster.html')
TEAL, AMB, RED, INK, DIM, GRID = '#0b7a75', '#c2670a', '#b3203f', '#14202b', '#5b6b78', '#d5dde3'
BLUE = '#2b5fa8'
FW = 950  # figure width in px (card inner width is >= FW, so figures are never down-scaled)
e = html.escape


def svg(w, h, body, label):
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{e(label)}">{body}</svg>'


def t(x, y, s, size=36, fill=INK, anchor='start', weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{e(s)}</text>'


def rect(x, y, w, h, fill, stroke='none', rx=6, sw=3):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def line(x1, y1, x2, y2, c=GRID, sw=3, dash=''):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{sw}"{d}/>'


# rough Arial advance widths (em) used only to pack chips in the timeline
_NARROW = set('ilj.,;:!|\'tfI ')
_WIDE = set('mwMW')


def tw(s, size):
    w = 0
    for ch in s:
        if ch in _NARROW:
            w += .3
        elif ch in _WIDE:
            w += .85
        elif ch.isupper():
            w += .68
        else:
            w += .55
    return w * size


# ---------------------------------------------------------------- pipeline (setup)
def pipeline():
    W = FW
    b = []
    steps = [
        ('CICIDS2017', '535,069 flows · 78 features · 14 attack labels', INK),
        ('Fit inside every training split', 'scaler → top-20 feature selection → SMOTE', TEAL),
        ('Four ordinary models, fixed a priori', 'LogReg · Random Forest · XGBoost · MLP, no tuning', TEAL),
        ('Only the split changes', 'random 70/30 (5 seeds) vs day-disjoint (3 seeds)', AMB),
    ]
    y = 0
    bh, step = 116, 140
    for i, (h, s, c) in enumerate(steps):
        b.append(rect(0, y, W, bh, '#ffffff', c, 12, 6))
        b.append(rect(0, y, 18, bh, c, 'none', 4))
        b.append(t(44, y + 50, h, 42, c, weight=700))
        b.append(t(44, y + 94, s, 33, INK))
        if i < 3:
            b.append(f'<path d="M{W/2-26} {y+bh+6} L{W/2+26} {y+bh+6} L{W/2} {y+bh+32} Z" fill="{DIM}"/>')
        y += step
    return svg(W, y - (step - bh), ''.join(b), 'Evaluation pipeline')


# ---------------------------------------------------------------- day timeline (days as rows, families as chips)
def timeline():
    W = FW
    days = [('Mon', ['Benign only']), ('Tue', ['FTP-Patator', 'SSH-Patator']),
            ('Wed', ['DoS Hulk', 'GoldenEye', 'slowloris', 'Slowhttptest', 'Heartbleed']),
            ('Thu', ['Web brute f.', 'Web XSS', 'Web SQLi', 'Infiltration']),
            ('Fri', ['Botnet', 'Port scan', 'DDoS'])]
    fs, ch, gap, lx = 30, 56, 8, 150
    avail = W - lx - 16
    b = []
    y = 0
    for gi, (title, col, tint, sel) in enumerate((('TRAIN (Mon–Wed)', TEAL, 'rgba(11,122,117,0.10)', days[:3]),
                                                  ('TEST (Thu–Fri)', AMB, 'rgba(194,103,10,0.11)', days[3:]))):
        b.append(t(W / 2, y + 38, title, 38, col, 'middle', 700))
        y += 54
        rows = []
        for d, fam in sel:
            lines, cur, cw_ = [], [], 0
            for f in fam:
                w = tw(f, fs) + 34
                if cur and cw_ + gap + w > avail:
                    lines.append(cur); cur, cw_ = [], 0
                cw_ += (gap if cur else 0) + w
                cur.append((f, w))
            lines.append(cur)
            rows.append((d, lines))
        h_total = sum(len(l) * (ch + gap) for _, l in rows) + 8
        b.append(rect(0, y, W, h_total, tint, col, 14, 4))
        yy = y + 10
        for d, lines in rows:
            rh = len(lines) * (ch + gap)
            b.append(t(lx / 2, yy + rh / 2 - gap / 2 + 14, d, 42, INK, 'middle', 700))
            for k, ln in enumerate(lines):
                x = lx
                for f, w in ln:
                    b.append(rect(x, yy + k * (ch + gap), w, ch, '#ffffff', col, 12, 3))
                    b.append(t(x + w / 2, yy + k * (ch + gap) + 39, f, fs, INK, 'middle'))
                    x += w + gap
            yy += rh
        y += h_total + 22
    b.append(t(W / 2, y + 4, 'each family occurs on exactly one day → family-disjoint', 32, DIM, 'middle'))
    return svg(W, y + 16, ''.join(b), 'Capture days and attack families')


# ---------------------------------------------------------------- HERO figure: recall random vs day-disjoint
def recall_bars():
    W, H = FW, 840
    models = [('LogReg', .9100, .4975), ('RF', .9937, .3109), ('XGBoost', .9935, .3164), ('MLP', .9857, .3467)]
    x0, y0, ph = 92, 740, 620
    b = []
    for k in (0, .25, .5, .75, 1):
        yy = y0 - ph * k
        b.append(line(x0, yy, W, yy))
        b.append(t(x0 - 14, yy + 11, f'{k:.2f}', 30, DIM, 'end'))
    # big translucent "falling" arrow behind the bars
    b.append(f'<path d="M260 170 L650 430 L610 458 L800 520 L780 330 L742 356 L340 112 Z" fill="{AMB}" fill-opacity="0.10"/>')
    gw = (W - x0) / 4
    bw = 98
    for i, (m, r, d) in enumerate(models):
        x = x0 + i * gw + 7
        for j, (v, c) in enumerate(((r, TEAL), (d, AMB))):
            hh = ph * v
            bx = x + j * (bw + 6)
            b.append(rect(bx, y0 - hh, bw, hh, c, 'none', 6))
            b.append(t(bx + bw / 2, y0 - hh - 14, f'{v:.2f}', 46, c, 'middle', 700))
        b.append(t(x + bw + 3, y0 + 54, m, 40, INK, 'middle', 700))
    b.append(rect(x0 + 10, 4, 40, 40, TEAL) + t(x0 + 64, 38, 'random split', 36, INK) + rect(x0 + 350, 4, 40, 40, AMB) + t(x0 + 404, 38, 'day-disjoint split', 36, INK))
    return svg(W, H, ''.join(b), 'Attack recall under both protocols')


# ---------------------------------------------------------------- slope chart: macro-F1 ranking
def slope():
    W, H = FW, 610
    data = [('XGBoost', .9879, .6887, TEAL), ('RF', .9874, .6852, BLUE), ('MLP', .9491, .6928, '#7a4fa8'), ('LogReg', .8515, .7433, AMB)]
    xl, xr, top, bot = 340, 620, 90, 520
    lo, hi = .64, 1.0

    def Y(v):
        return bot - (v - lo) / (hi - lo) * (bot - top)
    b = [t(xl, 28, 'random', 34, TEAL, 'middle', 700), t(xr, 28, 'day-disjoint', 34, AMB, 'middle', 700)]
    b.append(line(xl, top + 10, xl, bot + 10, GRID, 4) + line(xr, top + 10, xr, bot + 10, GRID, 4))
    left_off = {'XGBoost': -14, 'RF': 20, 'MLP': 8, 'LogReg': 0}
    right_off = {'XGBoost': 8, 'RF': 36, 'MLP': -26, 'LogReg': 0}
    for m, a, d, c in data:
        b.append(f'<line x1="{xl}" y1="{Y(a)}" x2="{xr}" y2="{Y(d)}" stroke="{c}" stroke-width="9" stroke-linecap="round"/>')
        b.append(f'<circle cx="{xl}" cy="{Y(a)}" r="13" fill="{c}"/><circle cx="{xr}" cy="{Y(d)}" r="13" fill="{c}"/>')
        b.append(t(xl - 24, Y(a) + 12 + left_off[m], f'{m} {a:.4f}', 32, c, 'end', 700))
        b.append(t(xr + 24, Y(d) + 12 + right_off[m], f'{d:.4f} {m}', 32, c, 'start', 700))
    b.append(t(W / 2, 596, 'macro-F1 · LogReg: last → first', 34, INK, 'middle', 700))
    return svg(W, H, ''.join(b), 'Macro-F1 ranking inversion')


# ---------------------------------------------------------------- decomposition (XGBoost recall)
def decomposition():
    W, H = FW, 555
    items = [('random split', .9935, TEAL), ('random, grouped\nno near-duplicates', .9821, TEAL),
             ('seen families,\nsame days', .9975, TEAL), ('UNSEEN families\n(Thu–Fri attacks)', .3218, AMB)]
    x0, y0, ph = 70, 420, 330
    b = []
    for k in (0, .5, 1):
        yy = y0 - ph * k
        b.append(line(x0, yy, W, yy)); b.append(t(x0 - 12, yy + 12, f'{k:.1f}', 30, DIM, 'end'))
    bw = 160
    pitch = (W - 20 - x0) / 4
    for i, (lab, v, c) in enumerate(items):
        cx = x0 + pitch * (i + .5)
        x = cx - bw / 2
        hh = ph * v
        b.append(rect(x, y0 - hh, bw, hh, c, 'none', 6))
        b.append(t(cx, y0 - hh - 14, f'{v:.4f}', 36, c, 'middle', 700))
        for k, ln in enumerate(lab.split('\n')):
            b.append(t(cx, y0 + 44 + k * 34, ln, 28, INK, 'middle', 700 if 'UNSEEN' in ln else 400))
    b.append(t(W / 2, 541, 'XGBoost attack recall', 32, DIM, 'middle'))
    return svg(W, H, ''.join(b), 'Decomposition of the gap')


# ---------------------------------------------------------------- precision at prevalence
def ppv():
    W, H = FW, 530
    groups = [('1 in 100', .580, .515), ('1 in 1,000', .120, .095), ('1 in 10,000', .0135, .0104)]
    x0, y0, ph = 70, 440, 330
    b = []
    for k in (0, .25, .5, .75, 1):
        yy = y0 - ph * k
        b.append(line(x0, yy, W, yy)); b.append(t(x0 - 12, yy + 12, f'{k:.2f}', 30, DIM, 'end'))
    gw = (W - x0) / 3
    for i, (lab, r, d) in enumerate(groups):
        x = x0 + i * gw + 22
        for j, (v, c) in enumerate(((r, TEAL), (d, AMB))):
            hh = max(ph * v, 4)
            bx = x + j * 120
            b.append(rect(bx, y0 - hh, 108, hh, c, 'none', 5))
            b.append(t(bx + 54, y0 - hh - 14, {0.58: '0.580', 0.515: '0.515', 0.12: '0.120', 0.095: '0.095', 0.0135: '0.0135', 0.0104: '0.0104'}[v], 30, c, 'middle', 700))
        b.append(t(x + 114, y0 + 44, lab, 32, INK, 'middle'))
    b.append(t(W / 2, 514, 'attack prevalence on the link', 32, DIM, 'middle'))
    b.append(rect(x0 + 10, 4, 34, 34, TEAL) + t(x0 + 56, 32, 'random', 30, INK) + rect(x0 + 260, 4, 34, 34, AMB) + t(x0 + 306, 32, 'day-disjoint', 30, INK))
    return svg(W, H, ''.join(b), 'XGBoost precision at operational prevalence')


# ---------------------------------------------------------------- serving (log scale) + stage breakdown
def serving():
    W = FW
    bars = [('predicted from model cost', 950000, '9.5×10⁵ flows/s', AMB), ('batch of 256', 34662, '34,662 flows/s', BLUE),
            ('measured, best config', 404, '404 requests/s', TEAL), ('default threads, 8 clients', 309, '309 requests/s', DIM)]
    x0, maxv = 20, 6.2
    b = []
    y = 4
    for lab, v, txt, c in bars:
        w = (math.log10(v) / maxv) * (W - 2 * x0)
        b.append(t(x0, y + 28, lab, 32, INK, weight=700))
        b.append(rect(x0, y + 36, w, 46, c, 'none', 6))
        b.append(t(x0 + w + 18 if w < 500 else x0 + w - 18, y + 72, txt, 34, INK if w < 500 else '#fff', 'start' if w < 500 else 'end', 700))
        y += 100
    b.append(t(x0, y + 8, 'log scale · one flow per request pays the call cost each time', 28, DIM))
    y += 50
    tot = 2.93
    parts = [('model call + scaling', 1.04, TEAL), ('web framework', .81, BLUE), ('transport + ASGI + client', 1.08, DIM)]
    b.append(t(x0, y + 24, 'where one request spends 2.93 ms (1 maths thread)', 34, INK, weight=700))
    x = x0
    for lab, v, c in parts:
        w = v / tot * (W - 2 * x0)
        b.append(rect(x, y + 50, w, 80, c, '#fff', 0, 3))
        b.append(t(x + w / 2, y + 102, f'{v:.2f} ms', 34, '#fff', 'middle', 700))
        x += w
    yy = y + 156
    b.append(t(x0, yy, '■ model call + scaling 1.04', 28, TEAL, weight=700))
    b.append(t(x0, yy + 36, '■ web framework 0.81', 28, BLUE, weight=700))
    b.append(t(x0, yy + 72, '■ transport, ASGI server, co-located client 1.08', 28, DIM, weight=700))
    return svg(W, yy + 90, ''.join(b), 'Serving throughput and per-stage time')


# ---------------------------------------------------------------- QR codes (inline SVG, no external files)
def qr(url):
    q = segno.make(url, error='m')
    n = q.symbol_size(border=4)[0]
    s = q.svg_inline(scale=1, border=4, dark='#000000', light='#ffffff')
    return s.replace('<svg ', f'<svg viewBox="0 0 {n} {n}" shape-rendering="crispEdges" role="img" aria-label="QR code for {e(url)}" ', 1) \
            .replace(f'width="{n}" height="{n}"', '', 1)


GUIDE = [
    ('G1', 'report a split that shares no attack family beside the random one, and the gap'),
    ('G2', 'fit scaling, selection and oversampling inside each training split'),
    ('G3', 'per-family recall with test counts, leave-one-family-out'),
    ('G4', 'seeds, intervals, paired tests'),
    ('G5', 'rank at a stated operating point or threshold-free'),
    ('G6', 'state prevalence and translate error rates to the intended link'),
    ('G7', 'document feature alignment for cross-dataset claims'),
    ('G8', 'measure the served endpoint by stage; never convert an amortised model cost into a throughput.'),
]


def guide_grid():
    return '<div class="gg">' + ''.join(f'<div class="gi"><span class="chip">{k}</span><span class="gt">{e(v)}</span></div>' for k, v in GUIDE) + '</div>'


TABLE = ('<table class="tb"><tr><th>Model</th><th>Split</th><th>Macro-F1</th><th>Recall</th><th>FPR</th></tr>'
         '<tr><td><b>LogReg</b></td><td>random</td><td>0.8515</td><td>0.9100</td><td>0.1010</td></tr>'
         '<tr class="d"><td><b></b></td><td>day-disj.</td><td>0.7433</td><td>0.4975</td><td>0.0592</td></tr>'
         '<tr><td><b>RF</b></td><td>random</td><td>0.9874</td><td>0.9937</td><td>0.0076</td></tr>'
         '<tr class="d"><td><b></b></td><td>day-disj.</td><td>0.6852</td><td>0.3109</td><td>0.0029</td></tr>'
         '<tr><td><b>XGBoost</b></td><td>random</td><td>0.9879</td><td>0.9935</td><td>0.0073</td></tr>'
         '<tr class="d"><td><b></b></td><td>day-disj.</td><td>0.6887</td><td>0.3164</td><td>0.0030</td></tr>'
         '<tr><td><b>MLP</b></td><td>random</td><td>0.9491</td><td>0.9857</td><td>0.0359</td></tr>'
         '<tr class="d"><td><b></b></td><td>day-disj.</td><td>0.6928</td><td>0.3467</td><td>0.0211</td></tr></table>')

CSS = f'''
@page {{ size: 841mm 1189mm; margin: 0 }}
* {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact }}
html,body {{ margin:0; padding:0; background:#fff }}
body {{ width:841mm; height:1189mm; overflow:hidden; font-family: Arial, "Segoe UI", sans-serif; color:{INK} }}
.poster {{ width:3178px; height:4494px; position:relative; background:#fff; display:flex; flex-direction:column; overflow:hidden }}

/* ---------- header band (full bleed) ---------- */
header {{ flex:none; background:linear-gradient(115deg,#063b3a 0%,#08524f 45%,#0b7a75 100%); color:#fff; padding:34px 90px 34px;
  display:grid; grid-template-columns: 1fr 1650px; gap:50px; align-items:center; border-bottom:12px solid {AMB}; position:relative }}
header:before {{ content:""; position:absolute; inset:0; background:radial-gradient(900px 600px at 82% 40%, rgba(255,255,255,.10), rgba(255,255,255,0) 70%); pointer-events:none }}
.hl {{ position:relative }}
h1 {{ font-size:96px; line-height:1.04; margin:0 0 20px; letter-spacing:-1px; font-weight:800 }}
.sub {{ font-size:50px; color:#ffc980; margin:0 0 18px; font-weight:700; line-height:1.15 }}
.au {{ font-size:48px; margin:0 }} .au b {{ font-weight:800 }}
.af {{ font-size:36px; color:#d3efec; margin:10px 0 0; line-height:1.25 }}
.hero {{ position:relative; background:rgba(3,34,33,.42); border:5px solid rgba(255,255,255,.38); border-radius:34px; padding:20px 36px 26px; text-align:center }}
.hero .lab {{ font-size:38px; letter-spacing:6px; text-transform:uppercase; color:#ffc980; font-weight:700; margin:0 0 -6px }}
.hero .big {{ font-size:312px; line-height:.96; font-weight:800; white-space:nowrap; letter-spacing:-10px; color:#fff }}
.hero .big i {{ font-style:normal; color:#ffb347 }}
.hero .big em {{ font-style:normal; font-size:.5em; color:#ffb347; margin:0 .1em; position:relative; top:-.05em }}
.hero p {{ font-size:40px; line-height:1.2; margin:6px 0 0; color:#eefaf8 }}

/* ---------- columns ---------- */
.cols {{ flex:1; min-height:0; display:grid; grid-template-columns:repeat(3,1fr); gap:30px; padding:24px 38px 0 }}
.col {{ display:flex; flex-direction:column; gap:18px; min-height:0 }}
.card {{ background:#f6f9fb; border:3px solid #d9e3e9; border-radius:28px; padding:18px 24px 18px; position:relative }}
.col > .card:last-child {{ flex:1 }}
h2 {{ font-size:54px; margin:0 0 10px; color:{TEAL}; line-height:1.08; display:flex; align-items:center; gap:24px }}
h2.a {{ color:{AMB} }}
h2 .num {{ flex:none; width:90px; height:90px; border-radius:50%; background:{TEAL}; color:#fff; font-size:62px; font-weight:800; line-height:90px; text-align:center; box-shadow:0 0 0 8px rgba(11,122,117,.18) }}
h2.a .num {{ background:{AMB}; box-shadow:0 0 0 8px rgba(194,103,10,.20) }}
h2.s {{ font-size:48px; border-left:14px solid {TEAL}; padding-left:20px; border-radius:3px }}
h2.s.a {{ border-color:{AMB} }}
p, li {{ font-size:36px; line-height:1.25; margin:0 0 12px }}
.fig {{ margin:4px 0 0; background:#fff; border:3px solid #e1e8ed; border-radius:20px; padding:4px 0 0 }} .fig svg {{ width:100%; height:auto; display:block }}
.cap {{ font-size:36px; color:#44525e; margin:6px 0 0; line-height:1.2 }}
.hero-card {{ border:6px solid {AMB}; background:#fffaf4 }}
.hero-card .fig {{ border-color:#f0d9bd }}
.silent {{ display:flex; align-items:center; gap:20px; margin:10px 0 0; padding:10px 20px; border-radius:20px; background:rgba(194,103,10,.12); border:4px solid {AMB} }}
.silent svg {{ flex:none; width:72px; height:72px }}
.silent span {{ font-size:42px; line-height:1.15; font-weight:800; color:#8a4606 }}
.note {{ background:#fff; border:4px solid {GRID}; border-radius:16px; padding:16px 24px 6px }}
.note p {{ margin:0 0 10px }}
.tb {{ width:100%; border-collapse:collapse; font-size:34px }} .tb th,.tb td {{ border-bottom:3px solid {GRID}; padding:3px 10px; text-align:right }} .tb th:first-child,.tb td:first-child,.tb th:nth-child(2),.tb td:nth-child(2) {{ text-align:left }} .tb th {{ color:#fff; background:{TEAL}; border-bottom:0 }} .tb tr.d td {{ background:rgba(194,103,10,.09) }} .tb tr:nth-child(odd):not(:first-child) td {{ background:#fff }}
.callout {{ background:#e6f4f3; border:9px solid {TEAL}; box-shadow:0 0 0 6px rgba(11,122,117,.15) }}
.gg {{ display:grid; grid-template-columns:1fr 1fr; gap:12px 14px }}
.gi {{ display:flex; gap:14px; align-items:flex-start; background:#fff; border:3px solid #bfdedb; border-radius:20px; padding:12px 12px }}
.chip {{ flex:none; min-width:70px; height:70px; border-radius:35px; background:{TEAL}; color:#fff; font-size:36px; font-weight:800; line-height:70px; text-align:center }}
.gt {{ font-size:36px; line-height:1.18; padding-top:0 }}
.g {{ font-size:36px; line-height:1.25; margin:0 }}

/* ---------- footer ---------- */
footer {{ flex:none; margin:24px 44px 34px; background:#f6f9fb; border:3px solid #d9e3e9; border-top:12px solid {TEAL}; border-radius:30px; padding:12px 40px; display:grid; grid-template-columns: 1fr 1fr 1fr; gap:40px; align-items:center }}
.q {{ display:flex; align-items:center; gap:32px }}
.q svg {{ width:318px; height:318px; flex:none; border:3px solid {GRID}; background:#fff }}
.q .t {{ font-size:38px; line-height:1.2; color:{DIM} }} .q .t b {{ display:block; font-size:46px; color:{INK}; line-height:1.15; margin-bottom:10px }}
.q .t u {{ text-decoration:none; font-size:36px; color:{TEAL}; font-weight:700; overflow-wrap:anywhere }}
.fc {{ text-align:center; font-size:38px; line-height:1.3; color:{DIM} }} .fc b {{ color:{INK} }} .fc .big {{ font-size:46px; color:{INK}; font-weight:800; line-height:1.15; margin-bottom:10px }}
@media screen {{ body {{ overflow:auto; height:auto }} }}
'''

ARROW_ICON = f'<svg viewBox="0 0 84 84" aria-hidden="true"><path d="M30 6 H54 V42 H72 L42 78 L12 42 H30 Z" fill="{AMB}"/></svg>'


def page():
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SOICT 2026 poster · How Optimistic Is Your Intrusion-Detection Benchmark?</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head>
<body><div class="poster">
<header>
 <div class="hl">
  <h1>How Optimistic Is Your Intrusion-Detection Benchmark?</h1>
  <p class="sub">Leakage-resistant evaluation and measured serving cost</p>
  <p class="au"><b>Huy-Thanh Pham</b><sup>1,2</sup> · <b>Anh Truong</b><sup>*,1,2</sup></p>
  <p class="af"><sup>1</sup> Ho Chi Minh City University of Technology (HCMUT) · <sup>2</sup> Vietnam National University Ho Chi Minh City · * anhtt@hcmut.edu.vn · SOICT 2026, paper 9222</p>
 </div>
 <div class="hero"><div class="big">0.99<em>→</em><i>0.32</i></div><p>XGBoost attack recall on CICIDS2017 when only the split changes: from a random split to a split that shares no attack family.</p></div>
</header>
<div class="cols">
<div class="col">
 <section class="card"><h2><span class="num">1</span>The problem</h2>
  <p>Learned detectors report macro-F1 above <b>0.98</b> on public benchmarks as a matter of routine. Practitioners do not see that performance in the field.</p>
  <p>A random split scatters every attack episode across the train/test boundary, so the model is tested on traffic it has already seen. We keep models, hyperparameters and preprocessing fixed, vary <b>only the evaluation</b>, and measure how much of a score belongs to the protocol.</p></section>
 <section class="card"><h2><span class="num">2</span>Fixed pipeline</h2><div class="fig">{pipeline()}</div>
  <p class="cap">Standardisation, selection and oversampling are part of the model: re-fitted inside every training split, so nothing leaks from test data.</p></section>
 <section class="card"><h2><span class="num">3</span>Two protocols</h2><div class="fig">{timeline()}</div>
  <p class="cap">Day-disjoint: train Monday–Wednesday, test Thursday–Friday. Every test attack is a family the model never saw.</p></section>
 <section class="card"><h2 class="s">All four models, both protocols</h2>
  {TABLE}
  <p class="cap">Mean over 5 (random) and 3 (day-disjoint) seeds; only the split differs between the two rows of each model.</p></section>
 <section class="card"><h2 class="s">Is the best model really best?</h2>
  <div class="note"><p><b>XGBoost − Random Forest</b> = 0.00044 macro-F1 (5 seeds)</p>
  <p>paired t-test p = 0.13 · Wilcoxon p = 0.19 · 95 % interval −0.0002 to 0.0011, which includes zero.</p>
  <p>The “best model” claim is unsupported: the data separates two tiers (tree ensembles and the rest), not the winner.</p></div></section>
</div>
<div class="col">
 <section class="card hero-card"><h2 class="a"><span class="num">4</span>Recall collapses</h2><div class="fig">{recall_bars()}</div>
  <div class="silent">{ARROW_ICON}<span>silent failure: false-positive rate even improves</span></div>
  <p class="cap">XGBoost: recall 0.9935 → 0.3164, macro-F1 0.9879 → 0.6887; Random Forest 0.9937 → 0.3109. Missed attack flows rise from 185 to 36,506. The false-positive rate even improves (0.0073 → 0.0030), so the failure is silent.</p></section>
 <section class="card"><h2 class="a"><span class="num">5</span>The ranking inverts</h2><div class="fig">{slope()}</div>
  <p class="cap">Under the day-disjoint split LogReg is first by macro-F1 only by being less selective: FPR 0.0592 against 0.0030 for XGBoost. Threshold-free the order reverses: ROC-AUC 0.6448 against 0.8526. A benchmark that flatters a model can also select the wrong one.</p></section>
 <section class="card"><h2 class="a"><span class="num">6</span>What drives the gap?</h2><div class="fig">{decomposition()}</div>
  <p class="cap">Near-duplicates explain about a hundredth (0.9935 → 0.9821). Benign false-positive rate is 0.0030 on the training days and 0.0033 two days later: no drift. Recall collapses only on unseen families. Leave-one-family-out agrees: botnet 0.0000, port scan 0.0036.</p></section>
</div>
<div class="col">
 <section class="card"><h2 class="a"><span class="num">7</span>Precision at real prevalence</h2><div class="fig">{ppv()}</div>
  <p class="cap">XGBoost, measured TPR and FPR carried to the prevalence of a production link. At one attack per thousand flows, the best case (random split) gives precision 0.120: 7,257 false alerts per million flows, seven of eight alerts false.</p></section>
 <section class="card"><h2><span class="num">8</span>Serving cost, measured</h2><div class="fig">{serving()}</div>
  <p class="cap">The amortised model cost (0.001056 ms/row) would predict 9.5×10⁵ flows/s; the endpoint sustains 404 requests/s before latency collapses, an overstatement of about 2,300×. Killing one of four replicas under load lost 35 of ~8,000 requests and recovered in 3.13 s.</p></section>
 <section class="card callout"><h2 class="s">Evaluate your NIDS this way (G1–G8)</h2>
  {guide_grid()}</section>
 <section class="card"><h2 class="s a">Limits</h2>
  <p class="g">CICIDS2017 has documented labelling defects, so absolute scores are not field accuracy. Two corpora, four conventional models, one serving host with a co-located load generator. Deep sequence models are open under the same protocol.</p></section>
</div>
</div>
<footer>
 <div class="q">{qr('https://github.com/HThanh-how/nids-cicids2017')}<div class="t"><b>Code, manifests and raw results</b><u>github.com/HThanh-how/nids-cicids2017</u></div></div>
 <div class="fc"><div class="big">How Optimistic Is Your Intrusion-Detection Benchmark?</div><b>Huy-Thanh Pham, Anh Truong</b><br>SOICT 2026, paper 9222</div>
 <div class="q" style="justify-content:flex-end">{qr('https://hthanh-how.github.io/nids-cicids2017/')}<div class="t"><b>Slides</b><u>hthanh-how.github.io/nids-cicids2017</u></div></div>
</footer>
</div></body></html>'''


OUT.write_text(page(), encoding='utf-8')
print('wrote', OUT, OUT.stat().st_size)

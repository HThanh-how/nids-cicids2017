# Generates poster.html (A0 portrait, 841 x 1189 mm, light print theme, inline SVG, no JS, no network).
# Every number below is copied from the paper (Source/main.tex and Source/tables/*.tex).
import html, pathlib

OUT = pathlib.Path(__file__).with_name('poster.html')
TEAL, AMB, RED, INK, DIM, GRID = '#0b7a75', '#c2670a', '#b3203f', '#14202b', '#5b6b78', '#d5dde3'
BLUE = '#2b5fa8'
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


# ---------------------------------------------------------------- pipeline (setup)
def pipeline():
    W = 959
    b = []
    steps = [
        ('CICIDS2017', '535,069 flows · 78 features · 14 attack labels', INK),
        ('Fit inside every training split', 'scaler → top-20 feature selection → SMOTE', TEAL),
        ('Four ordinary models, fixed a priori', 'LogReg · Random Forest · XGBoost · MLP, no tuning', TEAL),
        ('Only the split changes', 'random 70/30 (5 seeds) vs day-disjoint (3 seeds)', AMB),
    ]
    y = 0
    for i, (h, s, c) in enumerate(steps):
        b.append(rect(0, y, W, 150, '#f6f9fb', c, 10, 5))
        b.append(t(32, y + 62, h, 44, c, weight=700))
        b.append(t(32, y + 116, s, 34, INK))
        if i < 3:
            b.append(f'<path d="M{W/2-22} {y+158} L{W/2+22} {y+158} L{W/2} {y+190} Z" fill="{DIM}"/>')
        y += 200
    return svg(W, y - 40, ''.join(b), 'Evaluation pipeline')


# ---------------------------------------------------------------- day timeline
def timeline():
    W, H = 959, 760
    days = [('Mon', ['Benign only']), ('Tue', ['FTP-Patator', 'SSH-Patator']),
            ('Wed', ['DoS Hulk', 'GoldenEye', 'slowloris', 'Slowhttptest', 'Heartbleed']),
            ('Thu', ['Web brute f.', 'Web XSS', 'Web SQLi', 'Infiltration']),
            ('Fri', ['Botnet', 'Port scan', 'DDoS'])]
    cw = W / 5
    b = [rect(0, 70, cw * 3, 640, 'rgba(11,122,117,0.09)', TEAL, 8, 4), rect(cw * 3, 70, cw * 2, 640, 'rgba(194,103,10,0.10)', AMB, 8, 4),
         t(cw * 1.5, 48, 'TRAIN (Mon–Wed)', 38, TEAL, 'middle', 700), t(cw * 4, 48, 'TEST (Thu–Fri)', 38, AMB, 'middle', 700)]
    for i, (d, fam) in enumerate(days):
        x = i * cw
        b.append(t(x + cw / 2, 124, d, 44, INK, 'middle', 700))
        col = TEAL if i < 3 else AMB
        for k, f in enumerate(fam):
            yy = 160 + k * 100
            b.append(rect(x + 10, yy, cw - 20, 82, '#ffffff', col, 8, 3))
            b.append(t(x + cw / 2, yy + 52, f, min(30, (cw - 36) / (0.56 * len(f))), INK, 'middle'))
    b.append(t(W / 2, 745, 'each family occurs on exactly one day → family-disjoint', 32, DIM, 'middle'))
    return svg(W, H, ''.join(b), 'Capture days and attack families')


# ---------------------------------------------------------------- grouped bars: recall random vs day-disjoint
def recall_bars():
    W, H = 959, 760
    models = [('LogReg', .9100, .4975), ('RF', .9937, .3109), ('XGBoost', .9935, .3164), ('MLP', .9857, .3467)]
    x0, y0, ph = 90, 680, 520
    b = []
    for k in (0, .25, .5, .75, 1):
        yy = y0 - ph * k
        b.append(line(x0, yy, W, yy))
        b.append(t(x0 - 14, yy + 12, f'{k:.2f}', 30, DIM, 'end'))
    gw = (W - x0) / 4
    for i, (m, r, d) in enumerate(models):
        x = x0 + i * gw + 26
        for j, (v, c) in enumerate(((r, TEAL), (d, AMB))):
            hh = ph * v
            bx = x + j * 100
            b.append(rect(bx, y0 - hh, 88, hh, c, 'none', 4))
            b.append(t(bx + 44, y0 - hh - 14, f'{v:.2f}', 34, c, 'middle', 700))
        b.append(t(x + 94, y0 + 46, m, 34, INK, 'middle'))
    b.append(rect(x0 + 10, 4, 36, 36, TEAL) + t(x0 + 58, 34, 'random split', 32, INK) + rect(x0 + 330, 4, 36, 36, AMB) + t(x0 + 378, 34, 'day-disjoint split', 32, INK))
    b.append(t(0, 30, '', 1))
    return svg(W, H, ''.join(b), 'Attack recall under both protocols')


# ---------------------------------------------------------------- slope chart: macro-F1 ranking
def slope():
    W, H = 959, 700
    data = [('XGBoost', .9879, .6887, TEAL), ('RF', .9874, .6852, BLUE), ('MLP', .9491, .6928, '#7a4fa8'), ('LogReg', .8515, .7433, AMB)]
    xl, xr, top, bot = 330, 630, 40, 600
    lo, hi = .64, 1.0

    def Y(v):
        return bot - (v - lo) / (hi - lo) * (bot - top)
    b = [t(xl, 28, 'random', 34, TEAL, 'middle', 700), t(xr, 28, 'day-disjoint', 34, AMB, 'middle', 700)]
    b.append(line(xl, top + 10, xl, bot + 10, GRID, 4) + line(xr, top + 10, xr, bot + 10, GRID, 4))
    # label offsets to avoid overlap
    left_off = {'XGBoost': -14, 'RF': 22, 'MLP': 0, 'LogReg': 0}
    right_off = {'XGBoost': 8, 'RF': 36, 'MLP': -26, 'LogReg': 0}
    for m, a, d, c in data:
        b.append(f'<line x1="{xl}" y1="{Y(a)}" x2="{xr}" y2="{Y(d)}" stroke="{c}" stroke-width="9" stroke-linecap="round"/>')
        b.append(f'<circle cx="{xl}" cy="{Y(a)}" r="13" fill="{c}"/><circle cx="{xr}" cy="{Y(d)}" r="13" fill="{c}"/>')
        b.append(t(xl - 24, Y(a) + 12 + left_off[m], f'{m} {a:.4f}', 32, c, 'end', 700))
        b.append(t(xr + 24, Y(d) + 12 + right_off[m], f'{d:.4f} {m}', 32, c, 'start', 700))
    b.append(t(W / 2, 672, 'macro-F1 · LogReg: last → first', 34, INK, 'middle', 700))
    return svg(W, H, ''.join(b), 'Macro-F1 ranking inversion')


# ---------------------------------------------------------------- decomposition (XGBoost recall)
def decomposition():
    W, H = 959, 760
    items = [('random split', .9935, TEAL), ('random, grouped\nno near-duplicates', .9821, TEAL),
             ('seen families,\nsame days', .9975, TEAL), ('UNSEEN families\n(Thu–Fri attacks)', .3218, AMB)]
    x0, y0, ph = 70, 610, 470
    b = []
    for k in (0, .5, 1):
        yy = y0 - ph * k
        b.append(line(x0, yy, W, yy)); b.append(t(x0 - 12, yy + 12, f'{k:.1f}', 30, DIM, 'end'))
    bw = 170
    gap = (W - x0 - 4 * bw) / 4
    for i, (lab, v, c) in enumerate(items):
        x = x0 + gap / 2 + i * (bw + gap)
        hh = ph * v
        b.append(rect(x, y0 - hh, bw, hh, c, 'none', 4))
        b.append(t(x + bw / 2, y0 - hh - 14, f'{v:.4f}', 34, c, 'middle', 700))
        for k, ln in enumerate(lab.split('\n')):
            b.append(t(x + bw / 2, y0 + 44 + k * 34, ln, 28, INK, 'middle', 700 if 'UNSEEN' in ln else 400))
    b.append(t(W / 2, 740, 'XGBoost attack recall', 32, DIM, 'middle'))
    return svg(W, H, ''.join(b), 'Decomposition of the gap')


# ---------------------------------------------------------------- precision at prevalence
def ppv():
    W, H = 959, 700
    groups = [('1 in 100', .580, .515), ('1 in 1,000', .120, .095), ('1 in 10,000', .0135, .0104)]
    x0, y0, ph = 70, 590, 470
    b = []
    for k in (0, .25, .5, .75, 1):
        yy = y0 - ph * k
        b.append(line(x0, yy, W, yy)); b.append(t(x0 - 12, yy + 12, f'{k:.2f}', 30, DIM, 'end'))
    gw = (W - x0) / 3
    for i, (lab, r, d) in enumerate(groups):
        x = x0 + i * gw + 30
        for j, (v, c) in enumerate(((r, TEAL), (d, AMB))):
            hh = max(ph * v, 4)
            bx = x + j * 120
            b.append(rect(bx, y0 - hh, 108, hh, c, 'none', 4))
            b.append(t(bx + 54, y0 - hh - 14, {0.58:'0.580',0.515:'0.515',0.12:'0.120',0.095:'0.095',0.0135:'0.0135',0.0104:'0.0104'}[v], 30, c, 'middle', 700))
        b.append(t(x + 114, y0 + 44, lab, 32, INK, 'middle'))
    b.append(t(W / 2, 680, 'attack prevalence on the link', 32, DIM, 'middle'))
    b.append(rect(x0 + 10, 4, 34, 34, TEAL) + t(x0 + 56, 32, 'random', 30, INK) + rect(x0 + 260, 4, 34, 34, AMB) + t(x0 + 306, 32, 'day-disjoint', 30, INK))
    return svg(W, H, ''.join(b), 'XGBoost precision at operational prevalence')


# ---------------------------------------------------------------- serving (log scale) + stage breakdown
def serving():
    import math
    W, H = 959, 980
    bars = [('predicted from model cost', 950000, '9.5×10⁵ flows/s', AMB), ('batch of 256', 34662, '34,662 flows/s', BLUE),
            ('measured, best config', 404, '404 requests/s', TEAL), ('default threads, 8 clients', 309, '309 requests/s', DIM)]
    x0, maxv = 40, 6.2
    b = []
    y = 20
    for lab, v, txt, c in bars:
        w = (math.log10(v) / maxv) * (W - 2 * x0)
        b.append(t(x0, y + 28, lab, 32, INK, weight=700))
        b.append(rect(x0, y + 44, w, 58, c, 'none', 4))
        b.append(t(x0 + w + 18 if w < 500 else x0 + w - 18, y + 90, txt, 36, INK if w < 500 else '#fff', 'start' if w < 500 else 'end', 700))
        y += 138
    b.append(t(x0, y + 8, 'log scale · one flow per request pays the call cost each time', 28, DIM))
    # stage stack
    y += 60
    tot = 2.93
    parts = [('model call + scaling', 1.04, TEAL), ('web framework', .81, BLUE), ('transport + ASGI + client', 1.08, DIM)]
    b.append(t(x0, y + 24, 'where one request spends 2.93 ms (1 maths thread)', 34, INK, weight=700))
    x = x0
    for lab, v, c in parts:
        w = v / tot * (W - 2 * x0)
        b.append(rect(x, y + 50, w, 80, c, '#fff', 0, 3))
        b.append(t(x + w / 2, y + 102, f'{v:.2f} ms', 34, '#fff', 'middle', 700))
        b.append(t(x + w / 2, y + 170, lab, 26, INK, 'middle') if False else '')
        x += w
    yy = y + 170
    b.append(t(x0, yy, '■ model call + scaling 1.04', 28, TEAL, weight=700))
    b.append(t(x0, yy + 38, '■ web framework 0.81', 28, BLUE, weight=700))
    b.append(t(x0, yy + 76, '■ transport, ASGI server, co-located client 1.08', 28, DIM, weight=700))
    return svg(W, yy + 100, ''.join(b), 'Serving throughput and per-stage time')


CSS = f'''
@page {{ size: 841mm 1189mm; margin: 0 }}
* {{ box-sizing: border-box }}
html,body {{ margin:0; padding:0; background:#fff }}
body {{ width:841mm; height:1189mm; overflow:hidden; font-family: Arial, "Segoe UI", sans-serif; color:{INK} }}
.poster {{ width:3178px; height:4494px; padding:70px 90px 60px; position:relative; background:#fff }}
header {{ display:grid; grid-template-columns: 1fr 640px; gap:60px; border-bottom:10px solid {TEAL}; padding-bottom:30px; height:640px }}
h1 {{ font-size:140px; line-height:1.04; margin:0 0 30px; letter-spacing:-1px }}
.sub {{ font-size:62px; color:{TEAL}; margin:0 0 26px; font-weight:700 }}
.au {{ font-size:50px; margin:0 }} .af {{ font-size:34px; color:{DIM}; margin:10px 0 0; line-height:1.25 }}
.key {{ background:{TEAL}; color:#fff; padding:34px 44px; border-radius:18px; font-size:42px; line-height:1.25; align-self:start }}
.key b {{ font-size:96px; display:block; line-height:1 }}
.cols {{ display:grid; grid-template-columns:repeat(3,1fr); gap:60px; margin-top:40px; height:3590px }}
.col > section {{ margin-bottom:46px }}
h2 {{ font-size:60px; margin:0 0 20px; color:{TEAL}; border-left:16px solid {TEAL}; padding-left:22px; line-height:1.1 }}
h2.a {{ color:{AMB}; border-color:{AMB} }}
p, li {{ font-size:40px; line-height:1.3; margin:0 0 16px }}
ul {{ margin:0; padding-left:44px }}
.fig {{ margin:10px 0 0 }} .fig svg {{ width:100%; height:auto; display:block }}
.cap {{ font-size:32px; color:{DIM}; margin:8px 0 0; line-height:1.25 }}
.note {{ background:#f6f9fb; border:4px solid {GRID}; border-radius:14px; padding:24px 28px }}
.note p {{ margin:0 0 10px }}
.tb {{ width:100%; border-collapse:collapse; font-size:36px }} .tb th,.tb td {{ border-bottom:3px solid {GRID}; padding:7px 10px; text-align:right }} .tb th:first-child,.tb td:first-child,.tb th:nth-child(2),.tb td:nth-child(2) {{ text-align:left }} .tb th {{ color:{TEAL} }}
.g {{ font-size:36px; line-height:1.25; margin:0 0 12px }} .g b {{ color:{TEAL} }}
footer {{ position:absolute; left:90px; right:90px; bottom:40px; border-top:6px solid {GRID}; padding-top:20px; display:flex; justify-content:space-between; font-size:36px; color:{DIM} }}
footer b {{ color:{INK} }}
@media screen {{ body {{ overflow:auto; height:auto }} }}
'''


def page():
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SOICT 2026 poster · How Optimistic Is Your Intrusion-Detection Benchmark?</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head>
<body><div class="poster">
<header>
 <div>
  <h1>How Optimistic Is Your Intrusion-Detection Benchmark?</h1>
  <p class="sub">Leakage-resistant evaluation and measured serving cost</p>
  <p class="au"><b>Huy-Thanh Pham</b><sup>1,2</sup> · <b>Anh Truong</b><sup>*,1,2</sup></p>
  <p class="af"><sup>1</sup> Ho Chi Minh City University of Technology (HCMUT) · <sup>2</sup> Vietnam National University Ho Chi Minh City · * anhtt@hcmut.edu.vn · SOICT 2026, paper 9222</p>
 </div>
 <div class="key"><b>0.99 → 0.32</b>XGBoost attack recall on CICIDS2017 when only the split changes: from a random split to a split that shares no attack family.</div>
</header>
<div class="cols">
<div class="col">
 <section><h2>The problem</h2>
  <p>Learned detectors report macro-F1 above <b>0.98</b> on public benchmarks as a matter of routine. Practitioners do not see that performance in the field.</p>
  <p>A random split scatters every attack episode across the train/test boundary, so the model is tested on traffic it has already seen. We keep models, hyperparameters and preprocessing fixed, vary <b>only the evaluation</b>, and measure how much of a score belongs to the protocol.</p></section>
 <section><h2>Fixed pipeline</h2><div class="fig">{pipeline()}</div>
  <p class="cap">Standardisation, selection and oversampling are part of the model: re-fitted inside every training split, so nothing leaks from test data.</p></section>
 <section><h2>Two protocols</h2><div class="fig">{timeline()}</div>
  <p class="cap">Day-disjoint: train Monday–Wednesday, test Thursday–Friday. Every test attack is a family the model never saw.</p></section>
 <section><h2 class="a">What drives the gap?</h2><div class="fig">{decomposition()}</div>
  <p class="cap">Near-duplicates explain about a hundredth (0.9935 → 0.9821). Benign false-positive rate is 0.0030 on the training days and 0.0033 two days later: no drift. Recall collapses only on unseen families. Leave-one-family-out agrees: botnet 0.0000, port scan 0.0036.</p></section>
</div>
<div class="col">
 <section><h2 class="a">Recall collapses</h2><div class="fig">{recall_bars()}</div>
  <p class="cap">XGBoost: recall 0.9935 → 0.3164, macro-F1 0.9879 → 0.6887; Random Forest 0.9937 → 0.3109. Missed attack flows rise from 185 to 36,506. The false-positive rate even improves (0.0073 → 0.0030), so the failure is silent.</p></section>
 <section><h2 class="a">The ranking inverts</h2><div class="fig">{slope()}</div>
  <p class="cap">Under the day-disjoint split LogReg is first by macro-F1 only by being less selective: FPR 0.0592 against 0.0030 for XGBoost. Threshold-free the order reverses: ROC-AUC 0.6448 against 0.8526. A benchmark that flatters a model can also select the wrong one.</p></section>
 <section><h2>Is the best model really best?</h2>
  <div class="note"><p><b>XGBoost − Random Forest</b> = 0.00044 macro-F1 (5 seeds)</p>
  <p>paired t-test p = 0.13 · Wilcoxon p = 0.19 · 95 % interval −0.0002 to 0.0011, which includes zero.</p>
  <p>The “best model” claim is unsupported: the data separates two tiers (tree ensembles and the rest), not the winner.</p></div></section>

 <section><h2>All four models, both protocols</h2>
  <table class="tb"><tr><th>Model</th><th>Split</th><th>Macro-F1</th><th>Recall</th><th>FPR</th></tr><tr><td><b>LogReg</b></td><td>random</td><td>0.8515</td><td>0.9100</td><td>0.1010</td></tr><tr><td><b></b></td><td>day-disj.</td><td>0.7433</td><td>0.4975</td><td>0.0592</td></tr><tr><td><b>RF</b></td><td>random</td><td>0.9874</td><td>0.9937</td><td>0.0076</td></tr><tr><td><b></b></td><td>day-disj.</td><td>0.6852</td><td>0.3109</td><td>0.0029</td></tr><tr><td><b>XGBoost</b></td><td>random</td><td>0.9879</td><td>0.9935</td><td>0.0073</td></tr><tr><td><b></b></td><td>day-disj.</td><td>0.6887</td><td>0.3164</td><td>0.0030</td></tr><tr><td><b>MLP</b></td><td>random</td><td>0.9491</td><td>0.9857</td><td>0.0359</td></tr><tr><td><b></b></td><td>day-disj.</td><td>0.6928</td><td>0.3467</td><td>0.0211</td></tr></table>
  <p class="cap">Mean over 5 (random) and 3 (day-disjoint) seeds; only the split differs between the two rows of each model.</p></section>
</div>
<div class="col">
 <section><h2 class="a">Precision at real prevalence</h2><div class="fig">{ppv()}</div>
  <p class="cap">XGBoost, measured TPR and FPR carried to the prevalence of a production link. At one attack per thousand flows, the best case (random split) gives precision 0.120: 7,257 false alerts per million flows, seven of eight alerts false.</p></section>
 <section><h2>Serving cost, measured</h2><div class="fig">{serving()}</div>
  <p class="cap">The amortised model cost (0.001056 ms/row) would predict 9.5×10⁵ flows/s; the endpoint sustains 404 requests/s before latency collapses, an overstatement of about 2,300×. Killing one of four replicas under load lost 35 of ~8,000 requests and recovered in 3.13 s.</p></section>
 <section><h2>Evaluate your NIDS this way</h2>
  <p class="g"><b>G1</b> report a split that shares no attack family beside the random one, and the gap · <b>G2</b> fit scaling, selection and oversampling inside each training split · <b>G3</b> per-family recall with test counts, leave-one-family-out · <b>G4</b> seeds, intervals, paired tests · <b>G5</b> rank at a stated operating point or threshold-free · <b>G6</b> state prevalence and translate error rates to the intended link · <b>G7</b> document feature alignment for cross-dataset claims · <b>G8</b> measure the served endpoint by stage; never convert an amortised model cost into a throughput.</p></section>
 <section><h2>Limits</h2>
  <p class="g">CICIDS2017 has documented labelling defects, so absolute scores are not field accuracy. Two corpora, four conventional models, one serving host with a co-located load generator. Deep sequence models are open under the same protocol.</p></section>
</div>
</div>
<footer><span><b>Code, manifests and raw results:</b> github.com/HThanh-how/nids-cicids2017</span><span>Slides: hthanh-how.github.io/nids-cicids2017</span></footer>
</div></body></html>'''


OUT.write_text(page(), encoding='utf-8')
print('wrote', OUT, OUT.stat().st_size)

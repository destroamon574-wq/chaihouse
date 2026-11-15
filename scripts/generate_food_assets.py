"""Генератор локальных SVG-иллюстраций блюд (запускается вручную)."""
from __future__ import annotations

import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "img"
OUT.mkdir(parents=True, exist_ok=True)


def bokeh(seed: int, color: str = "#e6b35f") -> str:
    rnd = random.Random(seed)
    circles = []
    for _ in range(16):
        x = rnd.randint(30, 770)
        y = rnd.randint(20, 300)
        r = rnd.randint(4, 26)
        op = round(rnd.uniform(0.03, 0.13), 3)
        circles.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" opacity="{op}"/>')
    return "\n".join(circles)


def wood_bg(seed: int, light: str = "#3a271b", dark: str = "#1b110c") -> str:
    return f"""
  <defs>
    <linearGradient id="table" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{light}"/>
      <stop offset=".55" stop-color="#2a1b12"/>
      <stop offset="1" stop-color="{dark}"/>
    </linearGradient>
    <radialGradient id="light" cx=".38" cy=".26" r=".75">
      <stop offset="0" stop-color="#ffd79a" stop-opacity=".32"/>
      <stop offset=".55" stop-color="#c9833e" stop-opacity=".10"/>
      <stop offset="1" stop-color="#000" stop-opacity="0"/>
    </radialGradient>
    <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="16"/>
    </filter>
    <filter id="soft" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="5"/>
    </filter>
    <filter id="grain">
      <feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/>
      <feColorMatrix type="saturate" values="0"/>
      <feComponentTransfer><feFuncA type="linear" slope=".08"/></feComponentTransfer>
    </filter>
  </defs>
  <rect width="800" height="600" fill="url(#table)"/>
  <g opacity=".5">
    {"".join(f'<path d="M0 {y} H800" stroke="#0f0906" stroke-width="1" opacity=".7"/>' for y in range(40, 600, 52))}
    {"".join(f'<path d="M0 {y} H800" stroke="#8b5b34" stroke-width="1" opacity=".16"/>' for y in range(56, 600, 52))}
  </g>
  <rect width="800" height="600" fill="url(#light)"/>
  {bokeh(seed)}
  <rect width="800" height="600" filter="url(#grain)" opacity=".55"/>
"""


def herbs(x: int, y: int, color: str = "#5f8a45", scale: float = 1.0, flip: bool = False) -> str:
    sign = -1 if flip else 1
    return f"""
  <g transform="translate({x} {y}) scale({scale * sign} {scale})" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round">
    <path d="M0 26 C0 10 2 -4 6 -18"/>
    <path d="M2 8 C-7 2 -12 -6 -14 -14" />
    <path d="M4 14 C13 8 18 0 20 -10" />
    <path d="M0 22 C-9 16 -14 8 -16 0" />
    <g fill="{color}" stroke="none" opacity=".9">
      <ellipse cx="-11" cy="-10" rx="6" ry="3" transform="rotate(-35 -11 -10)"/>
      <ellipse cx="14" cy="-6" rx="7" ry="3.4" transform="rotate(30 14 -6)"/>
      <ellipse cx="-12" cy="4" rx="6" ry="3" transform="rotate(-50 -12 4)"/>
      <ellipse cx="12" cy="3" rx="6" ry="3" transform="rotate(20 12 3)"/>
      <ellipse cx="5" cy="-14" rx="5" ry="2.8" transform="rotate(70 5 -14)"/>
    </g>
  </g>"""


def steam(x: int, y: int, color: str = "#fff5df") -> str:
    return f"""
  <g fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" opacity=".27">
    <path d="M{x-24} {y} C{x-44} {y-46} {x-4} {y-64} {x-22} {y-112}">
      <animate attributeName="opacity" values=".15;.35;.15" dur="5s" repeatCount="indefinite"/>
    </path>
    <path d="M{x+24} {y-6} C{x+44} {y-50} {x+6} {y-76} {x+26} {y-124}">
      <animate attributeName="opacity" values=".3;.12;.3" dur="6s" repeatCount="indefinite"/>
    </path>
  </g>"""


def plate(rx: int = 292, ry: int = 186, cy: int = 340) -> str:
    return f"""
  <ellipse cx="400" cy="{cy + 30}" rx="{rx + 12}" ry="{ry + 12}" fill="#000" opacity=".45" filter="url(#shadow)"/>
  <ellipse cx="400" cy="{cy}" rx="{rx}" ry="{ry}" fill="#efe4d2"/>
  <ellipse cx="400" cy="{cy}" rx="{rx - 20}" ry="{ry - 16}" fill="#faf3e8"/>
  <ellipse cx="400" cy="{cy}" rx="{rx - 54}" ry="{ry - 44}" fill="#f5ead9"/>
  <path d="M{400-rx+28} {cy-40} Q400 {cy-ry-4} {400+rx-28} {cy-40}" fill="none" stroke="#fff" stroke-width="5" opacity=".55"/>
"""


def board(cy: int = 340) -> str:
    return f"""
  <ellipse cx="400" cy="{cy + 36}" rx="324" ry="182" fill="#000" opacity=".42" filter="url(#shadow)"/>
  <rect x="92" y="{cy - 150}" width="616" height="300" rx="58" fill="#7b4a29"/>
  <rect x="108" y="{cy - 136}" width="584" height="272" rx="46" fill="#9a6236"/>
  <g opacity=".22" stroke="#3c2111" stroke-width="2">
    {"".join(f'<path d="M130 {cy - 100 + i * 26} H670"/>' for i in range(9))}
  </g>
"""


def bowl(cy: int = 330, broth: str = "#b95c27") -> str:
    return f"""
  <ellipse cx="400" cy="{cy + 52}" rx="268" ry="152" fill="#000" opacity=".4" filter="url(#shadow)"/>
  <ellipse cx="400" cy="{cy}" rx="268" ry="150" fill="#d9c1a0"/>
  <ellipse cx="400" cy="{cy}" rx="244" ry="130" fill="{broth}"/>
  <ellipse cx="400" cy="{cy + 6}" rx="244" ry="130" fill="none" stroke="#7a2d12" stroke-width="8" opacity=".3"/>
  <ellipse cx="400" cy="{cy - 6}" rx="220" ry="112" fill="{broth}"/>
  <path d="M170 {cy-10} Q400 {cy-210} 630 {cy-10}" fill="none" stroke="#fff" stroke-width="4" opacity=".18"/>
"""


def rice_mound(seed: int = 3, cx: int = 400, cy: int = 330, rx: int = 200, ry: int = 100) -> str:
    rnd = random.Random(seed)
    grains = []
    for _ in range(420):
        angle = rnd.random() * 6.283
        radius = rnd.random() ** 0.6
        x = cx + radius * rx * rnd.uniform(0.2, 1) * (1 if rnd.random() > .5 else -1)
        y = cy + radius * ry * rnd.uniform(0.2, 1) * (1 if rnd.random() > .5 else -1)
        rot = rnd.randint(0, 180)
        length = rnd.randint(5, 11)
        color = rnd.choice(["#f3e2b8", "#e9d29b", "#f8ebc9", "#dcc389"])
        grains.append(
            f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{length}" ry="2.4" fill="{color}" '
            f'opacity=".9" transform="rotate({rot} {x:.0f} {y:.0f})"/>'
        )
    return "".join(grains)


def meat_chunks(seed: int = 4, cx: int = 400, cy: int = 300, count: int = 14) -> str:
    rnd = random.Random(seed)
    chunks = []
    colors = ["#6b3420", "#7c3e24", "#8a4a2b", "#5c2c1a"]
    for _ in range(count):
        x = cx + rnd.randint(-175, 175)
        y = cy + rnd.randint(-80, 80)
        w = rnd.randint(28, 48)
        h = rnd.randint(20, 34)
        rot = rnd.randint(-35, 35)
        color = rnd.choice(colors)
        chunks.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{color}" '
            f'transform="rotate({rot} {x + w/2} {y + h/2})"/>'
            f'<path d="M{x+8} {y+7} q{w/3} -6 {w-16} 1" stroke="#c1784d" stroke-width="3" '
            f'fill="none" opacity=".45" transform="rotate({rot} {x + w/2} {y + h/2})"/>'
        )
    return "".join(chunks)


def carrots(seed: int = 5, cx: int = 400, cy: int = 320, count: int = 22) -> str:
    rnd = random.Random(seed)
    strips = []
    for _ in range(count):
        x = cx + rnd.randint(-190, 175)
        y = cy + rnd.randint(-90, 90)
        length = rnd.randint(28, 55)
        rot = rnd.randint(-60, 60)
        strips.append(
            f'<rect x="{x}" y="{y}" width="{length}" height="5" rx="2.5" fill="#e79132" '
            f'transform="rotate({rot} {x} {y})" opacity=".92"/>'
        )
    return "".join(strips)


def svg_doc(body: str, title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" role="img" aria-label="{title}">
  <title>{title}</title>
  {body}
</svg>
"""


def make_plov() -> str:
    body = f"""
  {wood_bg(11)}
  {plate()}
  {rice_mound(3)}
  {carrots(7)}
  {meat_chunks(4)}
  <g>
    <ellipse cx="520" cy="250" rx="42" ry="34" fill="#efe7d5"/>
    <path d="M492 238 q28 -30 56 0 q-6 30 -28 34 q-22 -4 -28 -34" fill="#f6efdf"/>
    <path d="M520 214 l-3 34" stroke="#d8c9a9" stroke-width="3"/>
    <path d="M500 286 q20 12 40 0" stroke="#c3ae89" stroke-width="4" fill="none"/>
  </g>
  {herbs(300, 250, "#5c8a46", 1.1, True)}
  {herbs(520, 386, "#5c8a46", .9)}
  <g transform="translate(260 410)">
    <path d="M0 0 q32 -26 64 0 q-8 30 -32 30 q-24 0 -32 -30" fill="#b23a2c"/>
    <path d="M24 -6 q8 -12 16 0" stroke="#f3d7b4" stroke-width="3" fill="none"/>
  </g>
  <ellipse cx="620" cy="420" rx="62" ry="30" fill="#f4ead8" opacity=".92"/>
  <ellipse cx="620" cy="416" rx="50" ry="20" fill="#9a3a29"/>
  <path d="M590 414 q30 16 60 0" stroke="#e8b46d" stroke-width="4" fill="none" opacity=".7"/>
"""
    return svg_doc(body, "Плов с бараниной, морковью и чесноком")


def make_lagman() -> str:
    noodles = "".join(
        f'<path d="M{250 + i*11} {250 + (i%3)*30} q40 -34 80 0 q40 34 80 0 q40 -34 80 0" '
        f'fill="none" stroke="#f0d9a8" stroke-width="7" stroke-linecap="round" opacity=".95"/>'
        for i in range(12)
    )
    body = f"""
  {wood_bg(12, "#3d2a1c", "#160e0a")}
  {bowl(330, "#b85a26")}
  {noodles}
  <g fill="#7b3a20">
    <rect x="300" y="270" width="48" height="28" rx="8" transform="rotate(-12 324 284)"/>
    <rect x="430" y="300" width="44" height="26" rx="8" transform="rotate(16 452 313)"/>
    <rect x="360" y="350" width="40" height="24" rx="7" transform="rotate(-6 380 362)"/>
  </g>
  <g fill="#d94b2a">
    <path d="M280 320 q30 -22 60 0 q-28 20 -60 0"/>
    <path d="M470 260 q26 -20 54 0 q-26 18 -54 0"/>
  </g>
  <g fill="#5f8b3f">
    <ellipse cx="340" cy="320" rx="22" ry="9" transform="rotate(-28 340 320)"/>
    <ellipse cx="480" cy="360" rx="24" ry="9" transform="rotate(22 480 360)"/>
    <ellipse cx="400" cy="390" rx="20" ry="8" transform="rotate(-8 400 390)"/>
  </g>
  {herbs(560, 240, "#6b9b4d", .9, True)}
  {steam(400, 250)}
"""
    return svg_doc(body, "Лагман с тянутой лапшой и говядиной")


def make_shurpa() -> str:
    body = f"""
  {wood_bg(13, "#38261a", "#170f0b")}
  {bowl(330, "#d19545")}
  <g>
    <rect x="300" y="290" width="62" height="42" rx="12" fill="#7d472b"/>
    <rect x="420" y="320" width="56" height="38" rx="11" fill="#8d5231"/>
    <circle cx="380" cy="280" r="28" fill="#e1b568"/>
    <circle cx="470" cy="292" r="22" fill="#d8a85c"/>
    <path d="M320 350 q34 -18 68 0 q-34 20 -68 0" fill="#d7642f"/>
    <ellipse cx="440" cy="372" rx="34" ry="18" fill="#e4c17a"/>
    <ellipse cx="300" cy="350" rx="18" ry="26" fill="#9db85e" transform="rotate(-20 300 350)"/>
  </g>
  <g fill="#5f8b3f">
    <ellipse cx="500" cy="360" rx="24" ry="9" transform="rotate(24 500 360)"/>
    <ellipse cx="360" cy="390" rx="22" ry="8" transform="rotate(-8 360 390)"/>
  </g>
  <path d="M250 310 q30 -16 58 0" stroke="#f7e5bb" stroke-width="3" fill="none" opacity=".6"/>
  {steam(400, 240)}
  <circle cx="610" cy="430" r="34" fill="#efe5d5"/>
  <circle cx="610" cy="430" r="24" fill="#b53c2b"/>
  {herbs(230, 430, "#628c46", .8, True)}
"""
    return svg_doc(body, "Шурпа из баранины с овощами")


def make_manti() -> str:
    manti = []
    positions = [(300, 300), (400, 270), (500, 300), (330, 390), (430, 400), (530, 380)]
    for index, (x, y) in enumerate(positions):
        rot = (-18, -6, 10, -8, 4, 18)[index]
        manti.append(f"""
    <g transform="translate({x} {y}) rotate({rot})">
      <ellipse cx="0" cy="16" rx="62" ry="36" fill="#000" opacity=".18" filter="url(#soft)"/>
      <path d="M-58 12 Q0 -46 58 12 Q0 62 -58 12" fill="#edd9ae"/>
      <path d="M-40 12 Q0 44 40 12" fill="#f6e7c6" opacity=".8"/>
      <path d="M0 -22 q16 18 0 34 q-16 -16 0 -34" fill="#e5c891"/>
      <path d="M-26 -2 q12 -14 24 -18 M26 -2 q-12 -14 -24 -18" stroke="#c7a66a" stroke-width="2.5" fill="none"/>
    </g>""")
    body = f"""
  {wood_bg(14, "#3b291c", "#170f0a")}
  {plate(300, 200, 340)}
  <g>{"".join(manti)}</g>
  <g transform="translate(620 270)">
    <ellipse cx="0" cy="10" rx="48" ry="26" fill="#000" opacity=".2" filter="url(#soft)"/>
    <ellipse cx="0" cy="0" rx="48" ry="26" fill="#f6eddc"/>
    <ellipse cx="0" cy="-2" rx="36" ry="17" fill="#fffaf0"/>
    <path d="M-16 -8 q16 10 32 0" stroke="#e2d2b6" stroke-width="3" fill="none"/>
  </g>
  {herbs(250, 410, "#5d8b45", .9, True)}
  {herbs(570, 440, "#5d8b45", .8)}
  <g fill="#b23a2c">
    <ellipse cx="600" cy="380" rx="14" ry="8" transform="rotate(-30 600 380)"/>
    <ellipse cx="635" cy="400" rx="12" ry="7" transform="rotate(24 635 400)"/>
  </g>
  {steam(420, 240)}
"""
    return svg_doc(body, "Манты с бараниной на пару")


def make_samsa() -> str:
    items = []
    for index, (x, y, rot) in enumerate([(330, 300, -14), (445, 265, 8), (390, 390, -3)]):
        items.append(f"""
    <g transform="translate({x} {y}) rotate({rot})">
      <ellipse cx="0" cy="52" rx="86" ry="28" fill="#000" opacity=".18" filter="url(#soft)"/>
      <path d="M-84 40 L0 -66 L84 40 Q0 76 -84 40Z" fill="#c98a45"/>
      <path d="M-72 34 L0 -50 L72 34 Q0 62 -72 34Z" fill="#e0a75c"/>
      <path d="M-58 28 L0 -34 L58 28 Q0 48 -58 28Z" fill="#efc47e"/>
      <g fill="#f6e3b6">
        <circle cx="-24" cy="6" r="3"/><circle cx="-8" cy="-8" r="2.6"/><circle cx="8" cy="10" r="3"/>
        <circle cx="26" cy="-2" r="2.4"/><circle cx="-2" cy="22" r="2.8"/><circle cx="38" cy="20" r="2.2"/>
      </g>
    </g>""")
    body = f"""
  {wood_bg(15, "#3c2a1d", "#180f0a")}
  {plate(300, 190, 340)}
  <g>{"".join(items)}</g>
  {herbs(250, 420, "#5e8c47", .8, True)}
  {steam(390, 210)}
  <circle cx="620" cy="430" r="38" fill="#f1e7d7"/>
  <circle cx="620" cy="430" r="28" fill="#b23e2d"/>
  <path d="M592 428 q28 14 56 0" stroke="#eab46b" stroke-width="4" fill="none"/>
"""
    return svg_doc(body, "Самса из тандыра с бараниной")


def make_shashlik() -> str:
    skewers = []
    for row, y in enumerate((300, 370)):
        cubes = []
        for i in range(4):
            x = 230 + i * 82 + (row * 10)
            cubes.append(f'<rect x="{x}" y="{y-26}" width="66" height="50" rx="12" fill="#713a22"/>'
                         f'<path d="M{x+10} {y-14} h44" stroke="#a9623c" stroke-width="4" opacity=".5"/>')
        skewers.append(f"""
    <g>
      <path d="M170 {y} L650 {y}" stroke="#c9a97a" stroke-width="7" stroke-linecap="round"/>
      {''.join(cubes)}
      <path d="M154 {y} q-10 -8 0 -16" stroke="#c9a97a" stroke-width="7" fill="none"/>
    </g>""")
    body = f"""
  {wood_bg(16, "#3d2a1c", "#170e09")}
  {board(340)}
  <g>{"".join(skewers)}</g>
  <g fill="none" stroke="#d9c7a5" stroke-width="5">
    <circle cx="620" cy="280" r="30"/><circle cx="620" cy="280" r="18"/>
    <circle cx="600" cy="350" r="26"/><circle cx="600" cy="350" r="14"/>
  </g>
  <g transform="translate(170 430)">
    <path d="M0 0 q42 -24 84 0 q-42 34 -84 0" fill="#a12f26"/>
    <path d="M22 -4 q20 12 40 0" stroke="#e9b96e" stroke-width="4" fill="none"/>
  </g>
  <g transform="translate(250 220) rotate(-18)">
    <path d="M0 0 q32 -18 64 0 q-32 24 -64 0" fill="#d9542e"/>
  </g>
  {herbs(330, 430, "#5f8d47", .9)}
  {herbs(500, 250, "#5f8d47", .9, True)}
  {steam(400, 220)}
"""
    return svg_doc(body, "Шашлык из баранины на углях")


def make_kebab() -> str:
    body = f"""
  {wood_bg(17, "#3a281b", "#160e0a")}
  {board(340)}
  <g>
    <rect x="190" y="300" width="420" height="46" rx="23" fill="#7a3d22" transform="rotate(-4 400 323)"/>
    <rect x="200" y="386" width="400" height="42" rx="21" fill="#834326" transform="rotate(3 400 407)"/>
    <g stroke="#4a2111" stroke-width="5" opacity=".55">
      <path d="M240 302 l18 30"/><path d="M300 302 l18 30"/><path d="M360 302 l18 30"/>
      <path d="M420 302 l18 30"/><path d="M480 302 l18 30"/><path d="M540 302 l18 30"/>
      <path d="M250 390 l18 28"/><path d="M320 390 l18 28"/><path d="M390 390 l18 28"/>
      <path d="M460 390 l18 28"/><path d="M530 390 l18 28"/>
    </g>
    <path d="M180 320 L160 320" stroke="#c9a97a" stroke-width="6"/>
  </g>
  <g transform="translate(610 260)">
    <circle cx="0" cy="0" r="44" fill="#c04a2a"/>
    <path d="M0 -44 q18 22 0 44 q-18 -22 0 -44" fill="#e07a3b"/>
    <circle cx="0" cy="0" r="44" fill="none" stroke="#f0c58c" stroke-width="4" opacity=".5"/>
  </g>
  <g transform="translate(620 390)">
    <ellipse cx="0" cy="0" rx="58" ry="30" fill="#f3e8d5"/>
    <g fill="#a8588a" opacity=".85">
      <circle cx="-28" cy="-8" r="7"/><circle cx="-6" cy="2" r="6"/><circle cx="20" cy="-10" r="7"/>
      <circle cx="38" cy="4" r="5"/><circle cx="-16" cy="14" r="5"/>
    </g>
    <path d="M-38 12 q38 14 76 0" stroke="#d9c3a0" stroke-width="3" fill="none"/>
  </g>
  <g transform="translate(160 250)">
    <path d="M0 0 q30 -20 60 0 q-30 26 -60 0" fill="#e7d3ab"/>
    <path d="M10 8 q20 8 40 0" stroke="#c0a678" stroke-width="3" fill="none"/>
  </g>
  {herbs(320, 460, "#608e48", .9)}
"""
    return svg_doc(body, "Люля-кебаб с печёными овощами")


def make_eggplant() -> str:
    rolls = []
    for index, (x, y, rot) in enumerate([(300, 300, -18), (380, 270, 8), (460, 300, 24),
                                         (330, 380, -8), (430, 390, 12)]):
        rolls.append(f"""
    <g transform="translate({x} {y}) rotate({rot})">
      <ellipse cx="0" cy="12" rx="52" ry="24" fill="#000" opacity=".18" filter="url(#soft)"/>
      <rect x="-48" y="-18" width="96" height="40" rx="20" fill="#4b2833"/>
      <rect x="-42" y="-12" width="84" height="28" rx="14" fill="#673546"/>
      <path d="M-28 -4 q26 -14 52 0" stroke="#a85f63" stroke-width="4" fill="none" opacity=".55"/>
      <ellipse cx="0" cy="-14" rx="20" ry="9" fill="#d9b45e" opacity=".9"/>
    </g>""")
    seeds = "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#a71f36"/>'
        for x, y, r in [(280, 240, 6), (300, 250, 4), (330, 230, 5), (500, 260, 6), (520, 280, 4),
                        (470, 430, 5), (340, 440, 4), (270, 400, 5), (540, 360, 4)]
    )
    body = f"""
  {wood_bg(18, "#3b281b", "#160e0a")}
  {plate(300, 195, 340)}
  <g>{"".join(rolls)}</g>
  {seeds}
  <g fill="#d76a4b">
    <circle cx="380" cy="450" r="17"/><circle cx="420" cy="458" r="14"/><circle cx="350" cy="462" r="12"/>
  </g>
  {herbs(250, 300, "#5f8d48", .85, True)}
  {herbs(560, 380, "#5f8d48", .85)}
  <g fill="#7d9c53" opacity=".8">
    <ellipse cx="300" cy="260" rx="12" ry="6" transform="rotate(-30 300 260)"/>
    <ellipse cx="480" cy="440" rx="12" ry="6" transform="rotate(20 480 440)"/>
  </g>
"""
    return svg_doc(body, "Салат из жареных баклажанов с гранатом")


def make_achichuk() -> str:
    tomatoes = []
    for x, y, rot in [(320, 300, -10), (410, 280, 15), (500, 310, -20), (360, 380, 8), (460, 400, -6)]:
        tomatoes.append(f"""
    <g transform="translate({x} {y}) rotate({rot})">
      <path d="M0 -34 Q44 -26 40 12 Q34 40 0 36 Q-36 34 -42 6 Q-46 -26 0 -34Z" fill="#c53a2d"/>
      <path d="M-18 -22 Q8 -30 24 -10" fill="none" stroke="#e46b54" stroke-width="5" opacity=".65"/>
      <path d="M-4 -34 q6 -8 10 0 q8 -4 8 6" fill="none" stroke="#7ba04f" stroke-width="4"/>
    </g>""")
    body = f"""
  {wood_bg(19, "#3c291c", "#170f0a")}
  {plate(300, 195, 340)}
  <g>{"".join(tomatoes)}</g>
  <g fill="none" stroke="#d9c6a6" stroke-width="6">
    <circle cx="250" cy="360" r="30"/><circle cx="250" cy="360" r="18"/>
    <circle cx="560" cy="300" r="28"/><circle cx="560" cy="300" r="16"/>
    <circle cx="390" cy="450" r="26"/><circle cx="390" cy="450" r="15"/>
  </g>
  <g fill="#5f8c47">
    <ellipse cx="330" cy="430" rx="24" ry="10" transform="rotate(-18 330 430)"/>
    <ellipse cx="470" cy="260" rx="22" ry="9" transform="rotate(24 470 260)"/>
    <ellipse cx="540" cy="410" rx="20" ry="8" transform="rotate(-10 540 410)"/>
  </g>
  <path d="M270 250 q28 -18 56 0" stroke="#f5ddae" stroke-width="4" fill="none" opacity=".5"/>
"""
    return svg_doc(body, "Ачичук из томатов, лука и перца")


def make_tea() -> str:
    body = f"""
  {wood_bg(20, "#432d1d", "#190f09")}
  <ellipse cx="390" cy="400" rx="300" ry="120" fill="#000" opacity=".32" filter="url(#shadow)"/>
  <g transform="translate(360 330)">
    <path d="M-120 -40 q20 -60 120 -60 q100 0 120 60 q18 70 -120 70 q-138 0 -120 -70" fill="#cfa65e"/>
    <path d="M-108 -36 q18 -48 108 -48 q90 0 108 48 q12 52 -108 52 q-120 0 -108 -52" fill="#e1bd76"/>
    <path d="M-84 -84 q84 -36 168 0" fill="none" stroke="#f3d79b" stroke-width="6" opacity=".7"/>
    <path d="M120 -22 q74 -4 64 42 q-8 34 -70 18" fill="none" stroke="#cfa65e" stroke-width="18"/>
    <path d="M-120 -18 q-58 0 -54 34 q4 28 54 24" fill="none" stroke="#cfa65e" stroke-width="16"/>
    <path d="M-34 -116 q34 -26 68 0" fill="none" stroke="#cfa65e" stroke-width="10"/>
    <circle cx="0" cy="-130" r="16" fill="#b23a2c"/>
    <path d="M-100 20 q100 42 200 0" fill="none" stroke="#7a4f23" stroke-width="6" opacity=".4"/>
  </g>
  <g transform="translate(610 380)">
    <ellipse cx="0" cy="40" rx="64" ry="18" fill="#000" opacity=".25" filter="url(#soft)"/>
    <path d="M-52 0 q0 50 52 50 q52 0 52 -50 q-52 14 -104 0" fill="#efe3cf"/>
    <ellipse cx="0" cy="0" rx="52" ry="17" fill="#f8efde"/>
    <ellipse cx="0" cy="2" rx="40" ry="11" fill="#a95a24"/>
    <path d="M-34 4 q34 14 68 0" stroke="#e3b36b" stroke-width="3" fill="none"/>
  </g>
  <g transform="translate(150 400) scale(.8)">
    <ellipse cx="0" cy="34" rx="54" ry="14" fill="#000" opacity=".22" filter="url(#soft)"/>
    <path d="M-44 0 q0 44 44 44 q44 0 44 -44 q-44 12 -88 0" fill="#efe3cf"/>
    <ellipse cx="0" cy="0" rx="44" ry="14" fill="#f8efde"/>
    <ellipse cx="0" cy="2" rx="34" ry="9" fill="#a95a24"/>
  </g>
  <g>
    <circle cx="600" cy="260" r="22" fill="#d9822b"/><circle cx="630" cy="276" r="16" fill="#c56a1f"/>
    <circle cx="575" cy="284" r="14" fill="#e0953e"/><circle cx="615" cy="300" r="12" fill="#b85b1a"/>
    <path d="M600 240 q4 -18 18 -24" stroke="#6f8b43" stroke-width="5" fill="none"/>
  </g>
  {steam(360, 210)}
  {steam(610, 300)}
"""
    return svg_doc(body, "Восточный чай в чайнике и пиалах")


def make_kompot() -> str:
    body = f"""
  {wood_bg(21, "#422c1c", "#180f09")}
  <ellipse cx="400" cy="440" rx="250" ry="76" fill="#000" opacity=".3" filter="url(#shadow)"/>
  <g transform="translate(400 330)">
    <path d="M-86 -110 L-64 150 Q0 184 64 150 L86 -110 Z" fill="#d9b070" opacity=".35"/>
    <path d="M-76 -104 L-56 142 Q0 174 56 142 L76 -104 Z" fill="#e08a2f" opacity=".65"/>
    <path d="M-70 -100 L-52 136 Q0 164 52 136 L70 -100 Z" fill="#e8a044"/>
    <ellipse cx="0" cy="-110" rx="86" ry="22" fill="#f0c37a"/>
    <ellipse cx="0" cy="-110" rx="70" ry="14" fill="#c06f20" opacity=".5"/>
    <g fill="#d8771c">
      <circle cx="-30" cy="-20" r="14"/><circle cx="18" cy="10" r="12"/><circle cx="-8" cy="52" r="13"/>
      <circle cx="32" cy="-48" r="10"/><circle cx="-34" cy="70" r="9"/>
    </g>
    <g fill="#f4d48c" opacity=".8">
      <circle cx="-30" cy="-20" r="4"/><circle cx="18" cy="10" r="3"/><circle cx="-8" cy="52" r="3.5"/>
    </g>
    <path d="M-76 -60 q20 10 40 0" stroke="#fff" stroke-width="5" fill="none" opacity=".25"/>
    <path d="M34 -150 L-6 70" stroke="#f4e6cf" stroke-width="8" stroke-linecap="round" opacity=".8"/>
  </g>
  <g transform="translate(600 380)">
    <circle cx="0" cy="0" r="36" fill="#e08a2f"/>
    <circle cx="0" cy="0" r="27" fill="#f4bf6a"/>
    <g stroke="#e08a2f" stroke-width="3">
      <path d="M0 -27 V27"/><path d="M-27 0 H27"/><path d="M-19 -19 L19 19"/><path d="M19 -19 L-19 19"/>
    </g>
  </g>
  <g fill="#6f8d45">
    <ellipse cx="300" cy="220" rx="26" ry="11" transform="rotate(-26 300 220)"/>
    <ellipse cx="325" cy="206" rx="22" ry="9" transform="rotate(18 325 206)"/>
  </g>
  <circle cx="260" cy="400" r="14" fill="#d8771c"/><circle cx="280" cy="420" r="10" fill="#e8a044"/>
"""
    return svg_doc(body, "Облепиховый морс с апельсином")


def main() -> None:
    files = {
        "dish-plov.svg": make_plov,
        "dish-lagman.svg": make_lagman,
        "dish-shurpa.svg": make_shurpa,
        "dish-manti.svg": make_manti,
        "dish-samsa.svg": make_samsa,
        "dish-shashlik.svg": make_shashlik,
        "dish-kebab.svg": make_kebab,
        "dish-eggplant.svg": make_eggplant,
        "dish-achichuk.svg": make_achichuk,
        "dish-tea.svg": make_tea,
        "dish-kompot.svg": make_kompot,
    }
    for filename, builder in files.items():
        (OUT / filename).write_text(builder(), encoding="utf-8")
        print("written", filename)


if __name__ == "__main__":
    main()

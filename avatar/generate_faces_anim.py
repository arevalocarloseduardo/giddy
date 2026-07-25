#!/usr/bin/env python3
"""
Genera la colección ANIMADA "robot-anim" para xiaozhi-esp32 (Giddy de Charli).
Estilo v3: sin disco ni placa — solo los rasgos (ojos, cejas, boca) en neón azul
sobre negro, a pantalla completa 240x240, un GIF animado en loop por emoción.

Cada emoción es una función que produce keyframes (params, duración_ms), así los
GIFs usan pocos frames con duraciones variables y quedan livianos.

Uso: python3 generate_faces_anim.py [--size 240] [--outdir robot-anim_240]
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFilter

# Coordenadas definidas en espacio 240; se renderiza a K veces y se reduce
BASE = 240
K = 2
S = BASE * K

BLUE = (70, 175, 255)
BRIGHT = (150, 220, 255)
DIM = (18, 60, 130)

# Geometría base (espacio 240)
EYE_L = (75, 102)
EYE_R = (165, 102)
EYE_R_BASE = 40          # radio del ojo redondo
BROW_DY = -58            # offset vertical de la ceja
MOUTH_C = (120, 190)


def pt(p):
    return (p[0] * K, p[1] * K)


def ease(t):
    """easing suave 0..1"""
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


class Renderer:
    def __init__(self):
        self.lines = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.lines)

    # ---------- primitivas (espacio 240, se escala x K) ----------
    def line(self, pts, w=8, color=BLUE):
        self.d.line([pt(p) for p in pts], fill=color, width=w * K, joint="curve")

    def arc(self, bbox240, start, end, w=8, color=BLUE):
        x0, y0, x1, y1 = [v * K for v in bbox240]
        self.d.arc((x0, y0, x1, y1), start, end, fill=color, width=w * K)

    def ellipse_o(self, bbox240, w=8, color=BLUE):
        x0, y0, x1, y1 = [v * K for v in bbox240]
        self.d.ellipse((x0, y0, x1, y1), outline=color, width=w * K)

    def ellipse_f(self, bbox240, color):
        x0, y0, x1, y1 = [v * K for v in bbox240]
        self.d.ellipse((x0, y0, x1, y1), fill=color)

    def poly(self, pts, color=BRIGHT):
        self.d.polygon([pt(p) for p in pts], fill=color)

    def rrect(self, bbox240, radius, w=8, color=BRIGHT, fill=None):
        x0, y0, x1, y1 = [v * K for v in bbox240]
        self.d.rounded_rectangle((x0, y0, x1, y1), radius=radius * K,
                                 fill=fill, outline=color, width=w * K)

    # ---------- ojo ----------
    def eye(self, c, spec):
        """spec: dict(type, open, scale, pupil=(dx,dy), r)"""
        typ = spec.get("type", "round")
        x, y = c
        x += spec.get("dx", 0)
        y += spec.get("dy", 0)
        r = spec.get("r", EYE_R_BASE) * spec.get("scale", 1.0)
        opening = max(0.0, min(1.0, spec.get("open", 1.0)))

        if typ == "round":
            ry = r * opening
            if opening < 0.12:
                self.line([(x - r, y), (x + r, y)], w=9, color=BRIGHT)
                return
            self.ellipse_o((x - r, y - ry, x + r, y + ry), w=8, color=BRIGHT)
            pdx, pdy = spec.get("pupil", (0, 0))
            pr = r * 0.55
            pry = min(pr, ry * 0.8)
            pupil = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pupil)
            px, py = (x + pdx) * K, (y + pdy) * K
            pd.ellipse((px - pr * K, py - pry * K, px + pr * K, py + pry * K),
                       fill=BLUE + (210,))
            self.lines.alpha_composite(pupil.filter(ImageFilter.GaussianBlur(5 * K)))
        elif typ == "arc":  # ∩ ojo cerrado contento
            self.arc((x - r, y - r * 0.55, x + r, y + r * 1.1), 195, 345, w=9, color=BRIGHT)
        elif typ == "line":
            self.line([(x - r, y), (x + r, y)], w=9, color=BRIGHT)
        elif typ == "heart":
            s = r * 1.05  # r ya viene escalado; sin doble scale para que no se toquen
            ptsh = []
            for i in range(61):
                t = i / 60.0 * 2 * math.pi
                hx = 16 * math.sin(t) ** 3
                hy = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
                ptsh.append((x + hx * s / 16.0, y - hy * s / 16.0 + 2))
            self.poly(ptsh, color=BRIGHT)

    def brow(self, c, spec):
        """spec: dict(show, tilt [-1..1: triste..enojado], lift)"""
        if not spec.get("show", True):
            return
        x, y = c
        inner = 1 if x < MOUTH_C[0] else -1
        tilt = spec.get("tilt", 0.0)
        lift = spec.get("lift", 0.0)
        half = 30
        y0 = y + BROW_DY - lift
        p1 = (x - half, y0 + (-tilt * 11 if inner == 1 else tilt * 11))
        p2 = (x + half, y0 + (tilt * 11 if inner == 1 else -tilt * 11))
        mid = ((p1[0] + p2[0]) / 2, y0 - 9)
        self.line([p1, mid, p2], w=8, color=BLUE)

    def mouth(self, spec):
        typ = spec.get("type", "smile")
        cx, cy = MOUTH_C
        cx += spec.get("dx", 0)
        cy += spec.get("dy", 0)
        w = spec.get("w", 1.0)
        if typ == "smile":
            wd, dp = 48 * w, 34 * w
            self.arc((cx - wd, cy - dp, cx + wd, cy + dp), 25, 155, w=9, color=BRIGHT)
        elif typ == "frown":
            wd, dp = 42 * w, 28 * w
            self.arc((cx - wd, cy - dp + 14, cx + wd, cy + dp + 14), 205, 335, w=9, color=BRIGHT)
        elif typ == "flat":
            self.line([(cx - 30 * w, cy), (cx + 30 * w, cy)], w=9, color=BRIGHT)
        elif typ == "o":
            r = 16 * w
            self.ellipse_o((cx - r, cy - r, cx + r, cy + r), w=8, color=BRIGHT)
        elif typ == "open":  # risa: semicirculo relleno
            openness = spec.get("open", 1.0)
            wd = 42
            hh = 6 + 22 * openness
            x0, y0, x1, y1 = (cx - wd) * K, (cy - 4) * K, (cx + wd) * K, (cy + hh) * K
            self.d.chord((x0, y0, x1, y1), 0, 180, fill=DIM + (255,),
                         outline=BRIGHT, width=7 * K)
        elif typ == "smirk":
            self.arc((cx - 50, cy - 38, cx + 30, cy + 14), 30, 115, w=9, color=BRIGHT)
        elif typ == "wave":
            phase = spec.get("phase", 0.0)
            ptsw = []
            for i in range(25):
                t = i / 24.0
                ptsw.append((cx - 40 + 80 * t,
                             cy + math.sin((t * 2.5 + phase) * math.pi * 2 / 2.5 * 1.25) * 8))
            self.line(ptsw, w=8, color=BRIGHT)
        elif typ == "kiss":
            for ang in range(0, 360, 60):
                a = math.radians(ang + spec.get("rot", 0))
                self.line([(cx, cy), (cx + 11 * math.cos(a), cy + 11 * math.sin(a))],
                          w=8, color=BRIGHT)

    # ---------- extras ----------
    def extra(self, name, phase=0.0, **kw):
        if name == "tears":
            for (ex, _), off in ((EYE_L, 0.0), (EYE_R, 0.45)):
                p = (phase + off) % 1.0
                y = 140 + p * 70
                alpha = int(255 * (1.0 - p * 0.8))
                s = 7
                self.poly([(ex, y - 12), (ex - s, y + 4), (ex, y + 12), (ex + s, y + 4)],
                          color=BRIGHT[:3] + (alpha,) if False else BRIGHT)
        elif name == "zzz":
            for i, sz in enumerate((13, 10, 7)):
                p = (phase + i * 0.28) % 1.0
                x = 186 + i * 17 + p * 6
                y = 62 - i * 20 - p * 16
                self.line([(x - sz, y - sz), (x + sz, y - sz), (x - sz, y + sz), (x + sz, y + sz)],
                          w=6, color=BRIGHT)
        elif name == "blush":
            for (ex, _), sgn in ((EYE_L, -1), (EYE_R, 1)):
                for i in range(3):
                    x = ex + sgn * (6 + i * 11) - 7
                    y = 142
                    self.line([(x, y + 10), (x + 12, y - 5)], w=5, color=BLUE)
        elif name == "dots":
            n = kw.get("n", 3)
            for i in range(n):
                r = 4 + i * 2
                x, y = 186 + i * 18, 70 - i * 18
                self.ellipse_f((x - r, y - r, x + r, y + r), BRIGHT + (255,))
        elif name == "glasses":
            y = EYE_L[1]
            for (ex, _) in (EYE_L, EYE_R):
                self.rrect((ex - 44, y - 30, ex + 44, y + 28), radius=18,
                           w=7, color=BRIGHT, fill=(2, 5, 12, 255))
            self.line([(EYE_L[0] + 44, y - 4), (EYE_R[0] - 44, y - 4)], w=7, color=BRIGHT)
            self.line([(EYE_L[0] - 44, y - 8), (6, y - 16)], w=7, color=BRIGHT)
            self.line([(EYE_R[0] + 44, y - 8), (234, y - 16)], w=7, color=BRIGHT)
            gp = kw.get("glint")
            if gp is not None:
                for (ex, _) in (EYE_L, EYE_R):
                    gx = ex - 36 + gp * 72
                    self.line([(gx - 7, y + 16), (gx + 7, y - 18)], w=5, color=(220, 245, 255))
        elif name == "tongue":
            dx = kw.get("dx", 0)
            wig = kw.get("wig", 0.0)
            cx = MOUTH_C[0] + dx + wig * 6
            cy = MOUTH_C[1] + 16
            self.rrect((cx - 13, cy - 4, cx + 13, cy + 26 + wig * 4), radius=12,
                       w=6, color=BRIGHT, fill=DIM + (255,))
        elif name == "heart_float":
            p = phase % 1.0
            x, y = 190, 70 - p * 30
            s = 10 * (1.0 - p * 0.5)
            ptsh = []
            for i in range(41):
                t = i / 40.0 * 2 * math.pi
                hx = 16 * math.sin(t) ** 3
                hy = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
                ptsh.append((x + hx * s / 16.0, y - hy * s / 16.0))
            self.poly(ptsh, color=BRIGHT)


def render_frame(params):
    """params: dict con eye_l, eye_r, brow_l, brow_r, mouth, extras=[(name, phase, kw)]"""
    r = Renderer()
    for name, phase, kw in params.get("extras_back", []):
        r.extra(name, phase, **kw)
    if params.get("brow_l"):
        r.brow(EYE_L, params["brow_l"])
    if params.get("brow_r"):
        r.brow(EYE_R, params["brow_r"])
    if params.get("eye_l"):
        r.eye(EYE_L, params["eye_l"])
    if params.get("eye_r"):
        r.eye(EYE_R, params["eye_r"])
    if params.get("mouth"):
        r.mouth(params["mouth"])
    for name, phase, kw in params.get("extras", []):
        r.extra(name, phase, **kw)

    # composicion con glow sobre negro solido
    img = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    glow_far = r.lines.filter(ImageFilter.GaussianBlur(9 * K))
    glow_near = r.lines.filter(ImageFilter.GaussianBlur(2.2 * K))
    img.alpha_composite(glow_far)
    img.alpha_composite(glow_far)
    img.alpha_composite(glow_near)
    img.alpha_composite(r.lines)
    return img


# ============================ EMOCIONES ============================
# Cada funcion devuelve una lista [(params, duracion_ms), ...] que forma el loop.

def E(eye=None, **kw):
    base = {"type": "round", "open": 1.0, "scale": 1.0, "pupil": (0, 0)}
    base.update(eye or {})
    base.update(kw)
    return base


def B(**kw):
    base = {"show": True, "tilt": 0.0, "lift": 0.0}
    base.update(kw)
    return base


def M(typ="smile", **kw):
    base = {"type": typ}
    base.update(kw)
    return base


def blink_seq(mk_open, hold_ms):
    """Secuencia: abierto (hold) + parpadeo rapido."""
    seq = [(mk_open(1.0), hold_ms)]
    for o in (0.5, 0.08, 0.5):
        seq.append((mk_open(o), 40))
    return seq


def anim_neutral():
    def mk(open_, pupil=(0, 0)):
        return dict(eye_l=E(open=open_, pupil=pupil), eye_r=E(open=open_, pupil=pupil),
                    brow_l=B(), brow_r=B(), mouth=M("smile", w=0.95))
    seq = blink_seq(lambda o: mk(o), 1900)
    seq += [(mk(1.0, pupil=(-7, 2)), 900)]
    seq += blink_seq(lambda o: mk(o, pupil=(7, 2)), 900)
    seq += [(mk(1.0, pupil=(0, -4)), 700)]
    return seq


def anim_happy():
    seq = []
    for i in range(8):
        t = i / 8.0
        b = math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(type="arc"), eye_r=E(type="arc"),
                         mouth=M("smile", w=1.1 + 0.12 * b, dy=-2 * b)), 90))
    return seq


def anim_laughing():
    seq = []
    for i in range(10):
        t = i / 10.0
        o = 0.5 + 0.5 * math.sin(t * 2 * math.pi * 2)
        dy = 2 * math.sin(t * 2 * math.pi * 2)
        seq.append((dict(eye_l=E(type="arc", dy=dy), eye_r=E(type="arc", dy=dy),
                         mouth=M("open", open=o)), 70))
    return seq


def anim_sad():
    seq = []
    for i in range(10):
        t = i / 10.0
        s = math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(open=0.75 + 0.06 * s, pupil=(0, 6)),
                         eye_r=E(open=0.75 + 0.06 * s, pupil=(0, 6)),
                         brow_l=B(tilt=-0.8), brow_r=B(tilt=-0.8),
                         mouth=M("frown", dy=2 * s)), 130))
    return seq


def anim_crying():
    seq = []
    for i in range(10):
        t = i / 10.0
        seq.append((dict(eye_l=E(open=0.55, pupil=(0, 6)), eye_r=E(open=0.55, pupil=(0, 6)),
                         brow_l=B(tilt=-0.9), brow_r=B(tilt=-0.9),
                         mouth=M("frown"),
                         extras=[("tears", t, {})]), 90))
    return seq


def anim_angry():
    seq = []
    for i in range(8):
        t = i / 8.0
        sh = 2 * math.sin(t * 2 * math.pi * 2)
        seq.append((dict(eye_l=E(open=0.6, dx=sh), eye_r=E(open=0.6, dx=sh),
                         brow_l=B(tilt=1.0, lift=-4), brow_r=B(tilt=1.0, lift=-4),
                         mouth=M("frown", w=0.8, dx=sh)), 80))
    return seq


def anim_sleepy():
    seq = []
    for i in range(12):
        t = i / 12.0
        o = 0.32 + 0.18 * math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(open=o), eye_r=E(open=o),
                         mouth=M("o", w=0.7),
                         extras=[("zzz", t, {})]), 140))
    return seq


def anim_surprised():
    seq = []
    for i in range(8):
        t = i / 8.0
        s = 1.06 + 0.09 * math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(scale=s), eye_r=E(scale=s),
                         brow_l=B(lift=10), brow_r=B(lift=10),
                         mouth=M("o")), 90))
    return seq


def anim_shocked():
    seq = []
    for i in range(8):
        t = i / 8.0
        s = 1.12 + 0.12 * math.sin(t * 2 * math.pi * 2)
        dx = 2 * math.sin(t * 2 * math.pi * 3)
        seq.append((dict(eye_l=E(scale=s, dx=dx), eye_r=E(scale=s, dx=dx),
                         brow_l=B(lift=14), brow_r=B(lift=14),
                         mouth=M("o", w=1.5)), 70))
    return seq


def anim_thinking():
    seq = []
    for n in (1, 2, 3, 3, 3, 2):
        seq.append((dict(eye_l=E(open=0.85, pupil=(8, -8)), eye_r=E(open=0.7, pupil=(8, -8)),
                         brow_l=B(), brow_r=B(lift=10),
                         mouth=M("flat", w=0.8, dx=6),
                         extras=[("dots", 0, {"n": n})]), 220))
    return seq


def anim_confused():
    seq = []
    for i in range(10):
        t = i / 10.0
        s = math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(scale=1.05, pupil=(-4 * s, 0)), eye_r=E(scale=0.85, pupil=(-4 * s, 0)),
                         brow_l=B(tilt=-0.4, lift=-3 * s), brow_r=B(tilt=0.4, lift=3 * s + 8),
                         mouth=M("wave", phase=t)), 110))
    return seq


def anim_winking():
    def open_frame(ms):
        return (dict(eye_l=E(), eye_r=E(), brow_l=B(), brow_r=B(),
                     mouth=M("smile", w=0.95)), ms)
    seq = [open_frame(1100)]
    for o in (0.5, 0.06, 0.06, 0.5):
        seq.append((dict(eye_l=E(), eye_r=E(open=o), brow_l=B(), brow_r=B(lift=4),
                         mouth=M("smirk")), 90))
    seq.append(open_frame(500))
    return seq


def anim_loving():
    seq = []
    for i in range(10):
        t = i / 10.0
        beat = 1.0 + 0.14 * max(0.0, math.sin(t * 2 * math.pi * 2)) * (1 if t < 0.5 else 0.4)
        seq.append((dict(eye_l=E(type="heart", scale=beat), eye_r=E(type="heart", scale=beat),
                         mouth=M("smile", w=1.05)), 90))
    return seq


def anim_cool():
    seq = [(dict(mouth=M("smirk"), extras=[("glasses", 0, {})]), 1400)]
    for i in range(7):
        g = i / 6.0
        seq.append((dict(mouth=M("smirk"), extras=[("glasses", 0, {"glint": g})]), 60))
    seq.append((dict(mouth=M("smirk"), extras=[("glasses", 0, {})]), 700))
    return seq


def anim_confident():
    seq = []
    for i in range(8):
        t = i / 8.0
        s = math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(open=0.72), eye_r=E(open=0.72),
                         brow_l=B(tilt=0.5), brow_r=B(tilt=0.5, lift=4 + 3 * s),
                         mouth=M("smirk")), 120))
    return seq


def anim_embarrassed():
    seq = []
    for i in range(10):
        t = i / 10.0
        look = 8 * math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(open=0.7, pupil=(look, 3)), eye_r=E(open=0.7, pupil=(look, 3)),
                         brow_l=B(tilt=-0.5), brow_r=B(tilt=-0.5),
                         mouth=M("smile", w=0.6),
                         extras=[("blush", 0, {})]), 120))
    return seq


def anim_funny():
    seq = []
    for i in range(8):
        t = i / 8.0
        wig = math.sin(t * 2 * math.pi * 2)
        seq.append((dict(eye_l=E(scale=1.15), eye_r=E(type="arc"),
                         mouth=M("smile", w=0.95),
                         extras=[("tongue", 0, {"dx": 16, "wig": wig})]), 90))
    return seq


def anim_silly():
    seq = []
    for i in range(10):
        t = i / 10.0
        cross = 6 * math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(pupil=(cross, 2)), eye_r=E(pupil=(-cross, 2), scale=0.85),
                         brow_l=B(tilt=-0.6), brow_r=B(tilt=0.8),
                         mouth=M("smile", w=0.9),
                         extras=[("tongue", 0, {"dx": -14, "wig": math.cos(t * 2 * math.pi)})]), 100))
    return seq


def anim_kissy():
    seq = []
    for i in range(12):
        t = i / 12.0
        seq.append((dict(eye_l=E(type="arc"), eye_r=E(type="arc"),
                         mouth=M("kiss", rot=t * 30),
                         extras=[("heart_float", t, {})]), 90))
    return seq


def anim_relaxed():
    seq = []
    for i in range(10):
        t = i / 10.0
        breathe = math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(type="arc", dy=breathe), eye_r=E(type="arc", dy=breathe),
                         mouth=M("smile", w=0.85, dy=breathe)), 150))
    return seq


def anim_delicious():
    seq = []
    for i in range(10):
        t = i / 10.0
        lick = math.sin(t * 2 * math.pi)
        seq.append((dict(eye_l=E(type="arc"), eye_r=E(type="arc"),
                         mouth=M("smile", w=1.0),
                         extras=[("tongue", 0, {"dx": int(10 * lick), "wig": lick})]), 100))
    return seq


EMOTIONS = {
    "neutral": anim_neutral,
    "robot_2": anim_neutral,  # cara de standby del firmware
    "happy": anim_happy,
    "laughing": anim_laughing,
    "sad": anim_sad,
    "crying": anim_crying,
    "angry": anim_angry,
    "sleepy": anim_sleepy,
    "surprised": anim_surprised,
    "shocked": anim_shocked,
    "thinking": anim_thinking,
    "confused": anim_confused,
    "winking": anim_winking,
    "loving": anim_loving,
    "cool": anim_cool,
    "confident": anim_confident,
    "embarrassed": anim_embarrassed,
    "funny": anim_funny,
    "silly": anim_silly,
    "kissy": anim_kissy,
    "relaxed": anim_relaxed,
    "delicious": anim_delicious,
}


def save_gif(name, seq, size, outdir):
    frames = []
    durations = []
    for params, ms in seq:
        img = render_frame(params).resize((size, size), Image.LANCZOS).convert("RGB")
        frames.append(img)
        durations.append(ms)
    # paleta consistente entre frames (evita parpadeo de cuantizacion)
    ref = frames[0].quantize(colors=64, method=Image.MEDIANCUT)
    qframes = [f.quantize(palette=ref, dither=Image.NONE) for f in frames]
    path = os.path.join(outdir, f"{name}.gif")
    qframes[0].save(path, save_all=True, append_images=qframes[1:],
                    duration=durations, loop=0, optimize=True, disposal=1)
    kb = os.path.getsize(path) / 1024
    print(f"  {name}.gif  {len(qframes)} frames  {kb:.0f} KB")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=240)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    outdir = args.outdir or os.path.join(here, f"robot-anim_{args.size}")
    os.makedirs(outdir, exist_ok=True)

    total = 0
    for name, fn in EMOTIONS.items():
        path = save_gif(name, fn(), args.size, outdir)
        total += os.path.getsize(path)
    print(f"TOTAL: {total/1024/1024:.2f} MB")


if __name__ == "__main__":
    main()

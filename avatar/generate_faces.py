#!/usr/bin/env python3
"""
Genera la colección de emojis "robot-face" para xiaozhi-esp32.
Estilo: cara robot neón azul sobre disco negro brillante (avatar de Charli).
Renderiza a 512px con capas de glow y baja a 64x64 (supersampling).
Uso: python3 generate_faces.py [--size 64] [--outdir robot-face_64]
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFilter

S = 512  # tamaño de render interno

# Paleta neón (RGB)
BLUE = (70, 175, 255)
BRIGHT = (150, 220, 255)
DIM = (18, 60, 130)
HEAD_FILL = (6, 10, 20, 255)
PLATE_FILL = (2, 5, 12, 255)

# Geometría base
CX, CY = 256, 256
EYE_L = (183, 258)
EYE_R = (329, 258)
EYE_R_DEFAULT = 40
MOUTH_C = (256, 342)


def new_layer():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


class Face:
    """Acumula trazos en una capa de líneas y extras, luego compone con glow."""

    def __init__(self):
        self.lines = new_layer()  # trazos neón
        self.d = ImageDraw.Draw(self.lines)

    # ---------- primitivas ----------
    def arc(self, bbox, start, end, w=11, color=BLUE):
        self.d.arc(bbox, start, end, fill=color, width=w)

    def line(self, pts, w=11, color=BLUE):
        self.d.line(pts, fill=color, width=w, joint="curve")

    def ellipse_outline(self, bbox, w=11, color=BLUE):
        self.d.ellipse(bbox, outline=color, width=w)

    def ellipse_fill(self, bbox, color):
        self.d.ellipse(bbox, fill=color)

    def polygon(self, pts, color=BLUE):
        self.d.polygon(pts, fill=color)

    # ---------- ojos ----------
    def eye_circle(self, c, r=EYE_R_DEFAULT, glow_pupil=True):
        x, y = c
        self.ellipse_outline((x - r, y - r, x + r, y + r), w=10, color=BRIGHT)
        if glow_pupil:
            pr = int(r * 0.62)
            pupil = new_layer()
            pd = ImageDraw.Draw(pupil)
            pd.ellipse((x - pr, y - pr, x + pr, y + pr), fill=BLUE + (200,))
            pupil = pupil.filter(ImageFilter.GaussianBlur(7))
            self.lines.alpha_composite(pupil)

    def eye_happy_arc(self, c, r=38):
        # arco ∩ (ojo cerrado contento)
        x, y = c
        self.arc((x - r, y - r + 12, x + r, y + r + 26), 195, 345, w=12, color=BRIGHT)

    def eye_line(self, c, half=34):
        x, y = c
        self.line([(x - half, y), (x + half, y)], w=12, color=BRIGHT)

    def eye_heart(self, c, size=44):
        x, y = c
        s = size
        pts = []
        for t in [i / 60.0 * 2 * math.pi for i in range(61)]:
            px = 16 * math.sin(t) ** 3
            py = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((x + px * s / 34.0, y - py * s / 34.0))
        self.polygon(pts, color=BRIGHT)

    # ---------- cejas ----------
    def brow(self, c, tilt=0.0, dy=-66, half=34, w=10):
        """Ceja arco; tilt>0 = extremo interno hacia abajo (enojo), <0 = pena."""
        x, y = c
        inner = 1 if x < CX else -1  # dirección hacia el centro de la cara
        y0 = y + dy
        p1 = (x - half, y0 + (-tilt * 14 if inner == 1 else tilt * 14))
        p2 = (x + half, y0 + (tilt * 14 if inner == 1 else -tilt * 14))
        mid = ((p1[0] + p2[0]) / 2, y0 - 12)
        self.line([p1, mid, p2], w=w, color=BLUE)

    # ---------- bocas ----------
    def mouth_smile(self, wd=52, depth=34, w=11, cx=None, cy=None):
        cx = cx or MOUTH_C[0]
        cy = cy or MOUTH_C[1]
        self.arc((cx - wd, cy - depth, cx + wd, cy + depth), 25, 155, w=w, color=BRIGHT)

    def mouth_frown(self, wd=46, depth=30):
        cx, cy = MOUTH_C[0], MOUTH_C[1] + 16
        self.arc((cx - wd, cy - depth, cx + wd, cy + depth), 205, 335, w=11, color=BRIGHT)

    def mouth_flat(self, half=34, dy=0):
        cx, cy = MOUTH_C[0], MOUTH_C[1] + dy
        self.line([(cx - half, cy), (cx + half, cy)], w=11, color=BRIGHT)

    def mouth_o(self, r=20):
        cx, cy = MOUTH_C
        self.ellipse_outline((cx - r, cy - r, cx + r, cy + r), w=10, color=BRIGHT)

    def mouth_open_laugh(self):
        cx, cy = MOUTH_C[0], MOUTH_C[1] + 2
        bbox = (cx - 44, cy - 26, cx + 44, cy + 30)
        self.d.chord(bbox, 0, 180, fill=DIM + (255,), outline=BRIGHT, width=9)

    def mouth_smirk(self):
        cx, cy = MOUTH_C
        self.arc((cx - 54, cy - 40, cx + 34, cy + 18), 30, 120, w=11, color=BRIGHT)

    def mouth_wave(self):
        cx, cy = MOUTH_C
        pts = []
        for i in range(25):
            t = i / 24.0
            pts.append((cx - 42 + 84 * t, cy + math.sin(t * math.pi * 2.5) * 10))
        self.line(pts, w=10, color=BRIGHT)

    def mouth_kiss(self):
        cx, cy = MOUTH_C
        for ang in range(0, 360, 60):
            a = math.radians(ang)
            self.line(
                [(cx, cy), (cx + 14 * math.cos(a), cy + 14 * math.sin(a))],
                w=9, color=BRIGHT,
            )

    # ---------- extras ----------
    def tongue(self, dx=18):
        cx, cy = MOUTH_C[0] + dx, MOUTH_C[1] + 18
        self.d.rounded_rectangle((cx - 16, cy - 6, cx + 16, cy + 34), radius=15,
                                 fill=DIM + (255,), outline=BRIGHT, width=8)

    def tears(self):
        for (ex, ey) in (EYE_L, EYE_R):
            x = ex
            y = ey + 52
            self.d.polygon(
                [(x, y), (x - 10, y + 22), (x, y + 34), (x + 10, y + 22)],
                fill=BRIGHT,
            )

    def blush(self):
        for (ex, ey), sgn in ((EYE_L, -1), (EYE_R, 1)):
            for i in range(3):
                x = ex + sgn * (18 + i * 14) - 14
                y = ey + 44
                self.line([(x, y + 14), (x + 18, y - 6)], w=7, color=BLUE)

    def zzz(self):
        base_x, base_y = 356, 108
        for i, s in enumerate((30, 22, 15)):
            x = base_x + i * 34
            y = base_y - i * 26
            self.line([(x - s, y - s), (x + s, y - s), (x - s, y + s), (x + s, y + s)],
                      w=8, color=BRIGHT)

    def sunglasses(self):
        y = EYE_L[1]
        for (ex, _) in (EYE_L, EYE_R):
            self.d.rounded_rectangle((ex - 46, y - 34, ex + 46, y + 28), radius=24,
                                     fill=PLATE_FILL, outline=BRIGHT, width=9)
        self.line([(EYE_L[0] + 46, y - 6), (EYE_R[0] - 46, y - 6)], w=9, color=BRIGHT)
        self.line([(EYE_L[0] - 46, y - 10), (104, y - 22)], w=9, color=BRIGHT)
        self.line([(EYE_R[0] + 46, y - 10), (408, y - 22)], w=9, color=BRIGHT)

    def heart_float(self, c=(376, 150), size=26):
        self.eye_heart(c, size=size)

    def dots_think(self):
        for i, r in enumerate((7, 9, 11)):
            x = 384 + i * 26
            y = 150 - i * 24
            self.ellipse_fill((x - r, y - r, x + r, y + r), BRIGHT + (255,))


def compose(face: Face) -> Image.Image:
    """Arma la imagen final: disco negro + placa + líneas con glow."""
    # fondo negro sólido: sin esquinas transparentes, nunca se ve el tema detrás
    img = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)

    # disco de la cabeza (negro brillante)
    d.ellipse((30, 30, 482, 482), fill=HEAD_FILL)

    # placa de la cara (pantalla redondeada oscura)
    d.rounded_rectangle((78, 108, 434, 414), radius=95, fill=PLATE_FILL)

    # anillo exterior + contorno de placa (capa de trazos estructurales)
    ring = new_layer()
    rd = ImageDraw.Draw(ring)
    rd.ellipse((30, 30, 482, 482), outline=BLUE, width=7)
    rd.rounded_rectangle((78, 108, 434, 414), radius=95, outline=BLUE, width=8)

    art = new_layer()
    art.alpha_composite(ring)
    art.alpha_composite(face.lines)

    # glow: dos pasadas de blur + trazo nítido
    glow_far = art.filter(ImageFilter.GaussianBlur(18))
    glow_near = art.filter(ImageFilter.GaussianBlur(5))
    img.alpha_composite(glow_far)
    img.alpha_composite(glow_far)  # refuerzo del halo
    img.alpha_composite(glow_near)
    img.alpha_composite(art)
    return img


def build_emotion(name: str) -> Image.Image:
    f = Face()
    if name in ("neutral", "robot_2"):  # robot_2 = cara de standby/idle del firmware
        f.brow(EYE_L); f.brow(EYE_R)
        f.eye_circle(EYE_L); f.eye_circle(EYE_R)
        f.mouth_smile(wd=44, depth=26)
    elif name == "happy":
        f.eye_happy_arc(EYE_L); f.eye_happy_arc(EYE_R)
        f.mouth_smile(wd=56, depth=38)
    elif name == "laughing":
        f.eye_happy_arc(EYE_L); f.eye_happy_arc(EYE_R)
        f.mouth_open_laugh()
    elif name == "funny":
        f.eye_circle(EYE_L, r=44); f.eye_happy_arc(EYE_R)
        f.mouth_smile(wd=50, depth=30); f.tongue(dx=22)
    elif name == "silly":
        f.brow(EYE_L, tilt=-0.6); f.brow(EYE_R, tilt=0.8)
        f.eye_happy_arc(EYE_L, r=42); f.eye_circle(EYE_R, r=30)
        f.mouth_smile(wd=46, depth=28); f.tongue(dx=-20)
    elif name == "loving":
        f.eye_heart(EYE_L); f.eye_heart(EYE_R)
        f.mouth_smile(wd=52, depth=32)
    elif name == "kissy":
        f.eye_happy_arc(EYE_L); f.eye_happy_arc(EYE_R)
        f.mouth_kiss(); f.heart_float()
    elif name == "cool":
        f.sunglasses()
        f.mouth_smirk()
    elif name == "confident":
        f.brow(EYE_L, tilt=0.5); f.brow(EYE_R, tilt=0.5)
        f.eye_circle(EYE_L, r=34); f.eye_circle(EYE_R, r=34)
        f.mouth_smirk()
    elif name == "relaxed":
        f.eye_happy_arc(EYE_L, r=34); f.eye_happy_arc(EYE_R, r=34)
        f.mouth_smile(wd=42, depth=22)
    elif name == "delicious":
        f.eye_happy_arc(EYE_L); f.eye_happy_arc(EYE_R)
        f.mouth_smile(wd=50, depth=30); f.tongue(dx=0)
    elif name == "sad":
        f.brow(EYE_L, tilt=-0.8); f.brow(EYE_R, tilt=-0.8)
        f.eye_circle(EYE_L, r=34); f.eye_circle(EYE_R, r=34)
        f.mouth_frown()
    elif name == "crying":
        f.brow(EYE_L, tilt=-0.9); f.brow(EYE_R, tilt=-0.9)
        f.eye_circle(EYE_L, r=30); f.eye_circle(EYE_R, r=30)
        f.mouth_frown(); f.tears()
    elif name == "angry":
        f.brow(EYE_L, tilt=1.0, dy=-58); f.brow(EYE_R, tilt=1.0, dy=-58)
        f.eye_circle(EYE_L, r=30); f.eye_circle(EYE_R, r=30)
        f.mouth_frown(wd=40, depth=24)
    elif name == "sleepy":
        f.eye_line(EYE_L); f.eye_line(EYE_R)
        f.mouth_o(r=13); f.zzz()
    elif name == "surprised":
        f.brow(EYE_L, dy=-76); f.brow(EYE_R, dy=-76)
        f.eye_circle(EYE_L, r=46); f.eye_circle(EYE_R, r=46)
        f.mouth_o(r=18)
    elif name == "shocked":
        f.brow(EYE_L, dy=-84); f.brow(EYE_R, dy=-84)
        f.eye_circle(EYE_L, r=52); f.eye_circle(EYE_R, r=52)
        f.mouth_o(r=26)
    elif name == "thinking":
        f.brow(EYE_L, dy=-60); f.brow(EYE_R, dy=-80)
        f.eye_circle(EYE_L, r=32); f.eye_circle(EYE_R, r=40)
        f.mouth_flat(half=26, dy=4); f.dots_think()
    elif name == "confused":
        f.brow(EYE_L, dy=-60, tilt=-0.4); f.brow(EYE_R, dy=-82, tilt=0.4)
        f.eye_circle(EYE_L, r=42); f.eye_circle(EYE_R, r=30)
        f.mouth_wave()
    elif name == "embarrassed":
        f.brow(EYE_L, tilt=-0.5); f.brow(EYE_R, tilt=-0.5)
        f.eye_circle(EYE_L, r=30); f.eye_circle(EYE_R, r=30)
        f.mouth_smile(wd=34, depth=18); f.blush()
    elif name == "winking":
        f.brow(EYE_L); f.brow(EYE_R, dy=-72)
        f.eye_happy_arc(EYE_L, r=36); f.eye_circle(EYE_R)
        f.mouth_smile(wd=48, depth=30)
    else:
        raise ValueError(f"emocion desconocida: {name}")
    return compose(f)


EMOTIONS = [
    "angry", "confident", "confused", "cool", "crying", "delicious",
    "embarrassed", "funny", "happy", "kissy", "laughing", "loving",
    "neutral", "relaxed", "robot_2", "sad", "shocked", "silly", "sleepy",
    "surprised", "thinking", "winking",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    outdir = args.outdir or os.path.join(here, f"robot-face_{args.size}")
    os.makedirs(outdir, exist_ok=True)

    for name in EMOTIONS:
        img = build_emotion(name)
        img = img.resize((args.size, args.size), Image.LANCZOS)
        img.save(os.path.join(outdir, f"{name}.png"))
        print(f"  {name}.png")

    # hoja de contactos para previsualizar
    cell = 128
    cols = 7
    rows = (len(EMOTIONS) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (10, 12, 18, 255))
    for i, name in enumerate(EMOTIONS):
        img = build_emotion(name).resize((cell - 8, cell - 8), Image.LANCZOS)
        sheet.alpha_composite(img, ((i % cols) * cell + 4, (i // cols) * cell + 4))
    sheet_path = os.path.join(here, "preview_sheet.png")
    sheet.save(sheet_path)
    print(f"preview: {sheet_path}")


if __name__ == "__main__":
    main()

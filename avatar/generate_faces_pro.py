#!/usr/bin/env python3
"""
Colección "robot-pro" — avatar profesional para Giddy (xiaozhi-esp32).

Diseño v5, estilo robot comercial (EMO/Vector):
- Ojos = formas RELLENAS con gradiente vertical luminoso + brillo especular,
  glow suave. Sin contornos finos ni pupilas de caricatura.
- BOCA por emoción (sonrisa, mueca, "o" de sorpresa, smirk, ondulada,
  boca abierta de risa) con el mismo lenguaje: relleno gradiente + glow.
- Las emociones morfan la FORMA del ojo (medialuna feliz, párpado caído,
  inclinación de enojo, pop de sorpresa) con easing entre keyframes.
- Anti-banding: paleta de 255 colores por GIF + dithering ordenado (Bayer 8x8)
  de baja amplitud, estable entre frames (sin "hormigueo").

Salida: un GIF en loop por emoción, 240x240, paleta fija por GIF.
Uso: python3 generate_faces_pro.py [--size 240] [--outdir robot-pro_240]
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFilter

BASE = 240
K = 2
S = BASE * K

# Gradiente de los ojos (arriba -> abajo) y acentos
C_TOP = (170, 230, 255)
C_BOT = (25, 110, 235)
C_GLOW = (60, 160, 255)
VISOR_FILL = (8, 16, 34, 255)

# Geometría (espacio 240)
EYE_L = (74, 108)
EYE_R = (166, 108)
EYE_W = 66
EYE_H = 88
EYE_RAD = 28
MOUTH_Y = 177


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def vgrad(w, h, top=C_TOP, bot=C_BOT):
    """Tile con gradiente vertical."""
    g = Image.new("RGB", (1, 256))
    for i in range(256):
        f = i / 255.0
        g.putpixel((0, i), tuple(int(top[c] + (bot[c] - top[c]) * f) for c in range(3)))
    return g.resize((w, h))


def rounded_mask(w, h, rad):
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=rad, fill=255)
    return m


def heart_mask(size):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    pts = []
    for i in range(121):
        t = i / 120.0 * 2 * math.pi
        hx = 16 * math.sin(t) ** 3
        hy = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((size / 2 + hx * size / 36.0, size / 2 - hy * size / 36.0 + size * 0.04))
    d.polygon(pts, fill=255)
    return m


def drop_mask(w, h):
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(w // 2, 0), (int(w * 0.08), int(h * 0.62)), (w // 2, h - 1),
               (int(w * 0.92), int(h * 0.62))], fill=255)
    return m.filter(ImageFilter.GaussianBlur(1))


class Frame:
    """Un frame: acumula piezas 'emisivas' y compone con glow al final."""

    def __init__(self):
        self.emissive = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    def paste_piece(self, piece, center240):
        x = int(center240[0] * K - piece.width / 2)
        y = int(center240[1] * K - piece.height / 2)
        self.emissive.alpha_composite(piece, (x, y))

    # ---------- piezas ----------
    def eye(self, center, w=EYE_W, h=EYE_H, rad=EYE_RAD, squash=1.0,
            cut_bottom=0.0, lid=0.0, rot=0.0, dx=0.0, dy=0.0, scale=1.0,
            crescent=False):
        """Ojo relleno con gradiente.
        squash: 0..1 apertura vertical (parpadeo)
        cut_bottom: 0..1 recorte inferior (ojo sonriente)
        lid: 0..1 párpado superior plano (entrecerrado)
        crescent: forma medialuna completa (feliz)
        """
        w_px = int(w * K * scale)
        h_px = max(6, int(h * K * scale * max(0.05, squash)))
        rad_px = min(int(rad * K * scale), w_px // 2, h_px // 2)

        mask = rounded_mask(w_px, h_px, rad_px)
        if crescent or cut_bottom > 0:
            cut = Image.new("L", (w_px, h_px), 0)
            dcut = ImageDraw.Draw(cut)
            ch = h_px * (0.78 if crescent else cut_bottom)
            dcut.ellipse((-w_px * 0.25, h_px - ch * 0.9, w_px * 1.25, h_px + ch * 1.4), fill=255)
            mask = Image.composite(Image.new("L", mask.size, 0), mask, cut)
        if lid > 0:
            dlid = ImageDraw.Draw(mask)
            dlid.rectangle((0, 0, w_px, int(h_px * lid * 0.55)), fill=0)

        piece = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
        piece.paste(vgrad(w_px, h_px), (0, 0), mask)

        # brillo especular arriba-adentro
        hl = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
        dhl = ImageDraw.Draw(hl)
        dhl.ellipse((w_px * 0.16, h_px * 0.06, w_px * 0.62, h_px * 0.30),
                    fill=(255, 255, 255, 95))
        hl = hl.filter(ImageFilter.GaussianBlur(3 * K))
        piece.alpha_composite(Image.composite(hl, Image.new("RGBA", hl.size, (0, 0, 0, 0)),
                                              mask))
        if rot:
            piece = piece.rotate(rot, expand=True, resample=Image.BICUBIC)
        self.paste_piece(piece, (center[0] + dx, center[1] + dy))

    def mouth(self, kind="line", center=(120, MOUTH_Y), w=44, curve=0.0,
              thick=10, open_h=14, r=10, smirk=0.0, amp=3.0, phase=0.0,
              dx=0.0, dy=0.0, tilt=0.0):
        """Boca con el mismo lenguaje visual (relleno gradiente + glow).
        kind: "line"  trazo capsular con curva (curve>0 sonrisa, <0 mueca)
                      y smirk (>0 levanta la comisura derecha)
              "wavy"  línea ondulada (amp/phase)
              "open"  boca abierta: media elipse con borde superior plano
              "ring"  "o" de sorpresa/beso (anillo de radio r)
        """
        if kind == "open":
            wp, hp = int(w * K), max(6, int(open_h * K))
            m = Image.new("L", (wp, hp), 0)
            d = ImageDraw.Draw(m)
            d.ellipse((0, -hp, wp - 1, hp - 1), fill=255)
        elif kind == "ring":
            rp = int(r * K)
            t2 = max(3, int(thick * K * 0.45))
            wp = hp = rp * 2 + 4
            m = Image.new("L", (wp, hp), 0)
            d = ImageDraw.Draw(m)
            d.ellipse((2, 2, wp - 3, hp - 3), fill=255)
            d.ellipse((2 + t2, 2 + t2, wp - 3 - t2, hp - 3 - t2), fill=0)
        else:
            rad = thick * K / 2
            span = (abs(curve) + abs(smirk) + (amp if kind == "wavy" else 0)) * K
            wp = int(w * K + thick * K + 8)
            hp = int(2 * span + thick * K + 8)
            m = Image.new("L", (wp, hp), 0)
            d = ImageDraw.Draw(m)
            cxp, cyp = wp / 2, hp / 2
            steps = 56
            for i in range(steps + 1):
                t = i / steps
                x = (t - 0.5) * w * K
                if kind == "wavy":
                    y = amp * math.sin(2 * math.pi * (1.25 * t + phase)) * K
                else:
                    y = (curve * (1 - 2 * (2 * t - 1) ** 2) - smirk * (2 * t - 1)) * K
                d.ellipse((cxp + x - rad, cyp + y - rad, cxp + x + rad, cyp + y + rad),
                          fill=255)
        piece = Image.new("RGBA", m.size, (0, 0, 0, 0))
        piece.paste(vgrad(m.size[0], m.size[1]), (0, 0), m)
        if tilt:
            piece = piece.rotate(tilt, expand=True, resample=Image.BICUBIC)
        self.paste_piece(piece, (center[0] + dx, center[1] + dy))

    def heart(self, center, size240, beat=1.0):
        px = int(size240 * K * beat)
        m = heart_mask(px)
        piece = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        piece.paste(vgrad(px, px), (0, 0), m)
        self.paste_piece(piece, center)

    def tear(self, center, w240=13, h240=20, alpha=255):
        wp, hp = int(w240 * K), int(h240 * K)
        m = drop_mask(wp, hp).point(lambda v: v * alpha // 255)
        piece = Image.new("RGBA", (wp, hp), (0, 0, 0, 0))
        piece.paste(vgrad(wp, hp, top=(210, 240, 255), bot=(60, 150, 250)), (0, 0), m)
        self.paste_piece(piece, center)

    def visor(self, glint=None):
        """Visor único sobre ambos ojos, con destello opcional (0..1)."""
        w_px, h_px = int(176 * K), int(64 * K)
        rad = int(30 * K)
        piece = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
        d = ImageDraw.Draw(piece)
        d.rounded_rectangle((0, 0, w_px - 1, h_px - 1), radius=rad, fill=VISOR_FILL)
        # borde con gradiente: dibujar anillo con máscara
        ring_mask = Image.new("L", (w_px, h_px), 0)
        dr = ImageDraw.Draw(ring_mask)
        dr.rounded_rectangle((0, 0, w_px - 1, h_px - 1), radius=rad, outline=255,
                             width=int(5 * K))
        ring = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
        ring.paste(vgrad(w_px, h_px), (0, 0), ring_mask)
        piece.alpha_composite(ring)
        if glint is not None:
            gl = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
            dg = ImageDraw.Draw(gl)
            gx = int(glint * (w_px + 80 * K)) - 40 * K
            dg.polygon([(gx, h_px), (gx + 14 * K, h_px), (gx + 34 * K, 0), (gx + 20 * K, 0)],
                       fill=(235, 250, 255, 170))
            dg.polygon([(gx + 44 * K, h_px), (gx + 50 * K, h_px), (gx + 70 * K, 0), (gx + 64 * K, 0)],
                       fill=(235, 250, 255, 90))
            gl = gl.filter(ImageFilter.GaussianBlur(K))
            inner = rounded_mask(w_px, h_px, rad)
            piece.alpha_composite(Image.composite(gl, Image.new("RGBA", gl.size, (0, 0, 0, 0)), inner))
        self.paste_piece(piece, (120, 108))

    def zzz(self, phase):
        d = ImageDraw.Draw(self.emissive)
        for i, sz in enumerate((14, 10, 7)):
            p = (phase + i * 0.28) % 1.0
            x = (182 + i * 19 + p * 5) * K
            y = (64 - i * 21 - p * 14) * K
            szp = sz * K
            d.line([(x - szp, y - szp), (x + szp, y - szp), (x - szp, y + szp), (x + szp, y + szp)],
                   fill=(190, 235, 255), width=6 * K, joint="curve")

    def blush(self, alpha=150):
        for (ex, _), _sgn in ((EYE_L, -1), (EYE_R, 1)):
            wp, hp = int(34 * K), int(14 * K)
            piece = Image.new("RGBA", (wp, hp), (0, 0, 0, 0))
            d = ImageDraw.Draw(piece)
            d.ellipse((0, 0, wp - 1, hp - 1), fill=(120, 190, 255, alpha))
            piece = piece.filter(ImageFilter.GaussianBlur(2 * K))
            self.paste_piece(piece, (ex, 164))

    def dots(self, n):
        d = ImageDraw.Draw(self.emissive)
        for i in range(n):
            r = (4 + i * 2) * K
            x, y = (184 + i * 19) * K, (72 - i * 19) * K
            d.ellipse((x - r, y - r, x + r, y + r), fill=(190, 235, 255))

    def tongue(self, wig=0.0, dy=0.0):
        wp, hp = int(30 * K), int(26 * K)
        m = rounded_mask(wp, hp, int(13 * K))
        piece = Image.new("RGBA", (wp, hp), (0, 0, 0, 0))
        piece.paste(vgrad(wp, hp, top=(120, 200, 255), bot=(30, 110, 230)), (0, 0), m)
        self.paste_piece(piece, (120 + wig * 8, 178 + abs(wig) * 3 + dy))

    # ---------- composición ----------
    def compose(self):
        img = Image.new("RGBA", (S, S), (0, 0, 0, 255))
        # Rim angosto y brillante: da el look emisivo pegado al ojo. Gamma 1.4
        # mantiene el brillo cercano pero crushea el fleco tenue del borde a
        # negro (si no, ese fleco también se dithera y granula "por fuera").
        rr, rg, rb, ra = self.emissive.filter(ImageFilter.GaussianBlur(4 * K)).split()
        ra = ra.point(lambda v: int(255 * (v / 255.0) ** 1.4))
        rim = Image.merge("RGBA", (rr, rg, rb, ra))
        # Halo ambiente: el grano que se veía "por fuera" era la COLA TENUE de
        # este halo. Sobre panel emisivo negro, el dither deja puntitos sueltos
        # ahí. Curva gamma dura -> la cola tenue va a NEGRO PURO (0 = no genera
        # grano), manteniendo solo el glow cercano al ojo.
        r, g, b, a = self.emissive.filter(ImageFilter.GaussianBlur(6 * K)).split()
        a = a.point(lambda v: int(255 * (v / 255.0) ** 2.0 * 0.42))
        halo = Image.merge("RGBA", (r, g, b, a))
        img.alpha_composite(halo)
        img.alpha_composite(rim)
        img.alpha_composite(self.emissive)
        return img


# ============================ EMOCIONES ============================

def F(m=None, **eyes):
    """Crea un frame con dos ojos por defecto, boca opcional (m=dict) y overrides."""
    fr = Frame()
    l = dict(center=EYE_L)
    r = dict(center=EYE_R)
    l.update(eyes.get("l", {}))
    r.update(eyes.get("r", {}))
    if not eyes.get("skip_l"):
        fr.eye(**l)
    if not eyes.get("skip_r"):
        fr.eye(**r)
    if m:
        fr.mouth(**m)
    return fr


def frames_blink(base_l=None, base_r=None, ms=38, mouth=None):
    """Parpadeo con easing sobre un estado base."""
    seq = []
    for t in (0.75, 0.35, 0.08, 0.35, 0.75):
        l = dict(base_l or {})
        r = dict(base_r or {})
        l["squash"] = l.get("squash", 1.0) * t
        r["squash"] = r.get("squash", 1.0) * t
        seq.append((F(l=l, r=r, m=mouth), ms))
    return seq


def anim_neutral():
    m = dict(kind="line", w=34, thick=9, curve=2)
    seq = [(F(m=m), 1700)]
    seq += frames_blink(mouth=m)
    seq += [(F(m=m), 750)]
    # mirada a la izquierda con squash-stretch sutil (la boca acompaña)
    for t in (0.35, 1.0):
        e = ease(t)
        seq.append((F(l=dict(dx=-7 * e, squash=1 - 0.06 * e), r=dict(dx=-7 * e, squash=1 - 0.06 * e),
                      m=dict(m, dx=-4 * e)), 60))
    seq.append((F(l=dict(dx=-7), r=dict(dx=-7), m=dict(m, dx=-4)), 800))
    for t in (0.5, 1.0):
        e = ease(t)
        seq.append((F(l=dict(dx=-7 + 14 * e), r=dict(dx=-7 + 14 * e), m=dict(m, dx=-4 + 8 * e)), 60))
    seq.append((F(l=dict(dx=7), r=dict(dx=7), m=dict(m, dx=4)), 700))
    for t in (0.5, 1.0):
        e = ease(t)
        seq.append((F(l=dict(dx=7 - 7 * e), r=dict(dx=7 - 7 * e), m=dict(m, dx=4 - 4 * e)), 60))
    seq += frames_blink(mouth=m)
    return seq


def anim_happy():
    seq = []
    for i in range(10):
        t = i / 10.0
        b = math.sin(t * 2 * math.pi)
        seq.append((F(l=dict(crescent=True, dy=-2 * b, squash=0.9),
                      r=dict(crescent=True, dy=-2 * b, squash=0.9),
                      m=dict(kind="line", w=54, curve=9, thick=10, dy=-2 * b)), 85))
    return seq


def anim_laughing():
    seq = []
    for i in range(10):
        t = i / 10.0
        b = math.sin(t * 2 * math.pi * 2)
        seq.append((F(l=dict(crescent=True, dy=3 * b, squash=0.85 + 0.1 * b),
                      r=dict(crescent=True, dy=3 * b, squash=0.85 + 0.1 * b),
                      m=dict(kind="open", w=50, open_h=18 + 5 * b, center=(120, 174),
                             dy=2 * b)), 70))
    return seq


def anim_sad():
    seq = []
    for i in range(10):
        t = i / 10.0
        s = math.sin(t * 2 * math.pi)
        seq.append((F(l=dict(rot=-11, dy=6 + s, squash=0.8, lid=0.25),
                      r=dict(rot=11, dy=6 + s, squash=0.8, lid=0.25),
                      m=dict(kind="line", w=44, curve=-8, thick=10, center=(120, 179),
                             dy=s)), 130))
    return seq


def anim_crying():
    seq = []
    for i in range(10):
        t = i / 10.0
        fr = F(l=dict(rot=-11, dy=6, squash=0.7, lid=0.3),
               r=dict(rot=11, dy=6, squash=0.7, lid=0.3),
               m=dict(kind="line", w=38, curve=-7, thick=9, center=(120, 179)))
        for (ex, _), off in ((EYE_L, 0.0), (EYE_R, 0.45)):
            p = (t + off) % 1.0
            fr.tear((ex, 158 + p * 62), alpha=int(255 * (1 - p * 0.75)))
        seq.append((fr, 90))
    return seq


def anim_angry():
    seq = []
    for i in range(8):
        t = i / 8.0
        sh = 1.6 * math.sin(t * 2 * math.pi * 2)
        seq.append((F(l=dict(rot=13, squash=0.62, dx=sh, lid=0.2),
                      r=dict(rot=-13, squash=0.62, dx=sh, lid=0.2),
                      m=dict(kind="line", w=48, curve=-4, thick=11, dx=sh)), 80))
    return seq


def anim_sleepy():
    seq = []
    for i in range(12):
        t = i / 12.0
        o = 0.36 + 0.14 * math.sin(t * 2 * math.pi)
        fr = F(l=dict(squash=o, dy=6, lid=0.35), r=dict(squash=o, dy=6, lid=0.35),
               m=dict(kind="line", w=24, curve=1, thick=8, center=(120, 183)))
        fr.zzz(t)
        seq.append((fr, 140))
    return seq


def anim_surprised():
    seq = []
    for i in range(8):
        t = i / 8.0
        s = 1.1 + 0.08 * math.sin(t * 2 * math.pi)
        seq.append((F(l=dict(scale=s, rad=40), r=dict(scale=s, rad=40),
                      m=dict(kind="ring", r=10 * s, thick=10, center=(120, 176))), 90))
    return seq


def anim_shocked():
    seq = []
    for i in range(8):
        t = i / 8.0
        s = 1.16 + 0.1 * math.sin(t * 2 * math.pi * 2)
        dx = 1.6 * math.sin(t * 2 * math.pi * 3)
        seq.append((F(l=dict(scale=s, rad=44, dx=dx), r=dict(scale=s, rad=44, dx=dx),
                      m=dict(kind="ring", r=12 * s, thick=11, center=(120, 176), dx=dx)), 70))
    return seq


def anim_thinking():
    seq = []
    for n in (1, 2, 3, 3, 3, 2):
        fr = F(l=dict(dx=6, dy=-6, squash=0.82), r=dict(dx=6, dy=-6, squash=0.7, lid=0.2),
               m=dict(kind="line", w=26, curve=2, thick=9, dx=8, tilt=-6))
        fr.dots(n)
        seq.append((fr, 210))
    return seq


def anim_confused():
    seq = []
    for i in range(10):
        t = i / 10.0
        s = math.sin(t * 2 * math.pi)
        seq.append((F(l=dict(scale=1.06, rot=4 * s), r=dict(scale=0.8, rot=-6 * s, dy=4),
                      m=dict(kind="wavy", w=42, amp=3.2, thick=9, phase=t, tilt=3 * s)), 110))
    return seq


def anim_winking():
    m = dict(kind="line", w=46, curve=5, smirk=6, thick=10)
    open_fr = (F(m=m), 1000)
    seq = [open_fr]
    for t in (0.4, 1.0, 1.0, 0.4):
        seq.append((F(l=dict(), r=dict(crescent=True, squash=0.55, dy=4), m=m),
                    90 if t == 1.0 else 60))
    seq.append((F(m=m), 600))
    return seq


def anim_loving():
    seq = []
    for i in range(10):
        t = i / 10.0
        beat = 1.0 + 0.12 * max(0.0, math.sin(t * 2 * math.pi * 2)) * (1.0 if t < 0.5 else 0.35)
        fr = Frame()
        fr.heart(EYE_L, 62, beat)
        fr.heart(EYE_R, 62, beat)
        fr.mouth(kind="line", w=48, curve=8, thick=10)
        seq.append((fr, 90))
    return seq


def anim_cool():
    m = dict(kind="line", w=44, curve=3, smirk=6, thick=10)
    fr0 = Frame()
    fr0.visor()
    fr0.mouth(**m)
    seq = [(fr0, 1500)]
    for i in range(8):
        g = i / 7.0
        fr = Frame()
        fr.visor(glint=g)
        fr.mouth(**m)
        seq.append((fr, 55))
    fr1 = Frame()
    fr1.visor()
    fr1.mouth(**m)
    seq.append((fr1, 700))
    return seq


def anim_confident():
    seq = []
    for i in range(8):
        t = i / 8.0
        s = math.sin(t * 2 * math.pi)
        seq.append((F(l=dict(lid=0.42, squash=0.85, rot=4), r=dict(lid=0.42 - 0.06 * s, squash=0.85, rot=-4),
                      m=dict(kind="line", w=46, curve=4, smirk=7, thick=10)), 120))
    return seq


def anim_embarrassed():
    seq = []
    for i in range(10):
        t = i / 10.0
        look = 7 * math.sin(t * 2 * math.pi)
        fr = F(l=dict(dx=look, squash=0.72, dy=3), r=dict(dx=look, squash=0.72, dy=3),
               m=dict(kind="wavy", w=28, amp=2.2, thick=8, dy=3, dx=0.6 * look,
                      phase=0.25 * math.sin(t * 2 * math.pi)))
        fr.blush(alpha=120 + int(50 * abs(math.sin(t * math.pi * 2))))
        seq.append((fr, 115))
    return seq


def anim_funny():
    seq = []
    for i in range(8):
        t = i / 8.0
        b = math.sin(t * 2 * math.pi * 2)
        fr = F(l=dict(scale=1.1 + 0.05 * b), r=dict(crescent=True, squash=0.9),
               m=dict(kind="open", w=44, open_h=16 + 2 * b, center=(120, 173)))
        fr.tongue(wig=b, dy=7)
        seq.append((fr, 90))
    return seq


def anim_silly():
    seq = []
    for i in range(10):
        t = i / 10.0
        s = math.sin(t * 2 * math.pi)
        fr = F(l=dict(scale=1.0 + 0.12 * s, rot=6 * s), r=dict(scale=1.0 - 0.12 * s, rot=-6 * s),
               m=dict(kind="open", w=36, open_h=13, center=(120, 173), tilt=5 * s))
        fr.tongue(wig=math.cos(t * 2 * math.pi), dy=7)
        seq.append((fr, 95))
    return seq


def anim_kissy():
    seq = []
    for i in range(12):
        t = i / 12.0
        fr = F(l=dict(crescent=True, squash=0.9), r=dict(crescent=True, squash=0.9),
               m=dict(kind="ring", r=7 + 0.8 * math.sin(t * 2 * math.pi), thick=9,
                      center=(120, 174)))
        p = t
        fr.heart((120, 168 - p * 26), 26 * (1 - p * 0.35), 1.0)
        seq.append((fr, 90))
    return seq


def anim_relaxed():
    seq = []
    for i in range(10):
        t = i / 10.0
        b = math.sin(t * 2 * math.pi)
        seq.append((F(l=dict(crescent=True, squash=0.8, dy=b), r=dict(crescent=True, squash=0.8, dy=b),
                      m=dict(kind="line", w=46, curve=7, thick=9, dy=b)), 150))
    return seq


def anim_delicious():
    seq = []
    for i in range(10):
        t = i / 10.0
        lick = math.sin(t * 2 * math.pi)
        fr = F(l=dict(crescent=True), r=dict(crescent=True),
               m=dict(kind="open", w=40, open_h=12, center=(120, 172)))
        fr.tongue(wig=lick, dy=7)
        seq.append((fr, 100))
    return seq


EMOTIONS = {
    "neutral": anim_neutral,
    "robot_2": anim_neutral,
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


def snap565(pal):
    """Ajusta cada color de la paleta a la grilla RGB565 (lo que el panel puede mostrar).
    Así el color del GIF == color en pantalla: el firmware no vuelve a truncar."""
    out = []
    for i in range(0, len(pal), 3):
        r, g, b = pal[i], pal[i + 1], pal[i + 2]
        r5, g6, b5 = r >> 3, g >> 2, b >> 3
        out += [(r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)]
    return out


def save_gif(name, seq, size, outdir, colors=255):
    frames = []
    durations = []
    for fr, ms in seq:
        frames.append(fr.compose().resize((size, size), Image.LANCZOS).convert("RGB"))
        durations.append(ms)
    # paleta global tomada de varios frames repartidos
    n = len(frames)
    idxs = sorted({int(i * (n - 1) / 7) for i in range(8)}) if n > 1 else [0]
    strip = Image.new("RGB", (size, size * len(idxs)))
    for j, ix in enumerate(idxs):
        strip.paste(frames[ix], (0, j * size))
    ref = strip.quantize(colors=colors, method=Image.MEDIANCUT)
    ref.putpalette(snap565(ref.getpalette()))  # colores exactos del panel
    # Floyd-Steinberg: difunde el error -> degradé suave, sin grilla ni escalones
    qframes = [f.quantize(palette=ref, dither=Image.FLOYDSTEINBERG) for f in frames]
    path = os.path.join(outdir, f"{name}.gif")
    qframes[0].save(path, save_all=True, append_images=qframes[1:],
                    duration=durations, loop=0, optimize=True, disposal=1)
    print(f"  {name}.gif  {len(qframes)}f  {os.path.getsize(path)//1024} KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=240)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--only", default=None, help="generar solo una emocion")
    ap.add_argument("--colors", type=int, default=255)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    outdir = args.outdir or os.path.join(here, f"robot-pro_{args.size}")
    os.makedirs(outdir, exist_ok=True)

    total = 0
    for name, fn in EMOTIONS.items():
        if args.only and name != args.only:
            continue
        save_gif(name, fn(), args.size, outdir, colors=args.colors)
        total += os.path.getsize(os.path.join(outdir, f"{name}.gif"))
    print(f"TOTAL: {total/1024/1024:.2f} MB")


if __name__ == "__main__":
    main()

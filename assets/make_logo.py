"""LumoraTools logosunu üretir: assets/logo.png (512), icon.png (256) ve çok boyutlu icon.ico.

Tasarım: indigo→mor degrade zemin üzerinde büyük beyaz bir "L"; L'nin sol üst köşesine bitişik, daha küçük bir "T". Sağ üstte ışık saçan sarı bir kıvılcım
(lumen = ışık). Çalıştır: py assets/make_logo.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent
S = 2048                       # süper örnekleme: sonra küçültülür, kenarlar pürüzsüz çıkar
SIZE = 512
CORNER = int(S * 0.225)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background() -> Image.Image:
    c1, c2, c3 = (67, 56, 202), (109, 40, 217), (168, 85, 247)      # indigo → mor → açık mor
    grad = Image.new("RGB", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x * 0.45 + y * 0.55) / S
            px[x, y] = lerp(c1, c2, t * 2) if t < 0.5 else lerp(c2, c3, (t - 0.5) * 2)
    glow = Image.new("L", (S, S), 0)                                 # sol üstten yumuşak ışık
    ImageDraw.Draw(glow).ellipse((-S * 0.3, -S * 0.5, S * 0.75, S * 0.45), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.08))
    grad = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), grad, glow)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=CORNER, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    return img


def star(cx, cy, r, color):
    """Dört kollu kıvılcım."""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    k = r * 0.28
    pts = [(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
           (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)]
    ImageDraw.Draw(layer).polygon(pts, fill=color)
    return layer


def letters() -> tuple[Image.Image, Image.Image]:
    """(gölge, harfler): büyük L ve sol üst köşesine bitişik, daha küçük bir T."""
    t = int(S * 0.165)                                       # L'nin çizgi kalınlığı
    rad = int(t * 0.30)
    stem_x, top, bottom, foot_right = int(S * 0.43), int(S * 0.20), int(S * 0.80), int(S * 0.83)
    shapes_l = [
        (stem_x, top, stem_x + t, bottom),                   # L gövdesi
        (stem_x, bottom - t, foot_right, bottom),            # L tabanı
    ]
    # T: kolunun sağ ucu L'nin gövdesine biner (yapışık görünür), gövdesi aşağı sarkar
    bar = (int(S * 0.14), top, stem_x + int(S * 0.07), top + int(S * 0.125))
    mid = (bar[0] + bar[2]) // 2
    half = int(S * 0.058)
    stem_t = (mid - half, bar[3] - rad, mid + half, int(S * 0.62))
    shapes_t = [bar, stem_t]

    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    off = int(S * 0.014)
    for x0, y0, x1, y1 in (*shapes_l, *shapes_t):
        sd.rounded_rectangle((x0, y0 + off, x1, y1 + off), rad, fill=(30, 10, 80, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.014))

    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for box in shapes_l:
        d.rounded_rectangle(box, rad, fill=(255, 255, 255, 255))
    for box in shapes_t:                                     # T hafif mavimsi: L'den ayırt edilir
        d.rounded_rectangle(box, rad, fill=(224, 231, 255, 255))
    return shadow, layer


def build() -> Image.Image:
    img = background()
    shadow, layer = letters()
    img = Image.alpha_composite(img, shadow)
    img = Image.alpha_composite(img, layer)

    cx, cy, r = int(S * 0.80), int(S * 0.255), int(S * 0.14)
    halo = Image.new("RGBA", (S, S), (0, 0, 0, 0))                    # kıvılcımın parıltısı
    ImageDraw.Draw(halo).ellipse((cx - r * 1.5, cy - r * 1.5, cx + r * 1.5, cy + r * 1.5), fill=(255, 246, 200, 105))
    img = Image.alpha_composite(img, halo.filter(ImageFilter.GaussianBlur(S * 0.04)))
    img = Image.alpha_composite(img, star(cx, cy, r, (254, 240, 138, 255)))
    img = Image.alpha_composite(img, star(cx, cy, r * 0.52, (255, 255, 255, 255)))

    mask = Image.new("L", (S, S), 0)                                  # köşe dışına taşan her şeyi kes
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=CORNER, fill=255)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return img


def main() -> None:
    big = build()
    logo = big.resize((SIZE, SIZE), Image.LANCZOS)
    logo.save(OUT / "logo.png")
    logo.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon.ico", sizes=sizes)
    print("yazildi:", OUT / "logo.png", OUT / "icon.png", OUT / "icon.ico")


if __name__ == "__main__":
    main()

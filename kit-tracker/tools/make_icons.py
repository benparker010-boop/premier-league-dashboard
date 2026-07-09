"""Generate PWA / home-screen icons for Kit Tracker.

Draws a flat package-box glyph (top view with tape) in white on the brand
blue, at every size iOS and Android need. Run once; commit the PNGs.

    python tools/make_icons.py
"""
import os

from PIL import Image, ImageDraw

BRAND = (11, 95, 255)  # --brand
WHITE = (255, 255, 255)
OUT_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "static", "icons")


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_box_glyph(size, motif_scale, bg_radius_frac):
    """A single icon: brand-blue rounded square with a white taped-box glyph."""
    # Supersample for crisp edges, then downscale.
    ss = 4
    n = size * ss
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background (rounded square). Full bleed; corner radius scales with size.
    rounded(d, (0, 0, n - 1, n - 1), int(n * bg_radius_frac), BRAND)

    # Box glyph, centred, occupying `motif_scale` of the canvas.
    m = n * motif_scale
    x0 = (n - m) / 2
    y0 = (n - m) / 2
    x1 = x0 + m
    y1 = y0 + m
    box_radius = int(m * 0.10)
    stroke = max(2, int(m * 0.075))

    # Box body: white rounded square.
    rounded(d, (x0, y0, x1, y1), box_radius, WHITE)

    # Lid seam: a horizontal blue band across the upper third (where flaps meet).
    seam_y = y0 + m * 0.34
    d.rectangle((x0, seam_y - stroke / 2, x1, seam_y + stroke / 2), fill=BRAND)

    # Tape: a vertical blue strip down the centre, crossing the seam.
    cx = x0 + m / 2
    d.rectangle((cx - stroke / 2, y0, cx + stroke / 2, y1), fill=BRAND)

    return img.resize((size, size), Image.LANCZOS)


def save(img, name):
    path = os.path.normpath(os.path.join(OUT_DIR, name))
    # Flatten onto white so no transparency reaches iOS (it dislikes alpha).
    flat = Image.new("RGB", img.size, WHITE)
    flat.paste(img, (0, 0), img)
    flat.save(path, format="PNG")
    print("wrote", os.path.relpath(path))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # Standard PWA icons: modest corner radius, generous motif.
    save(draw_box_glyph(192, motif_scale=0.60, bg_radius_frac=0.18), "icon-192.png")
    save(draw_box_glyph(512, motif_scale=0.60, bg_radius_frac=0.18), "icon-512.png")
    # Maskable: Android may crop to a circle, so keep the motif inside the
    # 80% safe zone (smaller motif, full-bleed background, no rounded corners).
    save(draw_box_glyph(512, motif_scale=0.46, bg_radius_frac=0.0), "maskable-512.png")
    # Apple touch icon: full bleed, iOS applies its own mask.
    save(draw_box_glyph(180, motif_scale=0.58, bg_radius_frac=0.0), "apple-touch-icon.png")
    # Favicon.
    save(draw_box_glyph(32, motif_scale=0.62, bg_radius_frac=0.22), "favicon-32.png")


if __name__ == "__main__":
    main()

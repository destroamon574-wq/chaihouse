from PIL import Image, ImageDraw, ImageFont
from math import cos, sin, pi

W, H = 1200, 630
img = Image.new("RGB", (W, H), "#100b08")
d = ImageDraw.Draw(img, "RGBA")

# vertical gradient
for y in range(H):
    t = y / H
    r = int(30 + (12 - 30) * t)
    g = int(20 + (8 - 20) * t)
    b = int(14 + (6 - 14) * t)
    d.line([(0, y), (W, y)], fill=(r, g, b, 255))

# warm glow right
for radius in range(420, 0, -8):
    a = int(22 * (1 - radius / 420))
    d.ellipse([900 - radius, 300 - radius, 900 + radius, 300 + radius], fill=(233, 167, 82, a))


# lattice pattern
def star(draw, cx, cy, r, color):
    pts = []
    for i in range(16):
        ang = -pi / 2 + i * pi / 8
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rr * cos(ang), cy + rr * sin(ang)))
    draw.polygon(pts, outline=color)


for gy in range(0, H + 120, 120):
    for gx in range(0, W + 120, 120):
        star(d, gx, gy, 54, (217, 164, 65, 28))
        d.ellipse([gx - 3, gy - 3, gx + 3, gy + 3], fill=(217, 164, 65, 45))

# big emblem right
cx, cy = 900, 315
d.ellipse([cx - 178, cy - 178, cx + 178, cy + 178], outline=(217, 164, 65, 130), width=2)
d.ellipse([cx - 150, cy - 150, cx + 150, cy + 150], outline=(163, 75, 44, 180), width=2)
star(d, cx, cy, 132, (217, 164, 65, 170))
star(d, cx, cy, 92, (217, 164, 65, 105))
# cup
d.rounded_rectangle([cx - 42, cy - 22, cx + 42, cy + 40], radius=18, fill=(244, 232, 212, 235))
d.arc([cx + 34, cy - 8, cx + 78, cy + 34], 270, 90, fill=(244, 232, 212, 235), width=9)
d.ellipse([cx - 58, cy + 38, cx + 58, cy + 54], fill=(244, 232, 212, 235))
d.arc([cx - 28, cy - 52, cx - 8, cy - 10], 90, 260, fill=(244, 232, 212, 180), width=5)
d.arc([cx + 4, cy - 56, cx + 24, cy - 14], 90, 260, fill=(244, 232, 212, 150), width=5)

# text
georgia_b = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 104)
georgia = ImageFont.truetype("C:/Windows/Fonts/georgia.ttf", 38)
segoe = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24)
segoe_small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)

d.text((84, 92), "Ч А Й Х А Н А   ·   L O U N G E   B A R", font=segoe_small, fill=(224, 174, 91, 255))
d.text((80, 138), "ЧайHouse", font=georgia_b, fill=(246, 237, 222, 255))
d.rectangle([86, 278, 226, 283], fill=(184, 85, 47, 255))
d.text((84, 316), "Восточная кухня, чай", font=georgia, fill=(232, 217, 194, 255))
d.text((84, 364), "и неспешные вечера", font=georgia, fill=(232, 217, 194, 255))
d.text((84, 470), "Плов · лагман · манты · шашлык · чай", font=segoe, fill=(198, 165, 115, 255))
d.text((84, 530), "Москва, Ходынский бульвар, 4", font=segoe, fill=(185, 173, 156, 255))
d.text(
    (84, 564), "ТРЦ «Авиапарк», 3 этаж · ежедневно 12:00–00:00", font=segoe_small, fill=(150, 139, 123, 255)
)

# vignette
for i in range(80):
    a = int(80 * (1 - i / 80))
    d.rectangle([i, i, W - i, H - i], outline=(0, 0, 0, a), width=1)

img.save("static/img/og-cover.jpg", "JPEG", quality=88, optimize=True)
print("written static/img/og-cover.jpg")

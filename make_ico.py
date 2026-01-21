from PIL import Image

src = "icono.png"
dst = "MovilidadESII.ico"

img = Image.open(src).convert("RGBA")
sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
img.save(dst, format="ICO", sizes=sizes)
print("OK:", dst)

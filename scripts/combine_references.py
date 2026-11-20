"""Combined review sheet: the style references (docs/style-references/*.jfif) beside the gallery contact sheets.

    python scripts/combine_references.py

Run scripts/render_gallery.py first. Output: docs/style-gallery/contact-with-references.png
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent; g = root/"docs/style-gallery"; r = root/"docs/style-references"
bg=(30,31,36); fg=(235,235,240)
try: font=ImageFont.truetype("arial.ttf",30); big=ImageFont.truetype("arialbd.ttf",40)
except: font=big=ImageFont.load_default()
c169=Image.open(g/"contact-16x9.png").convert("RGB"); H=c169.height
c916=Image.open(g/"contact-9x16.png").convert("RGB")
c916=c916.resize((round(c916.width*H/c916.height),H),Image.LANCZOS)
refs=sorted(r.glob("*.jfif")); W=760; pad=20; lab=44
avail=(H-len(refs)*(lab+pad))
ims=[Image.open(p).convert("RGB") for p in refs]
sc=[min((W-2*pad)/i.width, 10) for i in ims]
tot=sum(i.height*s for i,s in zip(ims,sc))
k=min(1,avail/tot)
col=Image.new("RGB",(W,H),bg); d=ImageDraw.Draw(col); y=pad
for p,i,s in zip(refs,ims,sc):
    d.text((pad,y),p.stem,fill=fg,font=font); y+=lab
    im=i.resize((round(i.width*s*k),round(i.height*s*k)),Image.LANCZOS)
    col.paste(im,(pad,y)); y+=im.height+pad
gap=40; top=70
out=Image.new("RGB",(W+c169.width+c916.width+2*gap,H+top),bg); d=ImageDraw.Draw(out)
x=0
for title,im in [("References",col),("Gallery 16:9",c169),("Gallery 9:16",c916)]:
    d.text((x+20,15),title,fill=fg,font=big); out.paste(im,(x,top)); x+=im.width+gap
dst=g/"contact-with-references.png"; out.save(dst,optimize=True); print(dst,out.size)

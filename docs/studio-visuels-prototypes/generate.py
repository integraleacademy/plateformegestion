"""Génère huit planches statiques A3P, sans dépendance au Studio de production."""
from pathlib import Path
import base64
import json
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).parent
OUT = ROOT / "exports"
OUT.mkdir(exist_ok=True)
THEMES = json.loads((ROOT / "themes.json").read_text())
GREEN = THEMES["A3P"]
INK, CREAM, WHITE = "#101b1a", "#f3f1e9", "#ffffff"
LOGO = Image.open(ROOT.parents[1] / "static/img/logo-integrale.png").convert("RGBA")

def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)

def text(draw, xy, value, size, fill, bold=False, anchor=None, spacing=8):
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, anchor=anchor, spacing=spacing)

def brand(im, xy=(60, 50), size=140, slogan_fill=INK, slogan_xy=None):
    logo = LOGO.resize((size, size), Image.Resampling.LANCZOS)
    im.alpha_composite(logo, xy)
    d = ImageDraw.Draw(im)
    sx, sy = slogan_xy or (xy[0] + size + 22, xy[1] + size // 2 - 20)
    text(d, (sx, sy), "Faites le premier pas vers\nvotre futur métier", 22, slogan_fill, True, spacing=3)

def footer(d, y, fill, line=None):
    if line: d.rectangle((60, y-20, 1020, y-16), fill=line)
    text(d, (60, y), "04 22 47 07 68", 23, fill, True)
    text(d, (1020, y), "www.integraleacademy.com", 23, fill, True, "ra")

def badge(d, xy, label, fg=WHITE, bg=GREEN, w=118):
    x,y=xy; d.rounded_rectangle((x,y,x+w,y+48), 24, fill=bg)
    text(d, (x+w/2,y+24), label, 23, fg, True, "mm")

def cta(d, box, dark=False):
    d.rounded_rectangle(box, 18, fill=WHITE if dark else GREEN)
    size = 20 if box[2] - box[0] < 400 else 24
    text(d, ((box[0]+box[2])/2,(box[1]+box[3])/2), "Inscrivez-vous dès maintenant", size, INK if dark else WHITE, True, "mm")

def photo(size=(1080,1080)):
    """Portrait éditorial stylisé servant uniquement de photographie de prototype."""
    im=Image.new("RGB", size, "#74958a"); d=ImageDraw.Draw(im)
    for y in range(size[1]):
        t=y/size[1]; d.line((0,y,size[0],y), fill=(int(100-35*t),int(150-55*t),int(135-45*t)))
    d.ellipse((190,90,900,800), fill="#b8ccbf")
    d.ellipse((405,225,680,500), fill="#c99272")
    d.polygon(((405,330),(445,180),(650,185),(700,340),(650,280),(465,285)), fill="#202c2a")
    d.ellipse((300,440,800,1080), fill="#172422")
    d.polygon(((475,485),(610,485),(700,880),(420,880)), fill="#e4e8df")
    d.rectangle((0,900,size[0],size[1]), fill="#17362e")
    return im.filter(ImageFilter.GaussianBlur(1.2)).convert("RGBA")

PHOTO=photo()
def save(im, n):
    """Écrit le PNG local et sa représentation texte révisable dans une PR."""
    png = OUT / f"{n:02d}.png"
    im.convert("RGB").save(png, quality=95)
    (OUT / f"{n:02d}.png.base64").write_text(
        base64.encodebytes(png.read_bytes()).decode("ascii")
    )

def p1():
    im=PHOTO.copy(); im.alpha_composite(Image.new("RGBA",im.size,(5,18,17,150))); d=ImageDraw.Draw(im)
    brand(im,(62,48),150,WHITE); badge(d,(62,270),"A3P")
    text(d,(62,345),"DEVENEZ AGENT\nDE PROTECTION\nPHYSIQUE DES\nPERSONNES",62,WHITE,True,spacing=3)
    text(d,(65,690),"DU 1ER SEPTEMBRE AU 27 OCTOBRE 2026",25,"#9bf2c8",True)
    text(d,(65,738),"Examen 28 octobre 2026  •  Puget-sur-Argens",23,WHITE)
    text(d,(65,780),"328 heures  •  CPF et France Travail",23,WHITE)
    cta(d,(62,840,484,910)); footer(d,1000,WHITE,GREEN); save(im,1)

def p2():
    im=Image.new("RGBA",(1080,1080),WHITE); im.alpha_composite(PHOTO.crop((120,0,660,1080)),(0,0)); d=ImageDraw.Draw(im)
    d.rectangle((540,0,1080,1080),fill=WHITE); brand(im,(584,50),128,INK,(730,88)); badge(d,(584,222),"A3P")
    text(d,(584,300),"Devenez agent de\nprotection physique\ndes personnes",42,INK,True,spacing=2)
    d.rectangle((584,510,1018,514),fill=GREEN)
    text(d,(584,550),"SESSION",18,GREEN,True); text(d,(584,580),"Du 1er septembre au 27 octobre 2026",22,INK,True)
    text(d,(584,644),"EXAMEN  28 octobre 2026",20,INK); text(d,(584,690),"LIEU  Puget-sur-Argens",20,INK)
    text(d,(584,736),"DURÉE  328 heures",20,INK); text(d,(584,782),"FINANCEMENT  CPF et France Travail",20,INK)
    cta(d,(584,850,1018,918)); footer(d,1006,INK); save(im,2)

def p3():
    im=Image.new("RGBA",(1080,1080),"#dff5e9"); d=ImageDraw.Draw(im); d.ellipse((710,-220,1160,230),fill=GREEN)
    brand(im,(62,50),135,INK); badge(d,(62,240),"A3P",WHITE,INK)
    text(d,(58,312),"PROTÉGER",99,INK,True); text(d,(58,407),"EST UN",99,GREEN,True); text(d,(58,502),"MÉTIER.",112,INK,True)
    text(d,(62,642),"Devenez agent de protection physique des personnes",28,INK,True)
    d.rectangle((62,700,1018,704),fill=GREEN)
    text(d,(62,738),"Du 1er septembre au 27 octobre 2026",30,INK,True); text(d,(62,795),"EXAMEN 28 OCTOBRE 2026  /  PUGET-SUR-ARGENS  /  328 HEURES",18,INK)
    text(d,(62,840),"CPF et France Travail",23,GREEN,True); cta(d,(650,902,1018,965)); footer(d,1015,INK); save(im,3)

def p4():
    im=Image.new("RGBA",(1080,1080),CREAM); d=ImageDraw.Draw(im); d.polygon(((0,0),(1080,0),(1080,330),(0,720)),fill=INK)
    mask=Image.new("L",(1080,1080)); md=ImageDraw.Draw(mask); md.polygon(((500,180),(1080,0),(1080,850),(330,850)),fill=255)
    ph=PHOTO.copy(); ph.putalpha(mask); im.alpha_composite(ph); d=ImageDraw.Draw(im)
    d.polygon(((0,720),(1080,330),(1080,450),(0,840)),fill=GREEN)
    brand(im,(60,45),140,WHITE); badge(d,(60,300),"A3P")
    text(d,(60,370),"DEVENEZ\nAGENT DE\nPROTECTION",58,WHITE,True,spacing=2)
    text(d,(58,825),"PHYSIQUE DES PERSONNES",45,INK,True)
    text(d,(60,895),"Du 1er septembre au 27 octobre 2026  •  Examen 28 octobre",22,INK)
    text(d,(60,935),"Puget-sur-Argens  •  328 heures  •  CPF et France Travail",22,INK)
    cta(d,(650,816,1018,880)); footer(d,1015,INK); save(im,4)

def p5():
    im=Image.new("RGBA",(1080,1080),"#f6f8f5"); d=ImageDraw.Draw(im); brand(im,(60,48),135,INK); badge(d,(882,65),"A3P")
    text(d,(60,245),"Votre avenir dans la\nprotection commence ici.",53,INK,True)
    text(d,(60,380),"Devenez agent de protection physique des personnes",25,GREEN,True)
    cards=[("DATES","Du 1er septembre au\n27 octobre 2026\nExamen 28 octobre 2026"),("LIEU","Puget-sur-Argens\nFormation en présentiel"),("FINANCEMENT","CPF et France Travail\n328 heures")]
    for i,(a,b) in enumerate(cards):
        x=60+i*330; d.rounded_rectangle((x,475,x+300,720),24,fill=WHITE,outline="#d6e3dc",width=3); d.ellipse((x+24,500,x+66,542),fill=GREEN)
        text(d,(x+25,565),a,18,GREEN,True); text(d,(x+25,610),b,19,INK,True,spacing=8)
    cta(d,(60,790,480,862)); text(d,(60,905),"Une formation A3P pour faire de votre vigilance un métier.",23,INK)
    footer(d,1010,INK,GREEN); save(im,5)

def p6():
    im=Image.new("RGBA",(1080,1080),"#071411"); d=ImageDraw.Draw(im); d.rectangle((760,0,1080,1080),fill="#0c211b"); d.ellipse((790,110,1160,480),outline=GREEN,width=18)
    brand(im,(60,55),150,WHITE); badge(d,(60,270),"FORMATION A3P",INK,GREEN,230)
    text(d,(60,350),"L'EXIGENCE\nDE PROTÉGER.",66,WHITE,True)
    text(d,(60,515),"Devenez agent de protection physique\ndes personnes",30,"#a9c8bb",True)
    text(d,(60,630),"Du 1er septembre au 27 octobre 2026",27,WHITE,True); text(d,(60,685),"Examen 28 octobre 2026  •  Puget-sur-Argens",23,"#a9c8bb")
    text(d,(60,730),"328 heures  •  CPF et France Travail",23,"#a9c8bb")
    d.rectangle((760,510,764,840),fill=GREEN); text(d,(800,540),"A3P",64,GREEN,True); text(d,(800,635),"RIGUEUR\nMAÎTRISE\nENGAGEMENT",24,WHITE,True,spacing=18)
    cta(d,(60,825,500,897),True); footer(d,1010,WHITE,GREEN); save(im,6)

def p7():
    im=Image.new("RGBA",(1080,1080),WHITE); d=ImageDraw.Draw(im); brand(im,(60,48),135,INK); badge(d,(883,62),"A3P")
    text(d,(60,242),"328",190,GREEN,True); text(d,(555,355),"h",92,INK,True)
    text(d,(60,475),"POUR DEVENIR AGENT DE PROTECTION\nPHYSIQUE DES PERSONNES",38,INK,True)
    d.rectangle((60,590,1018,594),fill="#d5e8df")
    text(d,(60,640),"Du 1er septembre au 27 octobre 2026",27,INK,True); text(d,(60,690),"Examen : 28 octobre 2026",23,INK)
    text(d,(60,735),"Puget-sur-Argens",23,INK); text(d,(60,780),"Financement CPF et France Travail",23,INK)
    cta(d,(618,805,1018,878)); text(d,(618,900),"Votre nouveau métier commence ici.",20,GREEN,True)
    footer(d,1010,INK,GREEN); save(im,7)

def p8():
    im=Image.new("RGBA",(1080,1080),"#15211e"); d=ImageDraw.Draw(im); d.rectangle((0,0,1080,250),fill=GREEN); d.rectangle((0,845,1080,1080),fill=WHITE)
    crop=PHOTO.crop((0,160,1080,830)).resize((960,590)); im.alpha_composite(crop,(60,220)); d=ImageDraw.Draw(im)
    brand(im,(60,42),140,WHITE); badge(d,(866,75),"A3P",GREEN,WHITE)
    d.rectangle((60,610,760,810),fill=(9,24,20,225)); text(d,(90,640),"DEVENEZ AGENT DE PROTECTION\nPHYSIQUE DES PERSONNES",37,WHITE,True)
    cta(d,(90,735,490,795),True)
    text(d,(60,875),"Du 1er septembre au 27 octobre 2026",24,INK,True); text(d,(60,920),"Examen 28 octobre 2026  •  Puget-sur-Argens",21,INK)
    text(d,(60,960),"328 heures  •  CPF et France Travail",21,INK); footer(d,1030,INK,GREEN); save(im,8)

for fn in (p1,p2,p3,p4,p5,p6,p7,p8): fn()
print("8 prototypes 1080 × 1080 générés dans", OUT)

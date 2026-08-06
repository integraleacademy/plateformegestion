from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from pathlib import Path
import random, math
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'static/studio/prototypes/a3p'
OUT.mkdir(parents=True, exist_ok=True)
W=H=1080
GREEN='#42d07d'; DARK='#081812'; INK='#10241b'; CREAM='#f5f0e6'; WHITE='#ffffff'; GOLD='#d9b75c'
reg='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; condensed='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
def F(n,b=True):return ImageFont.truetype(bold if b else reg,n)
def roundrect(d,box,r,fill,outline=None,width=1): d.rounded_rectangle(box,r,fill,outline,width)
def text(d,xy,s,size,fill=WHITE,b=True,anchor=None,spacing=4,align='left'):
 d.multiline_text(xy,s,font=F(size,b),fill=fill,anchor=anchor,spacing=spacing,align=align)
def fit_text(d,s,maxw,start=58,minsize=25,b=True):
 for z in range(start,minsize-1,-1):
  f=F(z,b)
  if d.textbbox((0,0),s,font=f)[2]<=maxw:return f
 return F(minsize,b)
def photo(seed=2):
 random.seed(seed); im=Image.new('RGB',(1080,1080)); p=im.load()
 for y in range(H):
  for x in range(W):
   n=random.randrange(-8,9); p[x,y]=(max(0,26+n+int(y*.018)),max(0,56+n+int(y*.025)),max(0,43+n+int(y*.018)))
 im=im.filter(ImageFilter.GaussianBlur(1));d=ImageDraw.Draw(im,'RGBA')
 # architectural training-center lights
 for x in (80,320,760,1000): d.polygon([(x,0),(x+160,0),(x-80,1080),(x-240,1080)],fill=(255,255,255,14))
 # professional agent portrait/silhouette with dimensional highlights
 d.ellipse((345,95,770,520),fill=(45,31,25,255)); d.ellipse((405,125,715,455),fill=(169,113,80,255));
 d.polygon([(300,1080),(340,610),(490,480),(630,480),(790,610),(870,1080)],fill=(12,22,19,255))
 d.polygon([(470,485),(560,660),(655,485),(710,640),(560,800),(410,640)],fill=(235,235,225,230))
 d.polygon([(495,510),(560,660),(625,510),(600,820),(520,820)],fill=(31,75,55,255))
 d.rectangle((360,620,765,1080),fill=(12,25,20,150)); d.line((370,660,760,660),fill=(75,220,130,120),width=5)
 d.rounded_rectangle((625,685,730,742),10,fill=(230,235,230,230)); d.text((642,696),'A3P',font=F(23),fill=(20,55,38,255))
 return im.filter(ImageFilter.GaussianBlur(.35))
def logo(im,x,y,size=135,dark=False):
 src=Image.open(ROOT / 'static/img/logo-integrale.png').convert('RGBA'); src.thumbnail((size,size),Image.Resampling.LANCZOS)
 # gold background in source is square; round crop
 mask=Image.new('L',src.size); ImageDraw.Draw(mask).ellipse((0,0,*src.size),fill=255); src.putalpha(mask)
 im.alpha_composite(src,(x,y))
def footer(im,d,theme='dark',y=940):
 col=INK if theme=='light' else WHITE
 text(d,(60,y),'Faites le premier pas vers votre futur métier',23,col,False)
 text(d,(60,y+58),'04 22 47 07 68',25,col,True); text(d,(1020,y+58),'www.integraleacademy.com',22,col,True,anchor='ra')
def common_info(d,x,y,col=WHITE,leading=47,size=25):
 lines=['Du 1er septembre au 27 octobre 2026','Examen : 28 octobre 2026','Puget-sur-Argens','328 heures','CPF et France Travail']
 for i,s in enumerate(lines): text(d,(x,y+i*leading),s,size,col,i in (0,1))
def cta(d,box,col=INK,fill=GREEN):
 roundrect(d,box,22,fill); text(d,((box[0]+box[2])//2,(box[1]+box[3])//2),'Inscrivez-vous dès maintenant',25,col,True,anchor='mm')
def save(im,name): im.convert('RGB').save(OUT/name,'PNG',optimize=True)
# 1 full photo
im=photo().convert('RGBA'); shade=Image.new('RGBA',(W,H),(0,10,8,120)); im=Image.alpha_composite(im,shade);d=ImageDraw.Draw(im);logo(im,60,48);text(d,(60,220),'A3P',27,GREEN);text(d,(60,260),'Devenez agent de\nprotection physique\ndes personnes',61,WHITE,True,spacing=2);common_info(d,60,520,WHITE,42,23);cta(d,(60,770,520,840));footer(im,d,y=900);save(im,'01-photo-plein-ecran.png')
#2 split
im=Image.new('RGBA',(W,H),CREAM); im.alpha_composite(photo(3).crop((80,0,620,1080)).convert('RGBA'),(0,0));d=ImageDraw.Draw(im);d.rectangle((520,0,1080,1080),fill=INK);logo(im,870,45,140);text(d,(585,210),'A3P',26,GREEN);text(d,(585,252),'Devenez agent de\nprotection physique\ndes personnes',43);common_info(d,585,460,WHITE,48,22);cta(d,(585,735,1015,805));footer(im,d,y=900);save(im,'02-editorial-photo-gauche.png')
#3 typographic no photo
im=Image.new('RGBA',(W,H),'#eaf4ed');d=ImageDraw.Draw(im);d.ellipse((720,-180,1210,310),fill=GREEN);d.rectangle((0,0,44,H),fill=INK);logo(im,75,55);text(d,(1015,100),'A3P',34,INK,anchor='ra');text(d,(75,250),'DEVENEZ\nAGENT DE',75,INK);text(d,(75,425),'PROTECTION PHYSIQUE\nDES PERSONNES',46,GREEN);d.line((75,550,1000,550),fill=INK,width=4);common_info(d,75,600,INK,50,25);cta(d,(600,680,1000,760));footer(im,d,'light',900);save(im,'03-typographique.png')
#4 diagonal
im=photo(4).convert('RGBA');d=ImageDraw.Draw(im,'RGBA');d.polygon([(0,0),(850,0),(470,1080),(0,1080)],fill=(7,25,18,235));d.polygon([(850,0),(1080,0),(700,1080),(470,1080)],fill=(66,208,125,230));logo(im,55,45);text(d,(70,225),'A3P',27,GREEN);text(d,(70,270),'Devenez agent de\nprotection physique\ndes personnes',52);common_info(d,70,500,WHITE,46,24);cta(d,(70,765,510,835),INK,WHITE);footer(im,d,y=910);save(im,'04-diagonale.png')
#5 cards
im=Image.new('RGBA',(W,H),'#dcece4');d=ImageDraw.Draw(im);logo(im,60,48);text(d,(1020,88),'A3P',30,INK,anchor='ra');text(d,(60,220),'Devenez agent de protection\nphysique des personnes',49,INK);cards=[('DATES','Du 1er septembre au 27 octobre 2026'),('EXAMEN','28 octobre 2026'),('LIEU','Puget-sur-Argens'),('DURÉE','328 heures'),('FINANCEMENT','CPF et France Travail')]
for i,(a,b) in enumerate(cards):
 x=60+(i%2)*490;y=390+(i//2)*135; roundrect(d,(x,y,x+460,y+110),18,WHITE);text(d,(x+22,y+18),a,17,GREEN);text(d,(x+22,y+52),b,20,INK)
cta(d,(550,770,1020,840));footer(im,d,'light',915);save(im,'05-cartes-informations.png')
#6 premium
im=Image.new('RGBA',(W,H),'#07110e');d=ImageDraw.Draw(im);d.ellipse((650,80,1150,580),outline=GOLD,width=2);d.ellipse((715,145,1085,515),outline='#275540',width=12);logo(im,60,50);text(d,(70,235),'A3P — FORMATION',23,GOLD);text(d,(70,285),'Devenez agent de\nprotection physique\ndes personnes',55);d.line((70,505,560,505),fill=GOLD,width=2);common_info(d,70,550,'#d9e6df',48,24);cta(d,(590,690,1010,765),INK,GOLD);footer(im,d,y=910);save(im,'06-sombre-premium.png')
#7 big number
im=Image.new('RGBA',(W,H),'#faf9f3');d=ImageDraw.Draw(im);d.rectangle((0,0,1080,150),fill=GREEN);logo(im,55,25,105);text(d,(1020,74),'A3P',34,INK,anchor='ra');text(d,(60,220),'Devenez agent de protection\nphysique des personnes',45,INK);text(d,(60,400),'328',180,INK);text(d,(440,520),'heures',44,GREEN);common=['Du 1er septembre au 27 octobre 2026','Examen : 28 octobre 2026','Puget-sur-Argens','CPF et France Travail']
for i,s in enumerate(common):text(d,(580,410+i*55),s,21,INK,i<2)
cta(d,(580,680,1020,755));footer(im,d,'light',900);save(im,'07-grand-chiffre.png')
#8 center photo bands
im=Image.new('RGBA',(W,H),'#eef0eb');d=ImageDraw.Draw(im);d.rectangle((0,0,1080,185),fill=INK);d.rectangle((0,825,1080,1080),fill=GREEN); ph=photo(7).crop((150,100,930,880)).resize((690,570)); im.alpha_composite(ph.convert('RGBA'),(195,190));d=ImageDraw.Draw(im,'RGBA');logo(im,50,28,120);text(d,(1025,62),'A3P',28,GREEN,anchor='ra');text(d,(1025,105),'Devenez agent de protection physique\ndes personnes',31,WHITE,anchor='ra',align='right');roundrect(d,(40,260,330,545),20,(5,20,15,225));text(d,(65,290),'DATES',17,GREEN);text(d,(65,330),'Du 1er septembre\nau 27 octobre 2026',22);text(d,(65,420),'EXAMEN',17,GREEN);text(d,(65,460),'28 octobre 2026',21);roundrect(d,(750,500,1040,750),20,(5,20,15,225));text(d,(775,530),'Puget-sur-Argens',20);text(d,(775,585),'328 heures',24,GREEN);text(d,(775,640),'CPF et France Travail',19);cta(d,(560,845,1020,910),INK,WHITE);footer(im,d,'light',945);save(im,'08-photo-centrale.png')

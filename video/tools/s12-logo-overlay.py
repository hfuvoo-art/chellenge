import numpy as np, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
tr=np.array(json.load(open('track.json')),float); n=len(tr); t=np.arange(n)
fit=np.stack([np.polyval(np.polyfit(t,tr[:,k],2),t) for k in range(4)],1)
INS=5
def rect(i):
    L,T,R,B=fit[i]; return L+INS,T+INS,R-INS,B-INS
# --- reference clean texture from frame 1 (fixed, so it never flickers)
a0=np.array(Image.open('fr/0001.png').convert('RGB')).astype(float)
L,T,R,B=[int(round(v)) for v in rect(0)]
reg=a0[T:B,L:R]; colm=np.median(reg,0)
lum=reg.mean(2)/np.maximum(colm.mean(1),1)[None,:]
rowr=np.median(lum,1); yy=np.arange(len(rowr)); rowf=np.polyval(np.polyfit(yy,rowr,2),yy)
tex=colm[None,:,:]*rowf[:,None,None]; TH,TW=tex.shape[:2]
texI=Image.fromarray(np.clip(tex,0,255).astype('uint8'))
# feathered mask in texture space
my=np.minimum(np.minimum(yy,TH-1-yy)/4,1); mx=np.arange(TW); mx=np.minimum(np.minimum(mx,TW-1-mx)/4,1)
maskI=Image.fromarray((my[:,None]*mx[None,:]*255).astype('uint8'))
# per-frame brightness (smooth) so lighting change during pull-back is kept
br=[]
for i in range(n):
    a=np.array(Image.open(f'fr/{i+1:04d}.png').convert('RGB')).astype(float)
    l,tp,r,b=[int(round(v)) for v in rect(i)]
    br.append(np.median(a[tp:b,l:r]))
br=np.array(br); br=np.polyval(np.polyfit(t,br,2),t); br=br/br[0]
# overlay elements: pre-render alpha at ~label size in texture space (TW x TH canvas)
logo=Image.open('logo.png'); logo=logo.crop(logo.getbbox()).split()[-1]
font=ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',64)
def textimg(s):
    w=sum(font.getlength(c)+8 for c in s); im=Image.new('L',(int(w)+10,80),0); d=ImageDraw.Draw(im); x=5
    for c in s: d.text((x,5),c,fill=255,font=font); x+=font.getlength(c)+8
    return im.crop(im.getbbox())
S=4; ov=Image.new('L',(TW*S,TH*S),0)
def put(al,wfrac,cyfrac):
    w=TW*S*wfrac; h=al.size[1]*w/al.size[0]; al=al.resize((int(w),int(h)),Image.LANCZOS)
    ov.paste(al,(int(TW*S/2-w/2),int(TH*S*cyfrac-h/2)),al)
# fractions relative to label rect incl. inset (approx same as before)
put(logo,0.84,0.185); put(textimg('SMOKY POMEGRANATE'),0.66,0.80); put(textimg('FINE FRAGRANCE'),0.52,0.885)
ovI=ov.resize((TW*2,TH*2),Image.LANCZOS)  # 2x texture res for smooth warping
ovI=ovI.filter(ImageFilter.GaussianBlur(0.35)).point(lambda v:int(v*0.95))
INK=np.array([62,42,24],float)
for i in range(n):
    im=Image.open(f'fr/{i+1:04d}.png').convert('RGB'); a=np.array(im).astype(float)
    l,tp,r,b=rect(i); sx=(r-l)/TW; sy=(b-tp)/TH
    # affine: output(x,y) -> texture(u,v) with float precision
    A=(1/sx,0,-l/sx,0,1/sy,-tp/sy)
    tw=np.array(texI.transform(im.size,Image.AFFINE,A,resample=Image.BICUBIC)).astype(float)*br[i]
    mw=np.array(maskI.transform(im.size,Image.AFFINE,A,resample=Image.BILINEAR)).astype(float)[...,None]/255
    A2=(2/sx,0,-2*l/sx,0,2/sy,-2*tp/sy)
    # downscale from 2x via transform then light blur keeps it smooth
    ow=np.array(ovI.transform(im.size,Image.AFFINE,(A2[0]*1,0,A2[2],0,A2[4],A2[5]),resample=Image.BICUBIC)).astype(float)[...,None]/255
    a=a*(1-mw)+tw*mw
    a=a*(1-ow)+INK*ow
    Image.fromarray(np.clip(a,0,255).astype('uint8')).save(f'out/{i+1:04d}.png')
print('ok')

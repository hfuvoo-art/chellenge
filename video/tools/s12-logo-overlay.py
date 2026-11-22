import numpy as np, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
tr=np.array(json.load(open('track.json')),float); n=len(tr); t=np.arange(n)
fit=np.stack([np.polyval(np.polyfit(t,tr[:,k],2),t) for k in range(4)],1)
logo=Image.open('logo.png'); lb=logo.getbbox(); logo=logo.crop(lb)
INK=(62,42,24)
font=ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',64)
def textimg(s):
    # spaced caps rendered big, scaled later
    w=sum(font.getlength(c)+14 for c in s); im=Image.new('L',(int(w)+10,80),0); d=ImageDraw.Draw(im); x=5
    for c in s: d.text((x,5),c,fill=255,font=font); x+=font.getlength(c)+14
    return im.crop(im.getbbox())
t1=textimg('SMOKY POMEGRANATE'); t2=textimg('FINE FRAGRANCE')
for i in range(n):
    im=Image.open(f'fr/{i+1:04d}.png').convert('RGB'); a=np.array(im).astype(float)
    L,T,R,B=fit[i]; L=int(round(L))+5; R=int(round(R))-5; T=int(round(T))+5; B=int(round(B))-5
    reg=a[T:B,L:R]
    colm=np.median(reg,0)                      # (w,3) brushed streaks
    lum=reg.mean(2)/np.maximum(colm.mean(1),1)[None,:]
    rowr=np.median(lum,1); yy=np.arange(len(rowr))
    rowf=np.polyval(np.polyfit(yy,rowr,2),yy)
    clean=colm[None,:,:]*rowf[:,None,None]
    h,w=clean.shape[:2]
    # feather edges into original
    fy=np.minimum(np.minimum(yy,h-1-yy)/4,1); xx=np.arange(w); fx=np.minimum(np.minimum(xx,w-1-xx)/4,1)
    f=(fy[:,None]*fx[None,:])[...,None]
    a[T:B,L:R]=reg*(1-f)+clean*f
    out=Image.fromarray(np.clip(a,0,255).astype('uint8'))
    # overlay vector logo + label text (montage, not generated)
    W=(fit[i,2]-fit[i,0]); H=(fit[i,3]-fit[i,1]); cx=(fit[i,0]+fit[i,2])/2; y0=fit[i,1]
    S=4
    def paste(alpha, width, cy):
        hh=alpha.size[1]*width/alpha.size[0]
        al=alpha.resize((int(width*S),max(1,int(hh*S))),Image.LANCZOS).resize((int(round(width)),max(1,int(round(hh)))),Image.LANCZOS)
        al=al.filter(ImageFilter.GaussianBlur(0.4)).point(lambda v:int(v*0.9))
        col=Image.new('RGB',al.size,INK)
        out.paste(col,(int(round(cx-al.size[0]/2)),int(round(cy-al.size[1]/2))),al)
    paste(logo.split()[-1], W*0.80, y0+H*0.195)
    paste(t1, W*0.47, y0+H*0.815)
    paste(t2, W*0.38, y0+H*0.875)
    out.save(f'out/{i+1:04d}.png')
print('done')

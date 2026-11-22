import numpy as np, json
from PIL import Image
def mask(a):
    r,g,b=a[...,0],a[...,1],a[...,2]
    return (r>90)&(r-b>40)&(g-b>15)&(r-g<75)&(r-g>10)
def run(idx):
    best=(0,0);s=idx[0];p=idx[0]
    for v in list(idx[1:])+[10**9]:
        if v!=p+1:
            if p-s>best[1]-best[0]: best=(s,p)
            s=v
        p=v
    return best
L,T,R,B=476,390,716,610; res=[]
for i in range(1,122):
    a=np.array(Image.open(f'fr/{i:04d}.png').convert('RGB')).astype(int); m=mask(a)
    y0,y1=T+20,B-20; x0,x1=L-50,R+50
    cols=m[y0:y1,x0:x1].mean(0); xs=np.where(cols>0.6)[0]; bx=run(xs); nL,nR=x0+bx[0],x0+bx[1]
    ya,yb=T-50,B+50
    rows=m[ya:yb,nL+10:nR-10].mean(1); ys=np.where(rows>0.6)[0]; by=run(ys); nT,nB=ya+by[0],ya+by[1]
    L,T,R,B=nL,nT,nR,nB; res.append([int(L),int(T),int(R),int(B)])
json.dump(res,open('track.json','w'))
for i in range(0,121,15): print(i,res[i], res[i][2]-res[i][0], res[i][3]-res[i][1])

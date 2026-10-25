import cv2, numpy as np
# ---- spectrum: red cursor line should read 7.600 Hz
im = cv2.imread("img/crop_spec.jpg")
lines = np.load("img/spec_vlines.npy"); idx=[0,1,2,3,4,5,6,7,9,10]; grid={f:lines[i] for f,i in enumerate(idx)}
def xl(f,y): x0,y0,vx,vy=grid[f]; return x0+vx*(y-y0)/vy
def freq_at(x,y):
    xs=np.array([xl(f,y) for f in range(10)]); i=int(np.clip(np.searchsorted(xs,x)-1,0,8)); return i+(x-xs[i])/(xs[i+1]-xs[i])
b,g,r=[im[...,k].astype(float) for k in (0,1,2)]
red=((r-np.maximum(b,g))>18)
sub=np.zeros_like(red); sub[120:700,1380:1500]=True
ys,xs=np.nonzero(red&sub)
# fit x = a*y + c  (near-vertical line), robust by iterating
A=np.c_[ys,np.ones_like(ys)]; p=np.linalg.lstsq(A,xs,rcond=None)[0]
for _ in range(3):
    res=xs-A@p; keep=np.abs(res)<4; p=np.linalg.lstsq(A[keep],xs[keep],rcond=None)[0]
print("cursor line px:", keep.sum())
for y in (200,300,400,500,600,690):
    print("  row",y,"cursor reads f = %.4f Hz"%freq_at(p[0]*y+p[1],y))
fc=[freq_at(p[0]*y+p[1],y) for y in range(150,690,10)]
print("spectrum cursor: mean %.4f  std %.4f  (true 7.600) -> calibration error %+.4f Hz"%(np.mean(fc),np.std(fc),np.mean(fc)-7.6))

# ---- time plot: red cursor should read 2.188 s
imt = cv2.imread("img/crop_time.jpg"); Hm=np.load("img/time_H.npy")
b,g,r=[imt[...,k].astype(float) for k in (0,1,2)]
red=((r-np.maximum(b,g))>45)
ys,xs=np.nonzero(red[:,250:420]); xs=xs+250
sel=(ys>150)&(ys<1000)
pts=np.c_[xs[sel],ys[sel]].astype(np.float32)
# vertical cursor: x≈ a*y+c
A=np.c_[pts[:,1],np.ones(len(pts))]; p=np.linalg.lstsq(A,pts[:,0],rcond=None)[0]
for _ in range(3):
    res=pts[:,0]-A@p; keep=np.abs(res)<4; p=np.linalg.lstsq(A[keep],pts[keep,0],rcond=None)[0]
ts=[]
for y in range(200,1000,50):
    q=cv2.perspectiveTransform(np.array([[[p[0]*y+p[1],y]]],np.float32),Hm)[0,0]; ts.append(q[0])
print("time cursor: mean %.4f s  std %.4f (true 2.188) -> error %+.4f s"%(np.mean(ts),np.std(ts),np.mean(ts)-2.188))

import cv2, numpy as np
from digit_lines import find_grid

im, bw, vs, hs = find_grid("img/crop_spec.jpg", 0, 0, "spec")
H, W = im.shape[:2]
lines = np.load("img/spec_vlines.npy"); idx=[0,1,2,3,4,5,6,7,9,10]
V = {f: lines[i] for f,i in enumerate(idx)}      # f = 0..9 Hz
g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
kk = cv2.getStructuringElement(cv2.MORPH_RECT,(15,15))
bh = cv2.morphologyEx(cv2.GaussianBlur(g,(3,3),0), cv2.MORPH_BLACKHAT, kk).astype(float)
prof = bh[:, 130:200].mean(axis=1)
pk=[]
for y in range(5,H-5):
    if prof[y]==prof[y-3:y+4].max() and prof[y] > 0.25*prof.max():
        if not pk or y-pk[-1] > 20: pk.append(y)
print("left strip peaks:", pk)
def y_at(s, x): x1,y1,x2,y2,L=s; return y1+(y2-y1)*(x-x1)/(x2-x1)

rows = {1.6:170, 1.2:302, 0.8:434, 0.4:564, 0.0:691}
Hl = {}
for a_,yr in rows.items():
    cand=[s for s in hs if s[4]>600 and s[2]!=s[0] and abs(y_at(s,165)-yr)<16 and 0.01<(s[3]-s[1])/(s[2]-s[0])<0.05]
    pts=np.array([[s[0],s[1]] for s in cand]+[[s[2],s[3]] for s in cand],np.float32)
    vx,vy,x0,y0=cv2.fitLine(pts,cv2.DIST_L2,0,0.01,0.01).ravel(); Hl[a_]=(x0,y0,vx,vy)
    print("a=%.1f segs %d slope %.4f"%(a_,len(cand),vy/vx))
def inter(v,h):
    A=np.array([[v[2],-h[2]],[v[3],-h[3]]]); b=np.array([h[0]-v[0],h[1]-v[1]]); s=np.linalg.solve(A,b)
    return np.array([v[0]+v[2]*s[0], v[1]+v[3]*s[0]])
pix,world=[],[]
for f,v in V.items():
    for a,h in Hl.items(): pix.append(inter(v,h)); world.append([f,a])
pix=np.array(pix,np.float32); world=np.array(world,np.float32)
Hm,_=cv2.findHomography(pix,world,0)
res=cv2.perspectiveTransform(pix[None],Hm)[0]-world
print("homography residual RMS: f %.4f Hz, a %.4f m/s2"%(np.sqrt((res[:,0]**2).mean()),np.sqrt((res[:,1]**2).mean())))
np.save("img/spec_H.npy",Hm)
S_F,S_A=170.0,300.0   # px per Hz, px per m/s2
M=np.array([[S_F,0,60],[0,-S_A,1.7*S_A+30],[0,0,1]])
OW,OH=int(10*S_F+120),int(1.7*S_A+60)
rect=cv2.warpPerspective(im,M@Hm,(OW,OH),flags=cv2.INTER_LINEAR)
cv2.imwrite("img/spec_rect.jpg",rect)
b,gg,r=[rect[...,k].astype(float) for k in (0,1,2)]
gray=cv2.cvtColor(rect,cv2.COLOR_BGR2GRAY).astype(float)
redm=cv2.dilate(((r-np.maximum(b,gg))>10).astype(np.uint8),np.ones((5,5),np.uint8))>0
red=redm
dark=(gray<150)&~red
mask=np.zeros_like(dark)
for f in range(0,11):
    x=int(round(S_F*f+60)); mask[:,x-4:x+5]=True
for a in (0,0.4,0.8,1.2,1.6):
    y=int(round(-S_A*a+1.7*S_A+30)); mask[y-3:y+4,:]=True
y0=int(round(1.7*S_A+30))
freqs=np.arange(0,10.0001,0.05); amp=np.zeros(len(freqs))
redness=(r-np.maximum(b,gg))[:, 100:1200].mean(axis=1)
yred=int(np.argmax(redness[y0-int(1.4*S_A):y0-int(0.5*S_A)]))+y0-int(1.4*S_A)
print("red horizontal cursor at y=%d -> %.3f m/s2 (software cursor Y = 1.07)"%(yred,(y0-yred)/S_A))
mask[yred-5:yred+6,:]=True
curve=dark&~mask
ytop_lim=y0-int(1.25*S_A)
xc=60+S_F*7.619     # red cursor column (found in digit_check): neighbours used instead
for i,f in enumerate(freqs):
    x=int(round(S_F*f+60))
    if abs(x-xc)<5: x = int(xc-6) if x<=xc else int(xc+6)   # cursor-hidden bin: use the nearest clean column
    sub=curve[ytop_lim:y0-2, max(x-1,0):x+2].any(axis=1)
    rr=np.nonzero(sub)[0]
    if len(rr): amp[i]=max(0.0,(y0-(rr.min()+ytop_lim))/S_A)
pk=int(np.argmax(amp)); print("max digitized amp %.3f m/s2 at f=%.2f Hz (cursor reads 1.07 at 7.600)"%(amp[pk],freqs[pk]))
for f in (7.35,7.4,7.45,7.5,7.55,7.6,7.65,7.7,7.75,7.8,7.9): print("   f=%.2f  A=%.3f"%(f, amp[int(round(f/0.05))]))
np.save("img/spec_digit.npy",np.c_[freqs,amp])

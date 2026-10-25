import cv2, numpy as np
from digit_lines import find_grid

im, bw, vs, hs = find_grid("img/crop_time.jpg", 0, 0, "time")
H, W = im.shape[:2]
YREF = 300.0
def x_at(s, y):
    x1,y1,x2,y2,L = s; return x1 + (x2-x1)*(y-y1)/(y2-y1)
segs = sorted([s for s in vs if s[4] > 450 and s[3]!=s[1]], key=lambda s: x_at(s, YREF))
cl = []
for s in segs:
    xr = x_at(s, YREF)
    if cl and abs(xr-cl[-1][0]) < 30: cl[-1][1].append(s)
    else: cl.append([xr,[s]])
vlines = []
for xr, ss in cl:
    pts = np.array([[s[0],s[1]] for s in ss]+[[s[2],s[3]] for s in ss], np.float32)
    vx,vy,x0,y0 = cv2.fitLine(pts, cv2.DIST_L2,0,0.01,0.01).ravel()
    vlines.append((x0,y0,vx,vy))
xs = [l[0]+l[2]*(YREF-l[1])/l[3] for l in vlines]
print("vertical clusters", len(vlines)); print(np.round(xs,1)); print(np.round(np.diff(xs),1))

# horizontal lines from strip profiles (trace-free columns)
g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
k = cv2.getStructuringElement(cv2.MORPH_RECT,(15,15))
bh = cv2.morphologyEx(cv2.GaussianBlur(g,(3,3),0), cv2.MORPH_BLACKHAT, k).astype(float)
def strip_peaks(x0, x1):
    prof = bh[:, x0:x1].mean(axis=1)
    pk = [y for y in range(5,H-5) if prof[y]==prof[y-3:y+4].max() and prof[y] > 0.45*prof.max()*0.5]
    # merge near
    out = []
    for y in pk:
        if out and y-out[-1] < 20: continue
        out.append(y)
    return out, prof
pl, prof_l = strip_peaks(160, 215)
pr, prof_r = strip_peaks(1790, 1880)
print("left strip peaks:", pl); print("right strip peaks:", pr)
np.save("img/time_vlines.npy", np.array(vlines))

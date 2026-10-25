import cv2, numpy as np
from digit_lines import find_grid
im, bw, vs, hs = find_grid("img/crop_time.jpg", 0, 0, "time")
H, W = im.shape[:2]
vl = np.load("img/time_vlines.npy")
# keep t = 0,4,6,...,18  (clusters 0,5..12 of the 14 found)
t_of = {0:0, 5:4, 6:6, 7:8, 8:10, 9:12, 10:14, 11:16, 12:18}
V = {t: vl[i] for i,t in t_of.items()}
rows_left = [66,168,267,369,470,571,670,769,868,967,1064]
a_of = [20,16,12,8,4,0,-4,-8,-12,-16,-20]
def y_at(s, x):
    x1,y1,x2,y2,L = s; return y1 + (y2-y1)*(x-x1)/(x2-x1)
Hl = {}
# slope model from the well-behaved lines (a >= -12): slope varies linearly with a
sl_a = np.array([20,16,12,8,4,0,-4,-8,-12]); sl_v = np.array([0.0912,0.0871,0.0836,0.0791,0.0770,0.0737,0.0697,0.0653,0.0613])
pf = np.polyfit(sl_a, sl_v, 1)
for yr, a in zip(rows_left, a_of):
    pred = np.polyval(pf, a)
    cand = [s for s in hs if s[4] > 600 and s[2]!=s[0] and abs(y_at(s,190)-yr) < 14
            and abs((s[3]-s[1])/(s[2]-s[0]) - pred) < 0.012]
    if not cand: print("no segment for a=",a); continue
    pts = np.array([[s[0],s[1]] for s in cand]+[[s[2],s[3]] for s in cand], np.float32)
    vx,vy,x0,y0 = cv2.fitLine(pts, cv2.DIST_L2,0,0.01,0.01).ravel()
    Hl[a] = (x0,y0,vx,vy); print("a=%3d  segs %d  slope %.4f" % (a, len(cand), vy/vx))
def inter(v, h):
    # v: x = x0 + vx*s, y = y0 + vy*s ; h likewise ; solve
    A = np.array([[v[2], -h[2]],[v[3], -h[3]]]); b = np.array([h[0]-v[0], h[1]-v[1]])
    s = np.linalg.solve(A, b); return np.array([v[0]+v[2]*s[0], v[1]+v[3]*s[0]])
pix, world = [], []
for t,v in V.items():
    for a,h in Hl.items():
        pix.append(inter(v,h)); world.append([t,a])
pix = np.array(pix, np.float32); world = np.array(world, np.float32)
Hm, _ = cv2.findHomography(pix, world, 0)
proj = cv2.perspectiveTransform(pix[None], Hm)[0]
res = proj - world
print("homography residual RMS: t %.4f s, a %.4f m/s2" % (np.sqrt((res[:,0]**2).mean()), np.sqrt((res[:,1]**2).mean())))
np.save("img/time_H.npy", Hm)
# rectified view for inspection
S_T, S_A = 80.0, 20.0     # px per s, px per m/s2
M = np.array([[S_T,0,60],[0,-S_A,20*S_A+30],[0,0,1]])
warp = cv2.warpPerspective(im, M @ Hm, (int(20*S_T+120), int(40*S_A+60)))
cv2.imwrite("img/time_rect.jpg", warp)

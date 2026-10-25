import cv2, numpy as np
im = cv2.imread("img/crop_time.jpg"); Hm = np.load("img/time_H.npy")
S_T, S_A = 80.0, 20.0
M = np.array([[S_T,0,60],[0,-S_A,20*S_A+30],[0,0,1]])
Wd, Hd = int(20*S_T+120), int(40*S_A+60)
rect = cv2.warpPerspective(im, M @ Hm, (Wd, Hd), flags=cv2.INTER_LINEAR)
g = cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY).astype(float)
b,gc,r = [rect[...,k].astype(float) for k in (0,1,2)]
red = (r - np.maximum(b,gc)) > 35
dark = (g < 120) & ~red
# mask grid lines and axes
mask = np.zeros_like(dark)
for t in range(0,21,2):
    x = int(round(S_T*t+60)); mask[:, x-3:x+4] = True
for a in range(-20,21,4):
    y = int(round(-S_A*a + 20*S_A+30)); mask[y-2:y+3, :] = True
mask[:40,:]=True; mask[-45:,:]=True; mask[:, :60]=True; mask[:, 60+int(S_T*20):] = True
tr = dark & ~mask
# remove leftovers of horizontal grid lines (long horizontal runs); the trace itself is made of steep strokes
hor = cv2.morphologyEx(tr.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT,(31,1)))
hor = cv2.dilate(hor, np.ones((5,1),np.uint8)) > 0
tr = tr & ~hor
ys, xs = np.nonzero(tr)
print("trace pixels:", len(xs))
t_all = (xs-60)/S_T; a_all = (20*S_A+30-ys)/S_A
# per-column extremes
cols = np.arange(60, 60+int(S_T*20))
up = np.full(len(cols), np.nan); lo = up.copy()
for i,c in enumerate(cols):
    sel = xs==c
    if sel.sum()>=1:
        up[i] = a_all[sel].max(); lo[i] = a_all[sel].min()
t = (cols-60)/S_T
# sliding envelope (0.4 s ~ 3 cycles): amplitude = (max - min)/2 over window
win = int(0.4*S_T)
amp = np.full(len(t), np.nan); mid = amp.copy()
for i in range(len(t)):
    j0, j1 = max(0,i-win//2), min(len(t), i+win//2+1)
    u, l = np.nanmax(up[j0:j1]) if np.isfinite(up[j0:j1]).any() else np.nan, np.nanmin(lo[j0:j1]) if np.isfinite(lo[j0:j1]).any() else np.nan
    amp[i] = (u-l)/2; mid[i] = (u+l)/2
np.savetxt("img/envelope_acc_clean.csv", np.c_[t, up, lo, amp], delimiter=",", header="t_s,upper_ms2,lower_ms2,half_p2p_ms2", comments="")
def fit(t0,t1):
    sel = (t>=t0)&(t<=t1)&np.isfinite(amp)&(amp>0.3)
    p = np.polyfit(t[sel], np.log(amp[sel]), 1)
    sigma = -p[0]; A0 = np.exp(p[1])
    # R2
    res = np.log(amp[sel]) - np.polyval(p, t[sel]); r2 = 1 - res.var()/np.log(amp[sel]).var()
    return sigma, A0, r2, sel.sum()
f_n = 7.62
for (t0,t1) in [(2.0,8.0),(2.5,9.0),(3.0,10.0),(2.2,7.0),(3.5,9.0)]:
    s_,A0,r2,n = fit(t0,t1)
    print(f"fit {t0}-{t1}s: sigma={s_:.3f} 1/s  zeta={s_/(2*np.pi*f_n):.4f}  A0={A0:.1f} m/s2  R2={r2:.3f} n={n}")
print("peak amplitude and onset:", np.nanmax(amp), t[np.nanargmax(amp)])
# onset detect
on = t[np.nonzero(np.nan_to_num(amp)>2.0)[0][0]]
print("onset (amp>2 m/s2) at t = %.2f s" % on)
dbg = rect.copy(); dbg[tr] = (0,255,0); cv2.imwrite("img/time_rect_trace.jpg", dbg)

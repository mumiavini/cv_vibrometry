import cv2, numpy as np
im = cv2.imread("img/crop_spec.jpg")
lines = np.load("img/spec_vlines.npy")
order = [0,1,2,3,4,5,6,7,9,10]       # indices of clusters that are the 0..9 Hz gridlines
L = lines[[0,1,2,3,4,5,6,7,9,10]] if False else None
# rebuild the clusters 0..9 Hz (skip cluster 8 = peak edge)
idx = [0,1,2,3,4,5,6,7,9,10]
grid = {f: lines[i] for f, i in enumerate(idx)}
def xl(f, y):
    x0,y0,vx,vy = grid[f]; return x0 + vx*(y-y0)/vy

def freq_at(x, y):
    # find the bracketing gridlines along this row, interpolate linearly
    xs = np.array([xl(f, y) for f in range(10)])
    i = int(np.clip(np.searchsorted(xs, x) - 1, 0, 8))
    return i + (x - xs[i])/(xs[i+1]-xs[i])

# --- curve pixels: dark, not red, not near grid lines
g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(float)
b,gc,r = [im[...,k].astype(float) for k in (0,1,2)]
red = (r - np.maximum(b,gc)) > 40
dark = g < 150
H, W = g.shape
mask = np.zeros((H,W), bool)
yy = np.arange(H)
near = np.zeros((H,W), bool)
for f in range(10):
    x0,y0,vx,vy = grid[f]
    xline = x0 + vx*(yy-y0)/vy
    d = np.abs(np.arange(W)[None,:] - xline[:,None])
    near |= d < 7
# horizontal gridlines/axis: exclude via local row-run test (long horizontal dark runs) – simple: ignore rows near known y by morphological opening
k = cv2.getStructuringElement(cv2.MORPH_RECT, (41,1))
hor = cv2.morphologyEx((dark).astype(np.uint8), cv2.MORPH_OPEN, k) > 0
hor = cv2.dilate(hor.astype(np.uint8), np.ones((5,1),np.uint8)) > 0
curve = dark & ~red & ~near & ~hor
# restrict to window around the peak
win = np.zeros_like(curve); win[380:705, 1330:1560] = True
cv = curve & win
ys, xs_ = np.nonzero(cv)
print("curve pixels in window:", len(ys))
# apex = topmost cluster of curve pixels
ymin = ys.min()
top = ys <= ymin+3
xa = xs_[top].mean(); ya = ys[top].mean()
print("apex px:", xa, ya, " f_apex = %.4f Hz" % freq_at(xa, ya))
# curve centroid of top 20 % (sub-bin estimate)
cut = ymin + 0.25*(ys.max()-ymin)
sel = ys <= cut
print("centroid of upper 25%% of peak: f = %.4f Hz" % np.mean([freq_at(x, y) for x,y in zip(xs_[sel], ys[sel])]))
# peak spread: freq at several heights (left/right flanks) => symmetric centre
for frac in (0.1,0.2,0.3,0.4,0.5):
    yl = ymin + frac*(ys.max()-ymin)
    row = xs_[np.abs(ys-yl)<2]
    if len(row)>1:
        fl, fr = freq_at(row.min(), yl), freq_at(row.max(), yl)
        print(f" height {frac:.1f}: left {fl:.3f} right {fr:.3f}  centre {(fl+fr)/2:.3f}  width {fr-fl:.3f} Hz")
dbg = im.copy(); dbg[cv] = (0,255,0)
cv2.circle(dbg,(int(xa),int(ya)),8,(255,0,255),2)
cv2.imwrite("img/dbg_spec_peak.jpg", dbg[250:760,1250:1620])

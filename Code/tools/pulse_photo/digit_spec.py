import cv2, numpy as np
from digit_lines import find_grid

im, bw, vs, hs = find_grid("img/crop_spec.jpg", 0, 0, "spec")
H, W = im.shape[:2]
YREF = 450.0

def x_at(seg, y):
    x1,y1,x2,y2,L = seg
    return x1 + (x2-x1)*(y-y1)/(y2-y1) if y2!=y1 else None

# cluster long near-vertical segments by x at YREF
segs = [s for s in vs if s[4] > 450]
segs.sort(key=lambda s: x_at(s, YREF))
clusters = []
for s in segs:
    xr = x_at(s, YREF)
    if clusters and abs(xr - clusters[-1][0]) < 30: clusters[-1][1].append(s)
    else: clusters.append([xr, [s]])
lines = []
for xr, ss in clusters:
    pts = np.array([[s[0],s[1]] for s in ss] + [[s[2],s[3]] for s in ss], np.float32)
    vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
    lines.append((x0, y0, vx, vy))
xs = [l[0] + l[2]*(YREF-l[1])/l[3] for l in lines]
print("n vertical clusters:", len(lines)); print(np.round(xs,1)); print("spacing", np.round(np.diff(xs),1))
np.save("img/spec_vlines.npy", np.array(lines))

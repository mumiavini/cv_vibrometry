import cv2, numpy as np, sys, json

def find_grid(path, expect_v, expect_h, name):
    im = cv2.imread(path)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3,3), 0)
    # dark thin lines: black top-hat
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (15,15))
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k)
    _, bw = cv2.threshold(bh, 25, 255, cv2.THRESH_BINARY)
    H, W = g.shape
    lines = cv2.HoughLinesP(bw, 1, np.pi/720, threshold=200, minLineLength=int(0.35*min(H,W)), maxLineGap=25)
    vs, hs = [], []
    for x1,y1,x2,y2 in lines.reshape(-1,4):
        ang = np.degrees(np.arctan2(y2-y1, x2-x1))
        L = np.hypot(x2-x1, y2-y1)
        if abs(abs(ang)-90) < 12: vs.append((x1,y1,x2,y2,L))
        elif abs(ang) < 12 or abs(abs(ang)-180) < 12: hs.append((x1,y1,x2,y2,L))
    print(name, "segments v/h:", len(vs), len(hs))
    return im, bw, vs, hs

if __name__ == "__main__":
    for path, name in (("img/crop_spec.jpg","spec"),("img/crop_time.jpg","time")):
        im, bw, vs, hs = find_grid(path, 0, 0, name)
        dbg = im.copy()
        for x1,y1,x2,y2,L in vs: cv2.line(dbg,(x1,y1),(x2,y2),(0,0,255),2)
        for x1,y1,x2,y2,L in hs: cv2.line(dbg,(x1,y1),(x2,y2),(255,0,0),2)
        cv2.imwrite(f"img/dbg_{name}.jpg", dbg)
        cv2.imwrite(f"img/bw_{name}.jpg", bw)

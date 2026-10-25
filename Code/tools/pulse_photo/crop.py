import cv2
im = cv2.imread("img/215b78e0-Curva_acelerometro_full.jpg")
print(im.shape)
cv2.imwrite("img/crop_time.jpg", im[1080:2300, 1780:3760])
cv2.imwrite("img/crop_spec.jpg", im[2380:3200, 1750:3700])

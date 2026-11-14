"""Find the cloud folder ID text (template from a known frame) in every frame and blur it.
usage: blur_id.py <in.mp4> <template_frame.png> <out_noaudio.mp4> [--scan]
"""
import sys
import cv2
import numpy as np

src, tpl_frame, out = sys.argv[1], sys.argv[2], sys.argv[3]
scan_only = "--scan" in sys.argv
X0, Y0, X1, Y1 = 530, 584, 700, 604  # "gpt://<folder-id>" in template frame
TH = 0.75

def binar(gray):
    return (gray > 110).astype(np.uint8) * 255

tf = cv2.imread(tpl_frame, cv2.IMREAD_GRAYSCALE)
tpl = binar(tf[Y0:Y1, X0:X1])
th, tw = tpl.shape

cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
wr = None if scan_only else cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
i = hits_frames = 0
prev = []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    g = binar(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
    res = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(res >= TH)
    boxes = []
    for y, x in zip(ys, xs):
        if not any(abs(y - by) < th and abs(x - bx) < tw for by, bx in boxes):
            boxes.append((y, x))
    # keep last boxes for 2 frames to cover scroll blur between frames
    use = boxes + [b for b in prev if b not in boxes]
    if boxes:
        hits_frames += 1
        if i % 30 == 0 or not prev:
            print(f"t={i / fps:7.2f}s hits={len(boxes)} max={res.max():.2f}", flush=True)
    if wr is not None:
        for y, x in use:
            ya, yb = max(0, y - 4), min(h, y + th + 4)
            xa, xb = max(0, x - 4), min(w, x + tw + 6)
            fr[ya:yb, xa:xb] = cv2.GaussianBlur(fr[ya:yb, xa:xb], (31, 31), 0)
        wr.write(fr)
    prev = boxes
    i += 1
cap.release()
if wr is not None:
    wr.release()
print(f"frames={i} frames_with_id={hits_frames}")

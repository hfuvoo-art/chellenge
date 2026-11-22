# Синтез фоновой музыки для ролика Smoky Pomegranate (70 с).
# Лад шур (ре): дрон виолончели, щипковая «тар»-линия (Karplus-Strong),
# смычковая «кяманча» в середине, редкие ноты фортепиано, ревербер.
import numpy as np, wave, sys
SR = 44100; DUR = 70.0; N = int(SR * DUR)
rng = np.random.default_rng(7)
t = np.arange(N) / SR
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
D2, A2, D3 = 38, 45, 50
L = np.zeros(N); R = np.zeros(N)
def add(sig, start, pan=0.0, gain=1.0):
    i = int(start * SR); j = min(N, i + len(sig)); s = sig[: j - i] * gain
    L[i:j] += s * np.sqrt((1 - pan) / 2); R[i:j] += s * np.sqrt((1 + pan) / 2)
# 1. Дрон виолончели
def bowed(f, dur, vib=0.004, bright=1.6, nh=12):
    n = int(dur * SR); tt = np.arange(n) / SR
    ph = 2 * np.pi * f * (tt + vib / (2 * np.pi * 5.1) * np.sin(2 * np.pi * 5.1 * tt))
    s = sum(np.sin(k * ph + k) / k ** bright for k in range(1, nh + 1))
    s *= 1 + 0.05 * np.sin(2 * np.pi * 0.21 * tt)
    return s
drone = bowed(hz(D2), DUR, vib=0.002, bright=1.8) * 0.5 + bowed(hz(A2), DUR, vib=0.002, bright=2.0) * 0.3
env = np.clip(t / 5, 0, 1) * (0.7 + 0.3 * np.exp(-((t - 38) / 9) ** 2))
add(drone * env, 0, 0, 0.22)
# 2. Тар: Karplus-Strong
def pluck(f, dur=2.5, decay=0.996):
    n = int(dur * SR); p = int(SR / f)
    y = np.zeros(n); y[:p] = rng.uniform(-1, 1, p)
    for i in range(p, n, p):
        seg = y[i - p:i]; nxt = 0.5 * (seg + np.roll(seg, 1)) * decay
        y[i:i + p] = nxt[: len(y[i:i + p])]
    y *= np.exp(-np.arange(n) / SR * 1.2)
    return y
shur = [62, 63, 65, 67, 69, 70, 72, 74]  # D Eb F G A Bb C D
phrases = [
    (6.0, [69, 67, 65, 63, 62]), (13.0, [62, 63, 65, 63, 62]),
    (21.0, [65, 67, 69, 70, 69, 67]), (44.0, [74, 72, 70, 69, 67, 65, 63, 62]),
    (54.0, [69, 67, 65, 63, 62]),
]
for start, notes in phrases:
    tm = start
    for k, m in enumerate(notes):
        add(pluck(hz(m)), tm, -0.3, 0.32)
        if k % 2 == 0: add(pluck(hz(m)) * 0.5, tm + 0.12, -0.3, 0.12)  # тремоло-повтор
        tm += 0.55 if k < len(notes) - 1 else 0
# 3. Кяманча: смычковая мелодия на подъёме
kam = [(29.0, 69, 3.0), (32.0, 70, 2.0), (34.0, 72, 4.5), (38.5, 70, 2.0), (40.5, 69, 4.0)]
for st, m, d in kam:
    s = bowed(hz(m), d, vib=0.012, bright=1.3, nh=10)
    n = len(s); a = np.minimum(np.arange(n) / (0.5 * SR), 1) * np.minimum((n - np.arange(n)) / (0.8 * SR), 1)
    add(s * a, st, 0.35, 0.10)
# 4. Фортепиано, редкие ноты
def piano(f, dur=4.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * k * tt * (1 + 0.0004 * k * k)) * np.exp(-tt * (0.8 + 0.6 * k)) / k for k in range(1, 7))
    return s * np.minimum(tt / 0.005, 1)
for st, m in [(10, 74), (17, 70), (25, 69), (36, 77), (47, 74), (58, 62), (61, 69)]:
    add(piano(hz(m)), st, 0.2, 0.22)
# Ревербер: свёртка с затухающим шумом
def reverb(x, sec=2.8):
    n = int(sec * SR); ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / SR * 2.4); ir[0] = 0
    m = 1 << int(np.ceil(np.log2(len(x) + n)))
    y = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)]
    return y / np.max(np.abs(y)) * np.max(np.abs(x))
L = 0.7 * L + 0.45 * reverb(L); R = 0.7 * R + 0.45 * reverb(R)
master = np.clip(t / 2, 0, 1) * np.where(t < 58, 1, np.clip((65 - t) / 7, 0, 1))
L *= master; R *= master
pk = max(np.abs(L).max(), np.abs(R).max()); L /= pk / 0.8; R /= pk / 0.8
out = (np.stack([L, R], 1) * 32767).astype(np.int16)
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())

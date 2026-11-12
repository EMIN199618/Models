"""Luxury cinematic score (piano + strings + soft pulse) synced to the v2 timeline."""
import numpy as np, wave, sys

SR = 48000; DUR = 30.0; N = int(SR * DUR)
rng = np.random.default_rng(7)
L = np.zeros(N); R = np.zeros(N); send = np.zeros(N)
BEAT = .5
ta = lambda n: np.arange(n) / SR
midi = lambda m: 440 * 2 ** ((m - 69) / 12)


def place(sig, at, gain=1., pan=0., rev=0.):
    i = int(at * SR)
    if i >= N or i + len(sig) <= 0: return
    s = sig[: N - i] * gain
    l, r = np.cos((pan + 1) * np.pi / 4) * 1.414, np.sin((pan + 1) * np.pi / 4) * 1.414
    L[i:i + len(s)] += s * l; R[i:i + len(s)] += s * r; send[i:i + len(s)] += s * rev


def filt(x, lo=None, hi=None, order=2):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); Hh = np.ones_like(f)
    if hi: Hh *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo: Hh *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * Hh, len(x))


# ---------- instruments ----------
def piano(m, dur=2.5, vel=.8):
    f0 = midi(m); n = int((dur + 1.2) * SR); t = ta(n); s = np.zeros(n)
    B = .00025; bright = .6 + .5 * vel
    for k in range(1, 14):
        fk = k * f0 * np.sqrt(1 + B * k * k)
        if fk > 16000: break
        a = (1 / k ** 1.15) * (bright ** (k - 1) if k > 1 else 1)
        d = .55 + .35 * k + f0 / 900
        for det in (-.0004, .0004):
            s += a * np.sin(2 * np.pi * fk * (1 + det) * t + rng.random() * 6.28) * np.exp(-t * d) * .5
    s += filt(rng.standard_normal(n), lo=200, hi=min(9000, f0 * 9)) * np.exp(-t * 90) * .08 * vel
    att = np.minimum(1, t / .003); rel = np.clip(1 - (t - dur) / .35, 0, 1)
    return s * att * rel * vel * .5


def strings(ms, dur, att=.9, rel=1.2, bright=2400):
    n = int((dur + rel) * SR); t = ta(n); s = np.zeros(n)
    for m in ms:
        f = midi(m)
        for v in range(6):
            det = (rng.random() - .5) * .009; ph = rng.random()
            vib = 1 + .0025 * np.sin(2 * np.pi * (4.8 + rng.random()) * t + rng.random() * 6)
            s += (2 * ((np.cumsum(f * (1 + det) * vib) / SR + ph) % 1) - 1) / 6
    s = filt(s, lo=120, hi=bright, order=2)
    e = np.minimum(1, t / att) * np.clip(1 - (t - dur) / rel, 0, 1)
    return s * e * .12


def sub_pulse():
    n = int(.6 * SR); t = ta(n)
    f = 42 + 60 * np.exp(-t * 22)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 1.4)


def shaker():
    n = int(.08 * SR); t = ta(n); return filt(rng.standard_normal(n), lo=5000, hi=12000) * np.exp(-t * 55)


def rim():
    n = int(.12 * SR); t = ta(n); return (np.sin(2 * np.pi * 1700 * t) * .5 + filt(rng.standard_normal(n), lo=1500, hi=6000)) * np.exp(-t * 60)


def tom(f=90):
    n = int(.7 * SR); t = ta(n); ff = f * (1 + .6 * np.exp(-t * 18))
    return np.tanh(np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t * 7) * 1.5 + filt(rng.standard_normal(n), hi=2000) * np.exp(-t * 30) * .3)


def boom(dur=4.):
    n = int(dur * SR); t = ta(n)
    b = np.sin(2 * np.pi * np.cumsum(32 + 55 * np.exp(-t * 5)) / SR) * np.exp(-t * 1.3)
    c = filt(rng.standard_normal(n), lo=2500, hi=12000) * np.exp(-t * 2.2) * .18
    return np.tanh((b + c) * 1.3)


def swell(dur, f0=300, f1=6000, rev_=False):
    n = int(dur * SR); t = ta(n); p = t / dur; nz = rng.standard_normal(n); out = np.zeros(n); blk = 2048
    for b in range(0, n, blk):
        fc = f0 * (f1 / f0) ** (b / n); seg = nz[b:b + blk]
        out[b:b + blk] = filt(np.pad(seg, (0, blk - len(seg))), lo=fc * .5, hi=fc * 1.5)[: len(seg)]
    e = p ** 2.2
    return out * e


def whoosh(dur=.8):
    n = int(dur * SR); p = ta(n) / dur; nz = rng.standard_normal(n); out = np.zeros(n); blk = 1024
    for b in range(0, n, blk):
        fc = 300 + 3500 * np.sin(np.pi * b / n); seg = nz[b:b + blk]
        out[b:b + blk] = filt(np.pad(seg, (0, blk - len(seg))), lo=fc * .4, hi=fc * 1.6)[: len(seg)]
    return out * np.sin(np.pi * p) ** 2


def chime(f=2093, dur=1.6):
    n = int(dur * SR); t = ta(n)
    return sum(np.sin(2 * np.pi * f * h * t) * np.exp(-t * (2.5 + h)) / h for h in (1, 2.76, 5.4)) * .5


def click(f=3000):
    n = int(.03 * SR); t = ta(n); return (np.sin(2 * np.pi * f * t) * .5 + filt(rng.standard_normal(n), lo=2500) * .4) * np.exp(-t * 200)


# ---------- harmony ----------
# Fmaj7 | Em7 | Dm9 | Cmaj7   (2 s per chord)
CH = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60, 64], [48, 52, 55, 59]]
ROOT = [41, 40, 38, 36]
MEL = {0.0: 76, 1.0: 72, 2.5: 74, 3.5: 71, 4.0: 72, 6.0: 79, 7.0: 76, 8.0: 77, 9.0: 74, 10.0: 76, 11.0: 72,
       12.5: 84, 13.5: 81, 14.5: 79, 15.5: 77, 16.0: 76, 26.0: 84}

for bar in range(15):
    t0 = bar * 2.0; c = CH[bar % 4]
    sec = 'intro' if t0 < 5 else 'tour' if t0 < 12.5 else 'lib' if t0 < 17 else 'web' if t0 < 22 else 'build' if t0 < 26 else 'end'
    # piano
    if sec in ('intro', 'lib'):
        for i, m in enumerate(c): place(piano(m, 1.9, .55), t0 + i * .06, .9, pan=-.3 + i * .2, rev=.6)
    elif sec in ('tour', 'web'):
        pat = c + [c[1] + 12, c[2] + 12, c[0] + 12, c[2]]
        step = BEAT / 2 if sec == 'web' else BEAT / 2
        for k in range(8):
            place(piano(pat[k % len(pat)], .5, .45 + .1 * (k % 2 == 0)), t0 + k * step, .75, pan=-.4 + (k % 4) * .25, rev=.5)
        place(piano(c[0] - 12, 1.9, .55), t0, .8, rev=.4)
    elif sec == 'build':
        for k in range(16):
            place(piano(c[k % len(c)] + 12, .25, .35 + k * .025), t0 + k * BEAT / 4, .7, pan=-.4 + (k % 4) * .25, rev=.4)
    # strings
    if sec != 'end':
        gain = {'intro': .7, 'tour': .8, 'lib': 1.1, 'web': .6, 'build': 1.0}[sec]
        br = {'intro': 1600, 'tour': 2200, 'lib': 3200, 'web': 2000, 'build': 2800 + (t0 - 22) * 600}[sec]
        place(strings([m + 12 for m in c] + [ROOT[bar % 4]], 2.0, att=.8, rel=1.0, bright=br), t0, gain, rev=.5)
    # bass
    if sec in ('tour', 'web', 'build'):
        n = int(2.0 * SR); tt = ta(n); f = midi(ROOT[bar % 4])
        b = (np.sin(2 * np.pi * f * tt) + .3 * np.sin(2 * np.pi * 2 * f * tt)) * np.minimum(1, tt / .02) * np.clip(1 - (tt - 1.8) / .2, 0, 1)
        place(b, t0, .22)

for at, m in MEL.items():
    if at < 26: place(piano(m, 1.2, .7), at, .85, pan=.15, rev=.7)

# ---------- rhythm ----------
SP, SH, RM = sub_pulse(), shaker(), rim()
for b in np.arange(5.0, 12.5, BEAT):
    place(SP, b, .55 if (b * 2) % 2 == 0 else .3)
    place(SH, b + .25, .08, pan=.35); place(SH, b + .125, .04, pan=-.35); place(SH, b + .375, .04, pan=-.35)
for b in np.arange(17.0, 22.0, BEAT):
    place(SP, b, .5 if (b * 2) % 2 == 0 else .28); place(SH, b + .25, .08, pan=.3)
    if round(b * 2) % 4 == 2: place(RM, b, .18, pan=.2, rev=.3)
for i, b in enumerate(np.arange(22.0, 26.0, BEAT / 2)):
    place(tom(70 + (i % 4) * 8), b, .18 + i * .018, pan=-.3 + (i % 3) * .3, rev=.25)
    if i % 2 == 0: place(SP, b, .4)

# ---------- final chord ----------
fin = [36, 48, 55, 60, 64, 67, 71]
for i, m in enumerate(fin): place(piano(m, 3.6, .75), 26.0 + i * .02, .9, pan=-.4 + i * .13, rev=.8)
place(strings([60, 64, 67, 71, 76], 3.0, att=.15, rel=1.0, bright=3500), 26.0, 1.3, rev=.6)
place(piano(84, 2.5, .6), 27.5, .6, rev=.9); place(piano(79, 2.0, .5), 28.2, .5, rev=.9)

# ---------- SFX ----------
place(swell(4.6, 200, 5000), .4, .22, rev=.5)
place(whoosh(1.2), 4.2, .35, pan=-.2, rev=.4)
place(swell(1.4, 300, 7000), 11.1, .3, rev=.4); place(boom(4.5), 12.5, .65, rev=.5)
place(whoosh(1.0), 16.5, .35, pan=.2, rev=.4)
place(whoosh(.9), 21.6, .32, pan=-.2, rev=.4)
place(swell(3.8, 150, 8000), 22.2, .3, rev=.4)
place(boom(4.5), 26.0, .75, rev=.6)
for at in (5.6, 8.3, 10.7): place(chime(2093 if at < 8 else 2349 if at < 10 else 2637), at, .1, pan=.3, rev=.7)
for i in range(6): place(chime(1568 + i * 120, 1.0), 13.2 + i * .18, .05, pan=-.5 + i * .2, rev=.7)
for i in range(len('barrel lounge chair')): place(click(2400 + (i % 3) * 300), 17.6 + i * 1.0 / 19, .14, pan=.1)
place(click(1600), 19.45, .35); place(click(1600), 20.7, .35)
place(chime(1318.5, 1.4), 21.5, .14, rev=.5); place(chime(1975.5, 1.2), 21.6, .12, rev=.5)

# ---------- reverb ----------
irn = int(3.4 * SR); it = ta(irn)
ir = filt(rng.standard_normal(irn) * np.exp(-it * 1.9), hi=7000); ir2 = np.roll(ir, 53) * .97
nf = 1 << int(np.ceil(np.log2(N + irn)))
Sx = np.fft.rfft(send, nf)
L += np.fft.irfft(Sx * np.fft.rfft(ir, nf), nf)[:N] * .06
R += np.fft.irfft(Sx * np.fft.rfft(ir2, nf), nf)[:N] * .06

# ---------- master ----------
m = np.stack([L, R], 1)
fade = np.ones(N); fo = int(1.2 * SR); fade[-fo:] = np.linspace(1, 0, fo) ** 2; fade[:int(.03 * SR)] = np.linspace(0, 1, int(.03 * SR))
m *= fade[:, None]
m = filt(m[:, 0], lo=28)[:, None] * [1, 0] + filt(m[:, 1], lo=28)[:, None] * [0, 1]
m = np.tanh(m / np.max(np.abs(m)) * 1.5); m /= np.max(np.abs(m)) / .93
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'music2.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((m * 32767).astype('<i2').tobytes())
print('ok')

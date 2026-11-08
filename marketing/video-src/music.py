"""Synthesize a 30 s cinematic electronic track + SFX synced to the video timeline."""
import numpy as np, wave, sys

SR = 48000
DUR = 30.0
N = int(SR * DUR)
rng = np.random.default_rng(42)
BPM = 120
BEAT = 60 / BPM

L = np.zeros(N); R = np.zeros(N)
send = np.zeros(N)  # mono reverb send


def t_arr(n):
    return np.arange(n) / SR


def place(sig, at, gain=1.0, pan=0.0, rev=0.0):
    i = int(at * SR)
    if i >= N: return
    s = sig[: N - i] * gain
    l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
    L[i:i + len(s)] += s * l * 1.414; R[i:i + len(s)] += s * r * 1.414
    send[i:i + len(s)] += s * rev


def fft_filter(x, lo=None, hi=None, order=2):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); H = np.ones_like(f)
    if hi: H *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo: H *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * H, len(x))


def env_adsr(n, a, d, s, r, sustain_len):
    e = np.zeros(n); A, D, Rr = int(a * SR), int(d * SR), int(r * SR); S = int(sustain_len * SR)
    k = 0
    seg = np.linspace(0, 1, max(A, 1)); e[k:k + len(seg)] = seg[: n - k]; k += len(seg)
    if k < n: seg = np.linspace(1, s, max(D, 1)); e[k:k + len(seg)] = seg[: n - k]; k += len(seg)
    if k < n: e[k:k + S] = s; k += S
    if k < n: seg = np.linspace(s, 0, max(Rr, 1)); e[k:k + len(seg)] = seg[: n - k]
    return e


def saw(freq, n, detune=0.0):
    t = t_arr(n); ph = (t * freq * (1 + detune)) % 1.0
    return 2 * ph - 1


# ---------------- drums ----------------
def kick():
    n = int(.45 * SR); t = t_arr(n)
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 7.5)
    s += fft_filter(rng.standard_normal(n), lo=2000) * np.exp(-t * 300) * .3
    return np.tanh(s * 1.6)


def snare():
    n = int(.35 * SR); t = t_arr(n)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * .5
    nz = fft_filter(rng.standard_normal(n), lo=1200, hi=9000) * np.exp(-t * 16)
    return body + nz * .8


def hat(open_=False):
    n = int((.25 if open_ else .06) * SR); t = t_arr(n)
    return fft_filter(rng.standard_normal(n), lo=7000) * np.exp(-t * (14 if open_ else 70))


K, S, HH, OH = kick(), snare(), hat(), hat(True)

def drum_section(t0, t1, snare_on=True, hats=True):
    b = t0
    while b < t1 - 1e-6:
        place(K, b, .95)
        beat_idx = round((b - 0) / BEAT)
        if snare_on and beat_idx % 2 == 1: place(S, b, .45, rev=.25)
        if hats:
            place(HH, b + BEAT / 2, .22, pan=.3)
            place(HH, b + BEAT / 4, .08, pan=-.3); place(HH, b + 3 * BEAT / 4, .08, pan=-.3)
        b += BEAT

drum_section(3.0, 19.0)
drum_section(23.0, 26.0)
# S5: punchy half-time hits on the feature cuts
for at in (19.0, 20.33, 21.66):
    place(K, at, 1.0); place(S, at, .5, rev=.4)
for at in np.arange(19.0, 23.0, BEAT / 2): place(HH, at + BEAT / 4, .12, pan=.2)
# snare roll into 23 & 26
for i, at in enumerate(np.arange(22.0, 23.0, BEAT / 4)): place(S, at, .12 + i * .04, rev=.2)
for i, at in enumerate(np.arange(25.0, 26.0, BEAT / 4)): place(S, at, .12 + i * .045, rev=.2)

# ---------------- harmony ----------------
# Am - F - C - G (one bar = 2 s)
chords = [[57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62]]
roots = [45, 41, 48, 43]
midi = lambda m: 440 * 2 ** ((m - 69) / 12)

# pad (whole track)
pad = np.zeros(N)
for bar in range(15):
    c = chords[bar % 4]; n = int(2.0 * SR) + int(.6 * SR)
    s = np.zeros(n)
    for m in c:
        for d in (-.004, .0, .005):
            s += saw(midi(m), n, d)
    s = fft_filter(s, hi=1400 if 3 <= bar * 2 < 26 else 900) * env_adsr(n, .4, .2, .8, .6, 1.4)
    i = int(bar * 2.0 * SR); pad[i:i + n] += s[: N - i] * .05
# volume automation: big in intro & outro, softer under drums
auto = np.interp(t_arr(N), [0, 2.8, 3.0, 19, 19.5, 23, 26, 27, 29.3, 30], [.0, 1.1, .55, .55, .8, .5, 1.2, 1.0, .5, 0])
pad *= auto
# bass (8ths, 3-19 & 23-26)
bass = np.zeros(N)
for bar in range(15):
    st = bar * 2.0
    if not (3 <= st < 19 or 23 <= st < 26 or (2.0 <= st < 3)): continue
    for k in range(8):
        at = st + k * BEAT / 2
        if not (3 <= at < 19 or 23 <= at < 26): continue
        n = int(BEAT / 2 * SR * .9); f = midi(roots[bar % 4] - (0 if k % 4 else 12) + 12)
        s = saw(f, n) + .5 * np.sin(2 * np.pi * f / 2 * t_arr(n))
        s = fft_filter(s, hi=520) * env_adsr(n, .005, .08, .6, .05, BEAT / 2 * .5)
        i = int(at * SR); bass[i:i + n] += s[: N - i] * .32
# arp plucks (16ths) 8-19 & 23-26
arp = np.zeros(N)
for bar in range(15):
    c = chords[bar % 4]; notes = [c[0] + 12, c[1] + 12, c[2] + 12, c[1] + 24]
    for k in range(16):
        at = bar * 2.0 + k * BEAT / 4
        if not (8 <= at < 19 or 23 <= at < 26): continue
        n = int(.22 * SR); f = midi(notes[k % 4])
        tt = t_arr(n); s = (saw(f, n) * .5 + np.sin(2 * np.pi * f * tt)) * np.exp(-tt * 22)
        s = fft_filter(s, hi=3500)
        i = int(at * SR); arp[i:i + n] += s[: N - i] * .09

# sidechain ducking from kicks
duck = np.ones(N)
kicks = list(np.arange(3.0, 19.0, BEAT)) + [19.0, 20.33, 21.66] + list(np.arange(23.0, 26.0, BEAT))
for k in kicks:
    i = int(k * SR); n = int(.3 * SR); d = 1 - .6 * np.exp(-t_arr(n) * 12)
    duck[i:i + n] = np.minimum(duck[i:i + n], d[: N - i])
for sig, pn, rv in ((pad * duck, 0, .35), (bass * duck, 0, 0), (arp * duck, .0, .45)):
    L += sig; R += sig; send += sig * rv
# stereo widen arp with short delay
d = int(.012 * SR); R[d:] += arp[:-d] * duck[:-d] * .6; L[:] += 0

# ---------------- FX ----------------
def riser(dur, f0=200, f1=4000, noise=True):
    n = int(dur * SR); t = t_arr(n); p = t / dur
    s = np.zeros(n)
    if noise:
        nz = rng.standard_normal(n); out = np.zeros(n); blk = 2048
        for b in range(0, n, blk):
            fc = f0 * (f1 / f0) ** (b / n)
            seg = nz[b:b + blk]
            out[b:b + blk] = fft_filter(np.pad(seg, (0, blk - len(seg))), lo=fc * .5, hi=fc * 1.5)[: len(seg)]
        s += out * 1.5
    f = f0 * .5 * (f1 / f0 * .5 / .5) ** p
    s += np.sin(2 * np.pi * np.cumsum(220 * 2 ** (p * 2.5)) / SR) * .25
    return s * p ** 2


def whoosh(dur=.5):
    n = int(dur * SR); t = t_arr(n); p = t / dur
    e = np.sin(np.pi * p) ** 2
    nz = rng.standard_normal(n); out = np.zeros(n); blk = 1024
    for b in range(0, n, blk):
        pp = b / n; fc = 400 + 5000 * np.sin(np.pi * pp)
        seg = nz[b:b + blk]
        out[b:b + blk] = fft_filter(np.pad(seg, (0, blk - len(seg))), lo=fc * .4, hi=fc * 1.6)[: len(seg)]
    return out * e


def impact(dur=3.0):
    n = int(dur * SR); t = t_arr(n)
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-t * 6)) / SR) * np.exp(-t * 1.6)
    crash = fft_filter(rng.standard_normal(n), lo=3000) * np.exp(-t * 2.5) * .25
    return np.tanh((boom + crash) * 1.4)


def shimmer(dur):
    n = int(dur * SR); t = t_arr(n); p = t / dur
    s = sum(np.sin(2 * np.pi * np.cumsum(f * (1 + .5 * p)) / SR) for f in (1760, 2637, 3520)) / 3
    return s * np.sin(np.pi * p) * (.6 + .4 * np.sin(2 * np.pi * 9 * t))


def click(f=3200, dur=.03):
    n = int(dur * SR); t = t_arr(n)
    return (np.sin(2 * np.pi * f * t) * .6 + fft_filter(rng.standard_normal(n), lo=2500) * .5) * np.exp(-t * 180)


def ding():
    n = int(1.2 * SR); t = t_arr(n)
    return (np.sin(2 * np.pi * 1318.5 * t) + .6 * np.sin(2 * np.pi * 1975.5 * t) * (t > .09)) * np.exp(-t * 4)


place(riser(2.9, 150, 5000), 0.1, .55, rev=.4)
place(impact(), 3.0, .7, rev=.3)
place(riser(3.0, 200, 6000), 23.0, .35, rev=.3)
place(impact(4.0), 26.0, .6, rev=.5)
for c in (8.0, 13.0, 19.0, 23.0):
    place(whoosh(.55), c - .4, .5, pan=-.2, rev=.3)
for c in (20.33, 21.66):
    place(whoosh(.35), c - .25, .4, pan=.2, rev=.2)
place(whoosh(.7), 25.6, .5, rev=.4)
place(shimmer(2.5), .3, .12, pan=.3, rev=.6)
for a, b in ((8.1, 9.4), (9.3, 10.8), (10.6, 12.0)): place(shimmer(b - a), a, .1, pan=-.3 + .3 * (a - 8), rev=.6)
for i in range(len('scandinavian armchair')):  # typing
    place(click(2600 + (i % 3) * 300, .025), 13.6 + i * 1.1 / 21, .18, pan=.1)
place(click(1800, .05), 15.7, .4); place(click(1800, .05), 17.7, .4)
place(ding(), 18.5, .22, rev=.5)
for at in (9.0, 9.5, 10.0, 10.5): place(click(4200, .04), at, .25, pan=.4, rev=.3)  # chip pops

# ---------------- reverb ----------------
irn = int(2.4 * SR); it = t_arr(irn)
ir = rng.standard_normal(irn) * np.exp(-it * 2.6); ir = fft_filter(ir, hi=6000)
ir_r = np.roll(ir, 37) * .95
nfft = 1 << int(np.ceil(np.log2(N + irn)))
S_ = np.fft.rfft(send, nfft)
wetL = np.fft.irfft(S_ * np.fft.rfft(ir, nfft), nfft)[:N]
wetR = np.fft.irfft(S_ * np.fft.rfft(ir_r, nfft), nfft)[:N]
wet_scale = .08
L += wetL * wet_scale; R += wetR * wet_scale

# ---------------- master ----------------
master = np.stack([L, R], 1)
fade = np.ones(N); fo = int(.8 * SR); fade[-fo:] = np.linspace(1, 0, fo) ** 2
fi = int(.05 * SR); fade[:fi] = np.linspace(0, 1, fi)
master *= fade[:, None]
master = np.tanh(master / np.max(np.abs(master)) * 1.8)
master /= np.max(np.abs(master)) / .93
pcm = (master * 32767).astype('<i2')
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('ok')

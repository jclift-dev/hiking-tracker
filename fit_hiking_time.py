#!/usr/bin/env python3
"""
Fit a hiking-time model to the SchweizMobil stages in hikes.json and test how
well it transfers to stages from other publishers.

Needs numpy and scipy (not in requirements.txt: this is an analysis tool, not
part of the app or scrapers):  pip install numpy scipy

    python3 fit_hiking_time.py

Model (shape from SAC / DIN 33466):
    time = max(h, v) + k * min(h, v),   h = km / flat_kmh,
                                        v = ascent / up_mh + descent / down_mh
The fitted values are copied into HIKE_FIT in index.html (see
docs/hiking-time-model.md).
"""
import json
import os

import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))


def load_rows():
    with open(os.path.join(HERE, "hikes.json"), encoding="utf-8") as f:
        data = json.load(f)
    ch, other = [], []
    for r in data:
        if r["land"].endswith("cycle"):
            continue
        for s in r["stages"]:
            if all(s.get(k) is not None for k in ("dist_km", "elev_up", "elev_down", "duration_hrs")):
                row = (s["dist_km"], s["elev_up"], s["elev_down"], s["duration_hrs"])
                (ch if r["land"] == "ch-hike" else other).append(row)
    return np.array(ch, float), np.array(other, float)


def din(p, d, u, n):
    h = d / p[0]
    v = u / p[1] + n / p[2]
    return np.maximum(h, v) + p[3] * np.minimum(h, v)


def fit(d, u, n, t, p0=(4.0, 300.0, 500.0, 0.5)):
    r = least_squares(lambda p: (din(p, d, u, n) - t) / np.sqrt(t), p0, loss="soft_l1", f_scale=0.3, max_nfev=4000)
    return r.x


def report(name, pred, t):
    e = (pred - t) * 60
    print(f"  {name:34s} MAE {np.mean(np.abs(e)):5.1f} min  bias {np.mean(e):+6.1f}  "
          f"within 15 min {np.mean(np.abs(e) <= 15) * 100:3.0f}%")


def main():
    ch, other = load_rows()
    print(f"{len(ch)} Swiss stages with a published time; {len(other)} non-Swiss stages with a source time\n")
    D, U, N, T = ch.T
    folds = np.array_split(np.random.RandomState(0).permutation(len(T)), 5)
    pred = np.zeros(len(T))
    for i, te in enumerate(folds):
        tr = np.concatenate([folds[j] for j in range(5) if j != i])
        pred[te] = din(fit(D[tr], U[tr], N[tr], T[tr]), D[te], U[te], N[te])
    print("5-fold cross-validated, Swiss stages:")
    report("fitted DIN-shape model", pred, T)
    report("constant speed (km / km/h)", D / (D / T).mean(), T)
    P = fit(D, U, N, T)
    print("\nfull fit: flat km/h %.3f, climb m/h %.1f, descent m/h %.1f, k %.3f" % tuple(P))
    od, ou, on, ot = other.T
    sw = din(P, od, ou, on)
    ratio = float(np.exp(np.mean(np.log(ot / sw))))
    print(f"\nnon-Swiss stages (their own sources' times), Swiss formula applied:")
    report("as-is", sw, ot)
    report(f"x {ratio:.2f} pace factor", sw * ratio, ot)
    print(f"\ngeometric-mean source/Swiss ratio = {ratio:.2f} -> HIKE_PACE_OTHER (1.12 in index.html)")


if __name__ == "__main__":
    main()

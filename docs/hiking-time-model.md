# Hiking-time estimates

Most non-Swiss hiking stages have no published duration, and cycling stages never do (SchweizMobil publishes no riding times). The app shows an **estimate**, marked with a leading `~`, wherever a stage has no real duration. Real durations always win. Estimates are computed in the browser (`stageHours()` in `index.html`); nothing is stored in `hikes.json` or Supabase. They feed the duration badge, the "Quickest first" sort and the Duration filter.

## Hiking

```
time = max(h, v) + k × min(h, v)
h = km ÷ 4.672 km/h        (flat)
v = ascent ÷ 422.6 m/h + descent ÷ 971.5 m/h
k = 0.598
```

The shape is the one used by SAC / DIN 33466; the four numbers were fitted (`fit_hiking_time.py`) to the 887 Swiss stages that have a SchweizMobil `hikingTime`.

| Test | Mean error | Within 15 min |
|---|---|---|
| Swiss stages, 5-fold cross-validated | 6.6 min | 94 % |
| Same, via the shipped JavaScript (incl. rounding to 15 min) | 7.2 min | 96 % |
| Constant-speed model (distance only) | 37 min | 25 % |
| Plain SAC numbers (4 km/h, 300 m/h, 500 m/h) | +75 min too slow | 1 % |

### Outside Switzerland

The 206 non-Swiss stages that do carry a time (France, Italy, E1, Germany) come from many publishers with different conventions. The Swiss formula runs about **12 % faster** than they do, so non-Swiss estimates are multiplied by `HIKE_PACE_OTHER = 1.12`, which removes the average bias. Individual stages remain noisy: roughly **±40 min** typical error, and refitting all four parameters on those stages does no better (39 min), so the noise is in the source times, not the formula. Treat a `~` time for a non-Swiss stage as a rough guide.

Stages without both ascent and descent get no estimate (a distance-only guess would be far too short in the mountains).

## Cycling

`distance ÷ 16 km/h + ascent ÷ 600 m` hours, rounded to 15 min. This is an assumption, not fitted to data.

## Reproducing / updating

```bash
pip install numpy scipy
python3 fit_hiking_time.py
```

If the fitted numbers change meaningfully (e.g. after more Swiss stages are added), update `HIKE_FIT` and `HIKE_PACE_OTHER` in `index.html`.

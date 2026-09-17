# Equation 2 against measured Jetson CPU energy

One Cortex-A78AE core pinned at 1.4976 GHz, 224x224 input, 120 split points over 5 models.

| model | splits | W range [GFLOP] | kappa [J/GFLOP] | R2 (through origin) | MAPE [%] | kappa spread [%] | alpha [FLOP/cycle] |
|---|---:|---|---:|---:|---:|---:|---:|
| `squeezenet1_1` | 24 | 0.043-0.699 | 0.0829 | 0.6209 | 25.1 | 222 | 3.48 |
| `swin_v2_t` | 24 | 0.267-5.998 | 0.0887 | 0.9902 | 7.4 | 64 | 3.88 |
| `efficientnet_b4` | 24 | 0.202-3.191 | 0.0900 | 0.9276 | 16.3 | 69 | 3.55 |
| `resnet50` | 24 | 0.272-8.290 | 0.0416 | 0.9910 | 8.4 | 123 | 9.22 |
| `densenet169` | 24 | 0.301-6.910 | 0.0459 | 0.9916 | 7.0 | 85 | 8.29 |
| **pooled** | 120 | 0.043-8.290 | 0.0567 | 0.6713 | 36.7 | 292 | 4.26 |

Paper Table 2: gamma = 2.0e-26 J.s^2, f = 1.5e+09 Hz, alpha = 32.0 FLOP, giving kappa = 1.4062 J/GFLOP.
Measured pooled kappa = 0.0567 J/GFLOP, a ratio of 24.8x.
Implied alpha at the pinned frequency: median 4.26, max 9.64 FLOP/cycle.
Implied gamma from dynamic power: 1.642e-28 J.s^2.
Zero-work control, W(l) = 0: [2e-06, 2e-06, 2e-06, 2e-06, 2e-06] J.

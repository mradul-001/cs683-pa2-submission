# Design-exploration runs

Extra ChampSim runs quoted in Summary.pdf (25M warm-up + 25M simulation, same build as
`results/raw_logs/`). Each variant is a small edit of the submitted code; the exact change
is in `variants/*.diff` (diffs are against the uncommented version of the file).
Not every variant was run on all three traces.

| Log prefix | Change | Diff |
|---|---|---|
| `spp_fixed_deg4` | SPP, throttling off, degree always 4 | `spp_fixed4.diff` |
| `spp_fixed_deg1` | SPP, throttling off, degree always 1 | `spp_fixed1.diff` |
| `spp_bands_85_65_45` | SPP, stricter accuracy bands (85/65/45 %) | `spp_strict.diff` |
| `spp_bands_55_30_15` | SPP, looser accuracy bands (55/30/15 %) | `spp_loose.diff` |
| `t3_thresh025`, `t3_thresh035` | SPP + dynamic I-RRIP at threshold 0.25 / 0.35 | none (`IRRIP_THRESH`) |
| `t3_v1_pref_rrpv2_*` | prefetched lines inserted at RRPV 2 instead of 3 | `dyn_irrip_v1.diff` |
| `t3_v2_no_promote_on_pref_hit_*` | an L2 hit by a prefetch request does not promote the line | `dyn_irrip_v2.diff` |
| `t3_v3_v1_plus_v2_*` | v1 and v2 together | `dyn_irrip_v3.diff` |
| `t3_e_data_hit_rrpv0_*` | in I-RRIP mode data hits promote to RRPV 0 | `dyn_irrip_e.diff` |
| `t3_h_instr_insert_rrpv0_*` | in I-RRIP mode instruction lines inserted at RRPV 0 | `dyn_irrip_h.diff` |
| `t3_n_no_pref_handling_*` | no prefetch awareness (prefetch fills treated as demand) | `dyn_irrip_n.diff` |
| `t3_q_pref_rrpv1_*` | prefetched lines inserted at RRPV 1 | `dyn_irrip_q.diff` |
| `t3_force_srrip`, `t3_force_irrip` | followers forced to SRRIP (threshold 1.01) / I-RRIP (threshold 0) | none (`IRRIP_THRESH`) |

The suffix `_t015`, `_t025`, `_t035` is the dynamic I-RRIP threshold used.

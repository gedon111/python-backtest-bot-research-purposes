# Workstream B - blind recompute (written BEFORE opening locked-results extract)

Scope: statistics layer independently recomputed with scipy/numpy primitives.
Engine (simulate_trades) validated separately by scratch/regression.py.

```
dataset.bar_count = 8767
dataset.first_open_time = 2022-01-01 08:00:00
dataset.last_open_time = 2026-01-01 08:00:00
ob.total_detected = 761
ob.criterion_true.displacement = 107 (14.1%)
ob.criterion_true.large_bar = 444 (58.3%)
ob.criterion_true.fvg = 253 (33.2%)
ob.criterion_true.liquidity_sweep = 406 (53.4%)
ob.criterion_true.volume_expansion = 412 (54.1%)
ob.quality_distribution = {0: 93, 1: 154, 2: 206, 3: 197, 4: 90, 5: 21}
baseline.n_trades = 27
baseline.wins = 19
baseline.win_rate_pct = 70.3704
baseline.total_net_return_pct = 30.3065
baseline.avg_return_per_trade_pct = 1.1225
baseline.sd_return_pct_ddof1 = 2.4101
baseline.sd_return_pct_ddof0 = 2.3651
baseline.binom_one_sided_p = 0.026119
baseline.binom_two_sided_p_scipy = 0.052239
q_ge_1.n_trades = 25
q_ge_1.wins = 17
q_ge_1.win_rate_pct = 68.0000
q_ge_1.binom_one_sided_p = 0.053876
ablation_A_flat_atr.n_trades = 140
ablation_A_flat_atr.win_rate_pct = 47.1429
ablation_A_flat_atr.total_return_pct = -13.7214
ablation_B_swing_pivot.n_trades = 138
ablation_B_swing_pivot.win_rate_pct = 43.4783
ablation_B_swing_pivot.total_return_pct = -23.8461
baseline.compounded_final_capital_10k = 13417.77
baseline.simple_sum_final_capital_10k = 13030.65
benchmark.dumped = bench_raw.json
```

## Part 2 - correlations, bootstrap, Welch, risk metrics

```
corr.pearson_r = 0.4907
corr.pearson_p = 0.009356
corr.pearson_t_manual = 2.8158
corr.pearson_df = 25
corr.spearman_rho = 0.4797
corr.spearman_p = 0.011335
bootstrap.numpy_pcg64_seed42_B10000 = [+5.99%, +54.99%]
bootstrap.repo_reported = {'bootstrap_ci': {'n': 27, 'b': 10000, 'seed': 42, 'total_return_point_pct': 30.306456356031937, 'total_return_ci_pct': [5.9866116295368155, 54.98658996206774], 'avg_return_point_pct': 1.1224613465197013, 'avg_return_ci_pct': [0.2217263566495117, 2.036540368965472], 'pct_resamples_total_le_zero': 0.75, 'pct_resamples_avg_le_zero': 0.75}, 'mde_power': {'alpha': 0.05, 'power': 0.8, 'criteria': {'Displacement': {'n_true': 4, 'sd_true': 1.182231458800881, 'n_false': 23, 'sd_false': 2.567007402373479, 'observed_diff': -0.7398224498276162, 'mde': 2.2341109175382656, 'detectable': False}, 'LargeBar': {'n_true': 20, 'sd_true': 2.7061765000447906, 'n_false': 7, 'sd_false': 1.3906866729118907, 'observed_diff': 0.23201292464061718, 'mde': 2.2455655783753854, 'detectable': False}, 'FVG': {'n_true': 11, 'sd_true': 3.0590081540493084, 'n_false': 16, 'sd_false': 1.9222669656929892, 'observed_diff': 0.5574517467176601, 'mde': 2.9136877127450345, 'detectable': False}, 'LiqSweep': {'n_true': 15, 'sd_true': 2.7597776733835957, 'n_false': 12, 'sd_false': 1.9245555353531651, 'observed_diff': -0.7404730301759611, 'mde': 2.531395710810557, 'detectable': False}, 'VolExpansion': {'n_true': 15, 'sd_true': 2.927074019497352, 'n_false': 12, 'sd_false': 1.5678845000698036, 'observed_diff': -0.7782727506480802, 'mde': 2.468003073903855, 'detectable': False}}}}
welch.displacement = n_true=4 n_false=23 t=-0.9277 p=0.3775
welch.large_bar = n_true=20 n_false=7 t=0.2895 p=0.7751
welch.fvg = n_true=11 n_false=16 t=0.5360 p=0.5996
welch.liquidity_sweep = n_true=15 n_false=12 t=-0.8195 p=0.4204
welch.volume_expansion = n_true=15 n_false=12 t=-0.8835 p=0.3864
repo.strategy_arm = {'arm': 'OB-gated strategy', 'total_return_pct': 30.306456, 'final_capital': 13417.773474, 'sharpe': 1.114203, 'max_drawdown_pct': -6.461922, 'time_in_market_pct': 2.634881, 'starting_capital': 10000.0}
```

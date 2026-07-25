# Orthogonal Order Block Criteria Reference & Statistical Breakdown

> **Paper Title:** *Harnessing Bitcoin Volatility: Backtesting an Integrated Algorithmic Strategy Combining KDJ, MACD, and Smart Money Concepts*  
> **Repository Context:** Binance Backtest Bot Research Package (`BTCUSDT` 4H Dataset, 2022–2026)  
> **Dataset Baseline:** $N = 27$ Unique Historical Trades (Orthogonal / No Quality Threshold Filter)

---

## 1. Executive Summary & Design Revision Rationale

The original strategy evaluated Order Block (OB) quality by summing 5 binary criteria into an ordinal composite score ($0\text{--}5$) and running nested threshold filter sweeps ($Q_0, Q_1, Q_2, Q_3$). Because higher quality thresholds formed strict nested subsets of lower thresholds ($Q_3 \subset Q_2 \subset Q_1 \subset Q_0$), score-based threshold filtering confounded statistical evaluation.

This document presents the **Orthogonal Criteria Reference**, treating each of the 5 criteria as independent binary flags. Each criterion is evaluated independently by partitioning the $N=27$ historical trades into **True** vs. **False** subgroups to isolate the true marginal edge of each individual structural property.

---

## 2. All-OB Pairwise Correlation Matrix ($N = 761$ Detected OBs)

Across all 761 detected Order Blocks in the 15,331-bar dataset, the pairwise Phi-coefficient (Pearson correlation for binary variables) matrix confirms the structural independence and collinearity patterns among criteria:

| Criterion | Displacement | LargeBar | FVG | LiqSweep | VolExpansion |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Displacement** | 1.0000 | +0.0726 | **+0.3841** | +0.0762 | +0.0474 |
| **LargeBar** | +0.0726 | 1.0000 | -0.0972 | +0.1983 | **+0.4099** |
| **FVG** | **+0.3841** | -0.0972 | 1.0000 | +0.1259 | -0.0052 |
| **LiqSweep** | +0.0762 | +0.1983 | +0.1259 | 1.0000 | +0.2389 |
| **VolExpansion** | +0.0474 | **+0.4099** | -0.0052 | +0.2389 | 1.0000 |

* **Key Takeaway**: `LargeBar` and `VolExpansion` are collinear ($r = +0.4099$), both acting as proxies for origin candle volume/range expansion. `FVG` strongly co-occurs with `Displacement` ($r = +0.3841$) because strong displacement leaves 3-candle price gaps, but `FVG` is completely orthogonal to `VolExpansion` ($r = -0.0052$).

---

## 3. Independent 5-Criterion Breakdown ($N = 27$ Trades)

The table below summarizes historical trade performance for each of the 5 criteria partitioned into `True` vs `False` subgroups:

| Criterion | Subgroup | Count ($N$) | Win Rate (%) | Total Return (%) | Avg Return (%) | SD (%) | Odds Ratio | Fisher Exact $p$ | Welch t-test $p$ | Statistical Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Displacement** | True<br>False | 4<br>23 | 50.00%<br>73.91% | +1.97%<br>+28.34% | +0.49%<br>+1.23% | 1.18%<br>2.57% | 0.3529 | *--* | *--* | ⚠️ **Descriptive Only**<br>*(Sample $n=4 < 5$)* |
| **LargeBar** | True<br>False | 20<br>7 | 70.00%<br>71.43% | +23.65%<br>+6.65% | +1.18%<br>+0.95% | 2.71%<br>1.39% | 0.9333 | 1.0000 | 0.7751 | ✅ **Not Significant**<br>*(p $\ge 0.05$)* |
| **FVG** | True<br>False | 15<br>12 | 66.67%<br>75.00% | +17.66%<br>+12.65% | +1.18%<br>+1.05% | 2.65%<br>2.18% | 0.6667 | 0.6957 | 0.8956 | ✅ **Not Significant**<br>*(p $\ge 0.05$)* |
| **LiqSweep** | True<br>False | 15<br>12 | 66.67%<br>75.00% | +11.90%<br>+18.41% | +0.79%<br>+1.53% | 2.76%<br>1.92% | 0.6667 | 0.6957 | 0.4204 | ✅ **Not Significant**<br>*(p $\ge 0.05$)* |
| **VolExpansion** | True<br>False | 15<br>12 | 60.00%<br>83.33% | +11.65%<br>+18.66% | +0.78%<br>+1.55% | 2.93%<br>1.57% | 0.3000 | 0.2357 | 0.3864 | ✅ **Not Significant**<br>*(p $\ge 0.05$)* |

---

## 4. Formula & Statistical Methodology

### 1. Univariable Odds Ratio ($OR$)
\[ OR = \frac{W_{\text{True}} / L_{\text{True}}}{W_{\text{False}} / L_{\text{False}}} \]
Measures the relative odds of a winning trade when the criterion is present versus absent. An $OR > 1.0$ indicates positive association with winning trades; $OR < 1.0$ indicates negative association.

### 2. Fisher's Exact Test ($p$-value for Win Rate)
Computes the exact hypergeometric probability of observing the $2 \times 2$ win/loss contingency matrix under the null hypothesis of equal win rates between True and False subgroups. Evaluated for criteria with $\min(N_{\text{True}}, N_{\text{False}}) \ge 5$.

### 3. Welch's Two-Sample t-Test ($p$-value for Mean Return)
\[ t = \frac{\bar{y}_{\text{True}} - \bar{y}_{\text{False}}}{\sqrt{\frac{SD_{\text{True}}^2}{N_{\text{True}}} + \frac{SD_{\text{False}}^2}{N_{\text{False}}}}} \]
Evaluates whether the difference in average percentage returns between True and False subgroups is statistically significant without assuming equal variances.

---

## 5. Summary Findings

1. **No Individual Criterion Drives Significant Performance Disparity**:
   * None of the 4 adequately sampled criteria reached statistical significance ($p < 0.05$) on either Win Rate (Fisher Exact Test) or Mean Return (Welch t-test).
2. **Core Strategy Edge Derivation**:
   * The baseline trading edge (70.37% win rate, +30.31% net return) is driven primarily by the **MACD histogram momentum alignment**, **KDJ acceleration**, **ATR regime filtering**, and **Risk-Reward structure**, rather than individual Order Block annotations.

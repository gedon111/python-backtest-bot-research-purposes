# Orthogonal Order Block Criteria Reference & Magnitude Contribution Analysis

> **Paper Title:** *Harnessing Bitcoin Volatility: Backtesting an Integrated Algorithmic Strategy Combining KDJ, MACD, and Smart Money Concepts*  
> **Repository Context:** Binance Backtest Bot Research Package (`BTCUSDT` 4H Dataset, 2022–2026)  
> **Baseline Dataset:** $N = 27$ Unique Historical Trades (Threshold 0 / Orthogonal Baseline Set)  
> **Strategy Net Return:** **+30.31%** across 4 years

---

## 1. Primary Magnitude & Return Contribution Reference Table

This table partitions the $N=27$ historical trades across each of the 5 criteria into **True** vs. **False** subgroups, measuring each subgroup's contribution to the strategy's total +30.31% net return, return concentration, and central tendency (Mean vs Median):

| Criterion | Subgroup | Count ($N$) | % of Total Trades | Sum PnL (%) | % of Total Return | Mean Return (%) | Median Return (%) | Best Trade PnL (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Displacement** | True<br>False | 4<br>23 | 14.81%<br>85.19% | +1.97%<br>+28.34% | 6.50%<br>93.50% | +0.49%<br>+1.23% | +0.50%<br>+0.63% | +1.63%<br>+6.69% |
| **LargeBar** | True<br>False | 20<br>7 | 74.07%<br>25.93% | +23.65%<br>+6.65% | 78.04%<br>21.96% | +1.18%<br>+0.95% | +0.53%<br>+0.77% | +6.69%<br>+3.65% |
| **FVG** | True<br>False | 15<br>12 | 55.56%<br>44.44% | +17.66%<br>+12.65% | 58.27%<br>41.73% | +1.18%<br>+1.05% | +0.77%<br>+0.44% | +6.69%<br>+4.62% |
| **LiqSweep** | True<br>False | 15<br>12 | 55.56%<br>44.44% | +11.90%<br>+18.41% | 39.27%<br>60.73% | +0.79%<br>+1.53% | +0.38%<br>+1.31% | +6.69%<br>+4.36% |
| **VolExpansion** | True<br>False | 15<br>12 | 55.56%<br>44.44% | +11.65%<br>+18.66% | 38.44%<br>61.56% | +0.78%<br>+1.55% | +0.13%<br>+1.31% | +6.69%<br>+4.62% |

---

## 2. Key Insights & Return Concentration Analysis

### A. Return Share vs. Trade Share
1. **`LargeBar`**: Closely proportional contribution. $20/27$ trades (74.07%) generated **78.04%** (+23.65%) of total return.
2. **`FVG`**: Moderate positive bias. $15/27$ trades (55.56%) generated **58.27%** (+17.66%) of total return, with a higher median return (+0.77% vs +0.44%).
3. **`LiqSweep` & `VolExpansion`**: Inverse return concentration. For both criteria, the `False` subgroup ($12/27$ trades, 44.44%) generated **> 60% of total strategy return** (+18.41% and +18.66%), achieving significantly higher median returns per trade (**+1.31%** vs +0.38% / +0.13%).

### B. Outlier Concentration (% of Subgroup Return from Best Single Trade)
* **`Displacement = True`**: Highly concentrated ($82.98\%$ of group return came from 1 trade, +1.63% out of +1.97%).
* **`VolExpansion = True`**: Concentrated ($57.42\%$ of group return came from 1 single outlier trade of +6.69%).
* **`VolExpansion = False`**: Broadly distributed ($24.78\%$ from best trade), demonstrating consistent steady gains across multiple trades.

---

## 3. Secondary Hypothesis Testing (Exploratory Welch's t-Test)

> [!NOTE]
> **Methodological Framing**: Hypothesis testing is secondary and exploratory due to small subgroup sizes ($n=4 \text{ to } n=20$). Main inference relies on empirical magnitude and return distribution above.

* **Displacement**: $t = -0.9277$, $p = 0.3775$
* **LargeBar**: $t = +0.2895$, $p = 0.7751$
* **FVG**: $t = +0.1326$, $p = 0.8956$
* **LiqSweep**: $t = -0.8195$, $p = 0.4204$
* **VolExpansion**: $t = -0.8835$, $p = 0.3864$

---

## 4. All-OB Pairwise Correlation Matrix ($N = 761$ Detected OBs)

Across all 761 detected Order Blocks in the dataset:

| Criterion | Displacement | LargeBar | FVG | LiqSweep | VolExpansion |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Displacement** | 1.0000 | +0.0726 | **+0.3841** | +0.0762 | +0.0474 |
| **LargeBar** | +0.0726 | 1.0000 | -0.0972 | +0.1983 | **+0.4099** |
| **FVG** | **+0.3841** | -0.0972 | 1.0000 | +0.1259 | -0.0052 |
| **LiqSweep** | +0.0762 | +0.1983 | +0.1259 | 1.0000 | +0.2389 |
| **VolExpansion** | +0.0474 | **+0.4099** | -0.0052 | +0.2389 | 1.0000 |

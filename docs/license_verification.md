# License Verification

Two independent signals per package: GitHub's repo-license classifier (Signal A) and a keyword scan of the actual raw LICENSE file text fetched directly (Signal B). PASS requires both to independently agree on the same permissive family (MIT / BSD / Apache-2.0) with no restrictive modifier.

**Summary:** 8 PASS · 3 FLAGGED · 0 ERROR (of 11 packages)

| Package | Repo | Signal A (GitHub API) | Signal B (raw text) | Verdict | Notes |
|---|---|---|---|---|---|
| arch | bashtage/arch | none detected | BSD-3-Clause | **FLAGGED** | at least one signal produced no classification (see notes); Signal A: no SPDX license detected by GitHub's classifier |
| tsbootstrap | astrogilda/tsbootstrap | MIT | MIT | **PASS** | GitHub license API and independent raw-text scan agree |
| scikits-bootstrap | cgevans/scikits-bootstrap | BSD-3-Clause | BSD-3-Clause | **PASS** | GitHub license API and independent raw-text scan agree |
| empyrical-reloaded | stefan-jansen/empyrical-reloaded | Apache-2.0 | Apache-2.0 | **PASS** | GitHub license API and independent raw-text scan agree |
| quantstats | ranaroussi/quantstats | Apache-2.0 | Apache-2.0 | **PASS** | GitHub license API and independent raw-text scan agree |
| walk-forward-backtester | TonyMa1/walk-forward-backtester | MIT | MIT | **PASS** | GitHub license API and independent raw-text scan agree |
| rfpimp | parrt/random-forest-importances | MIT | MIT | **PASS** | GitHub license API and independent raw-text scan agree |
| pandas-ta-classic | xgboosted/pandas-ta-classic | MIT | MIT | **PASS** | GitHub license API and independent raw-text scan agree |
| ta | bukosabino/ta | MIT | MIT | **PASS** | GitHub license API and independent raw-text scan agree |
| mintalib | furechan/mintalib | MIT | none detected | **FLAGGED** | at least one signal produced no classification (see notes); Signal B: found LICENSE.txt but text did not match any known license pattern |
| MyTT | mpquant/MyTT | none detected | none detected | **FLAGGED** | at least one signal produced no classification (see notes); Signal A: no SPDX license detected by GitHub's classifier; Signal B: no LICENSE-like file found at any common filename |

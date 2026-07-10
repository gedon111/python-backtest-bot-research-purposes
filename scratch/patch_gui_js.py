import os

filepath = "gui.js"
with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

original_crlf = ("\r\n" in code)
code = code.replace("\r\n", "\n")

target = """        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                if (currentResizer) currentResizer.classList.remove('dragging');
                saveHeights();
            }
        });
    }
});"""

rep = """        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                if (currentResizer) currentResizer.classList.remove('dragging');
                saveHeights();
            }
        });
        
        // Setup ML Control Center integration
        setupMLControlCenter();
    }
    
    function setupMLControlCenter() {
        const strategySelect = document.getElementById('strategy-select');
        const mlPrevSelect = document.getElementById('ml-prev-select');
        const mlBtnTrain = document.getElementById('ml-btn-train');
        const mlNewLabel = document.getElementById('ml-new-label');
        const mlStatusPanel = document.getElementById('ml-status-panel');
        const mlStatusPhase = document.getElementById('ml-status-phase');
        const mlStatusProgress = document.getElementById('ml-status-progress');
        const mlStatusLog = document.getElementById('ml-status-log');
        const mlIterationsBody = document.getElementById('ml-iterations-body');
        const btnSyncGsheet = document.getElementById('btn-sync-gsheet');
        
        const compCard = document.getElementById('ml-comparison-card');
        const compParamsList = document.getElementById('comp-params-list');
        const compMetricsList = document.getElementById('comp-metrics-list');
        const compPatternsList = document.getElementById('comp-patterns-list');

        let isTraining = false;
        let pollInterval = null;

        // Fetch and render iterations
        async function loadIterations() {
            try {
                const res = await fetch('/api/iterations');
                if (!res.ok) throw new Error("Failed to fetch iterations");
                const iterations = await res.json();
                
                // Clear and populate dropdowns
                strategySelect.innerHTML = '<option value="0">Heuristic Base (No ML)</option>';
                mlPrevSelect.innerHTML = '<option value="none">None (Fresh Start)</option>';
                
                iterations.forEach(it => {
                    const opt1 = document.createElement('option');
                    opt1.value = it.iteration_id;
                    opt1.textContent = `[ID ${it.iteration_id}] ${it.label}`;
                    strategySelect.appendChild(opt1);

                    const opt2 = document.createElement('option');
                    opt2.value = it.iteration_id;
                    opt2.textContent = `[ID ${it.iteration_id}] ${it.label}`;
                    mlPrevSelect.appendChild(opt2);
                });

                // Render Iterations Table
                mlIterationsBody.innerHTML = '';
                if (iterations.length === 0) {
                    mlIterationsBody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-muted);">No iterations found. Run your first training run!</td></tr>';
                } else {
                    iterations.forEach(it => {
                        const tr = document.createElement('tr');
                        tr.style.borderBottom = '1px solid var(--border)';
                        
                        const pnl = it.metrics.optimized_pnl_pct != null ? it.metrics.optimized_pnl_pct.toFixed(2) : '0.00';
                        const wr = it.metrics.optimized_win_rate != null ? it.metrics.optimized_win_rate.toFixed(2) : '0.00';
                        
                        tr.innerHTML = `
                            <td style="padding: 10px;">${it.iteration_id}</td>
                            <td style="padding: 10px; font-weight: 500;" id="label-cell-${it.iteration_id}">${it.label}</td>
                            <td style="padding: 10px; color: ${pnl >= 0 ? '#10b981' : '#ef4444'}">${pnl}%</td>
                            <td style="padding: 10px;">${wr}%</td>
                            <td style="padding: 10px;">
                                <button class="btn-toggle" onclick="window.selectMLIteration(${it.iteration_id})" style="padding: 3px 8px; font-size: 0.8rem; background: #3b82f6; color: white; border: none; cursor: pointer; border-radius: 3px; font-family: inherit;">Activate</button>
                                <button class="btn-toggle" onclick="window.renameMLIteration(${it.iteration_id}, '${it.label.replace(/'/g, "\\\\'")}')" style="padding: 3px 8px; font-size: 0.8rem; background: #475569; color: white; border: none; cursor: pointer; border-radius: 3px; font-family: inherit; margin-left: 5px;">Rename</button>
                            </td>
                        `;
                        tr.style.cursor = 'pointer';
                        tr.addEventListener('click', (e) => {
                            if (e.target.tagName !== 'BUTTON') {
                                showComparison(it);
                            }
                        });
                        mlIterationsBody.appendChild(tr);
                    });
                }
            } catch (err) {
                console.error("Error loading iterations:", err);
            }
        }

        // Global functions for inline table actions
        window.selectMLIteration = async function(id) {
            strategySelect.value = id;
            await handleStrategyChange(id);
            // Navigate back to chart tab
            const chartTabBtn = document.querySelector('[data-tab="chart-tab"]');
            if (chartTabBtn) chartTabBtn.click();
        };

        window.renameMLIteration = async function(id, currentLabel) {
            const newLabel = prompt("Enter new label for this iteration:", currentLabel);
            if (newLabel === null || newLabel.trim() === "") return;
            
            try {
                const res = await fetch('/api/iterations/update_label', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ iteration_id: id, label: newLabel.trim() })
                });
                if (!res.ok) throw new Error("Failed to update label");
                await loadIterations();
            } catch (err) {
                alert("Error updating label: " + err.message);
            }
        };

        // Render iteration comparison card details
        function showComparison(it) {
            compCard.style.display = 'block';
            
            // 1. Tuned parameters
            compParamsList.innerHTML = '';
            const p = it.parameters;
            const paramLabels = {
                sl_ratio_min: 'Min SL Distance',
                kdj_j_long_cap: 'KDJ J Long Cap',
                kdj_k_long_cap: 'KDJ K Long Cap',
                kdj_k_short_floor: 'KDJ K Short Floor',
                kdj_j_short_cap: 'KDJ J Short Cap',
                atr_mult_exit: 'ATR Move Exit Mult',
                atr_mult_be: 'ATR BE SL Mult',
                rr_min: 'Min Reward/Risk Ratio'
            };
            Object.keys(paramLabels).forEach(key => {
                if (p[key] !== undefined) {
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${paramLabels[key]}:</strong> ${p[key]}`;
                    compParamsList.appendChild(li);
                }
            });

            // 2. Metrics (Heuristic vs Optimized side-by-side)
            compMetricsList.innerHTML = `
                <li><strong>Net PnL (Base):</strong> ${it.metrics.original_pnl_pct.toFixed(2)}%</li>
                <li><strong>Net PnL (ML Filtered):</strong> <span style="color:#10b981; font-weight:bold;">${it.metrics.optimized_pnl_pct.toFixed(2)}%</span></li>
                <hr style="border: 0; border-top: 1px solid var(--border); margin: 8px 0;">
                <li><strong>Win Rate (Base):</strong> ${it.metrics.original_win_rate.toFixed(2)}%</li>
                <li><strong>Win Rate (ML Filtered):</strong> <span style="color:#10b981; font-weight:bold;">${it.metrics.optimized_win_rate.toFixed(2)}%</span></li>
                <hr style="border: 0; border-top: 1px solid var(--border); margin: 8px 0;">
                <li><strong>Total Trades (Base):</strong> ${it.metrics.original_trades}</li>
                <li><strong>Total Trades (ML Filtered):</strong> ${it.metrics.optimized_trades}</li>
            `;

            // 3. Pattern Recognition Analysis
            compPatternsList.innerHTML = `
                <li><strong>Classifier Model:</strong> RandomForest</li>
                <li><strong>Pattern Improvement:</strong> ${it.pattern_diff.pnl_improvement_pct >= 0 ? '+' : ''}${it.pattern_diff.pnl_improvement_pct.toFixed(2)}% net</li>
                <li><strong>Feedback Reweights:</strong> Loaded ${it.pattern_diff.reweighted_failures_count} error patterns</li>
                <li style="margin-top: 10px; font-size: 0.8rem; color: var(--text-muted); font-style: italic;">
                    * The classifier scores indicators & OB touches at setup entry, automatically screening out negative expectancy patterns.
                </li>
            `;
        }

        // Handle strategy active changes
        async function handleStrategyChange(id) {
            strategySelect.disabled = true;
            const origText = strategySelect.options[strategySelect.selectedIndex].text;
            strategySelect.options[strategySelect.selectedIndex].text = "Simulating Strategy...";
            
            try {
                const res = await fetch('/api/iterations/select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ iteration_id: parseInt(id) })
                });
                if (!res.ok) throw new Error("Failed to select iteration on server");
                
                // Reload json artifacts & redraw
                const [manifest, candles, runsByThreshold, verification] = await Promise.all([
                    fetchJson('artifacts/manifest.json'),
                    fetchJson('artifacts/candles.json'),
                    fetchJson('artifacts/runs_by_threshold.json'),
                    fetchJson('artifacts/verification_report.json'),
                ]);
                
                currentData = candles;
                timeToIndex = new Map(candles.map((row, idx) => [row.time, idx]));
                setVerificationPill(verification);
                
                // Set indicators data
                macdHist.setData(candles.map(d => ({ time: d.time, value: d.MACD_hist, color: d.MACD_hist > 0 ? '#10b981' : '#ef4444' })));
                macdLine.setData(candles.map(d => ({ time: d.time, value: d.MACD })));
                signalLine.setData(candles.map(d => ({ time: d.time, value: d.MACD_signal })));
                kLine.setData(candles.map(d => ({ time: d.time, value: d.K })));
                dLine.setData(candles.map(d => ({ time: d.time, value: d.D })));
                jLine.setData(candles.map(d => ({ time: d.time, value: d.J })));
                atrLine.setData(candles.map(d => ({ time: d.time, value: d.ATR })));
                atr200Line.setData(candles.map(d => ({ time: d.time, value: d.ATR_200 })));

                // Recompute markers and lines
                const qualitySelect = document.getElementById('quality-select');
                const levelSelect = document.getElementById('ob-level');
                const structureSelect = document.getElementById('ob-structure');
                processData(runsByThreshold[qualitySelect.value] || { obs: [], trades: [] }, levelSelect.value, structureSelect.value);
                updateOverlays();
                
            } catch (err) {
                alert("Failed to load strategy details: " + err.message);
            } finally {
                strategySelect.disabled = false;
                strategySelect.options[strategySelect.selectedIndex].text = origText;
            }
        }

        strategySelect.addEventListener('change', (e) => {
            handleStrategyChange(e.target.value);
        });

        // 2. Training Run handling
        mlBtnTrain.addEventListener('click', async () => {
            if (isTraining) return;
            isTraining = true;
            mlBtnTrain.disabled = true;
            mlBtnTrain.innerText = "Optimising...";
            mlStatusPanel.classList.remove('hidden');
            
            const labelText = mlNewLabel.value.trim() || "ML RandomForest Run";
            const prevSelectVal = mlPrevSelect.value;
            const prevId = prevSelectVal === "none" ? null : parseInt(prevSelectVal);

            try {
                const res = await fetch('/api/run_ml', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ label: labelText, prev_iteration_id: prevId })
                });
                if (!res.ok) throw new Error("Optimizer launch failed");
                
                // Start polling
                pollInterval = setInterval(pollTrainingStatus, 1000);
            } catch (err) {
                mlStatusPhase.innerText = "Status: Error";
                mlStatusLog.innerText = "Error: " + err.message;
                isTraining = false;
                mlBtnTrain.disabled = false;
                mlBtnTrain.innerText = "Run Optimization Run";
            }
        });

        // Polling loop
        async function pollTrainingStatus() {
            try {
                const res = await fetch('/api/run_ml/status');
                if (!res.ok) throw new Error("Status poll failed");
                const status = await res.json();
                
                mlStatusPhase.innerText = `Status: ${status.phase}`;
                mlStatusProgress.style.width = `${status.progress}%`;
                mlStatusLog.innerText = status.log;
                mlStatusLog.scrollTop = mlStatusLog.scrollHeight; // auto-scroll
                
                if (status.phase === "Complete" || status.phase === "Error") {
                    clearInterval(pollInterval);
                    isTraining = false;
                    mlBtnTrain.disabled = false;
                    mlBtnTrain.innerText = "Run Optimization Run";
                    await loadIterations();
                }
            } catch (err) {
                console.error("Polling error:", err);
            }
        }

        // Google Sheets sync
        btnSyncGsheet.addEventListener('click', async () => {
            btnSyncGsheet.disabled = true;
            const origBg = btnSyncGsheet.style.background;
            btnSyncGsheet.style.background = "#475569";
            btnSyncGsheet.innerText = "Syncing...";
            
            try {
                const res = await fetch('/api/push_gsheet', { method: 'POST' });
                if (!res.ok) {
                    const errText = await res.text();
                    throw new Error(errText || "Google Sheets update failed.");
                }
                const result = await res.json();
                alert("Google Sheets Sync successful!");
            } catch (err) {
                alert("Sync failed: " + err.message);
            } finally {
                btnSyncGsheet.disabled = false;
                btnSyncGsheet.style.background = origBg;
                btnSyncGsheet.innerText = "Sync GSheets";
            }
        });

        // Initial load of iterations list
        loadIterations();
    }
});"""

target = target.replace("\r\n", "\n")
rep = rep.replace("\r\n", "\n")

if target in code:
    code = code.replace(target, rep)
    print("Patch 1 applied!")
else:
    print("Patch 1 not found!")

# Restore line endings
if original_crlf:
    code = code.replace("\n", "\r\n")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)
print("Successfully saved changes to gui.js!")

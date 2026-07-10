import os

filepath = "gui.html"
with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

original_crlf = ("\r\n" in code)
code = code.replace("\r\n", "\n")

# 1. Sidebar Nav items replacement
target_1 = """            <div class="nav-items">
                <button class="nav-item active" data-tab="chart-tab">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                    Chart View
                </button>
                <button class="nav-item" data-tab="sandbox-tab">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
                    Formula Sandbox
                </button>
            </div>"""

rep_1 = """            <div class="nav-items">
                <button class="nav-item active" data-tab="chart-tab">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                    Chart View
                </button>
                <button class="nav-item" data-tab="ml-tab">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                    ML Control Center
                </button>
                <button class="nav-item" data-tab="sandbox-tab">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
                    Formula Sandbox
                </button>
            </div>"""

target_1 = target_1.replace("\r\n", "\n")
rep_1 = rep_1.replace("\r\n", "\n")

if target_1 in code:
    code = code.replace(target_1, rep_1)
    print("Patch 1 applied!")
else:
    print("Patch 1 not found!")

# 2. Control bar replacement
target_2 = """                <div class="control-bar">
                    <label>Min OB Quality
                        <select id="quality-select"></select>
                    </label>
                    <label>OB Level
                        <select id="ob-level">
                            <option value="all">All</option>
                            <option value="internal">Internal</option>
                            <option value="swing">Swing</option>
                        </select>
                    </label>
                    <label>OB Structure
                        <select id="ob-structure">
                            <option value="all">All</option>
                            <option value="BOS">BOS</option>
                            <option value="CHoCH">CHoCH</option>
                        </select>
                    </label>
                    <button class="btn-toggle active" id="btn-show-lines">Show Lines: ON</button>
                    <label class="inline-check"><input id="toggle-ob-zones" type="checkbox" checked> Show OB Zones</label>
                    <label class="inline-check"><input id="toggle-ob-markers" type="checkbox" checked> Show OB Markers</label>
                    <button class="btn-toggle active" id="btn-auto-fit">Auto Fit: ON</button>
                </div>"""

rep_2 = """                <div class="control-bar">
                    <label>Active Strategy
                        <select id="strategy-select">
                            <option value="0">Heuristic Base (No ML)</option>
                        </select>
                    </label>
                    <label>Min OB Quality
                        <select id="quality-select"></select>
                    </label>
                    <label>OB Level
                        <select id="ob-level">
                            <option value="all">All</option>
                            <option value="internal">Internal</option>
                            <option value="swing">Swing</option>
                        </select>
                    </label>
                    <label>OB Structure
                        <select id="ob-structure">
                            <option value="all">All</option>
                            <option value="BOS">BOS</option>
                            <option value="CHoCH">CHoCH</option>
                        </select>
                    </label>
                    <button class="btn-toggle active" id="btn-show-lines">Show Lines: ON</button>
                    <label class="inline-check"><input id="toggle-ob-zones" type="checkbox" checked> Show OB Zones</label>
                    <label class="inline-check"><input id="toggle-ob-markers" type="checkbox" checked> Show OB Markers</label>
                    <button class="btn-toggle active" id="btn-auto-fit">Auto Fit: ON</button>
                    <button class="btn-toggle" id="btn-sync-gsheet" style="background: #eab308; color: #0f172a; font-weight: 600; font-family: inherit;">Sync GSheets</button>
                </div>"""

target_2 = target_2.replace("\r\n", "\n")
rep_2 = rep_2.replace("\r\n", "\n")

if target_2 in code:
    code = code.replace(target_2, rep_2)
    print("Patch 2 applied!")
else:
    print("Patch 2 not found!")

# 3. Sandbox Tab end / ML Tab insertion
target_3 = """                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </main>"""

rep_3 = """                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- ML Control Center Tab -->
            <section id="ml-tab" class="tab-pane">
                <div class="sandbox-header">
                    <h2>ML Control Center</h2>
                    <p>Train new iterations, label models, compare metrics, and select active configurations.</p>
                </div>
                
                <div class="sandbox-grid" style="grid-template-columns: 1fr 1fr; gap: 20px; display: grid;">
                    <!-- ML Training Control Card -->
                    <div class="calc-card" style="grid-column: 1;">
                        <h3>Train ML Model</h3>
                        <div style="margin-bottom: 1rem; text-align: left;">
                            <label>New Iteration Label: 
                                <input type="text" id="ml-new-label" value="ML Iteration Random Forest" style="width: 100%; margin-top: 5px; box-sizing: border-box; background: var(--bg-base); border: 1px solid var(--border); color: var(--text-base); padding: 8px; border-radius: 4px;">
                            </label>
                        </div>
                        <div style="margin-bottom: 1rem; text-align: left;">
                            <label>Base on Prior Iteration (Error Feedback):
                                <select id="ml-prev-select" style="width: 100%; margin-top: 5px; background: var(--bg-base); border: 1px solid var(--border); color: var(--text-base); padding: 8px; border-radius: 4px;">
                                    <option value="none">None (Fresh Start)</option>
                                </select>
                            </label>
                        </div>
                        <button id="ml-btn-train" class="btn-toggle" style="background: #10b981; color: white; width: 100%; height: 40px; font-weight: 600; cursor: pointer; border-radius: 4px; border: none; font-family: inherit;">Run Optimization Run</button>
                        
                        <div id="ml-status-panel" class="hidden" style="margin-top: 1.5rem; border-top: 1px solid var(--border); padding-top: 1rem;">
                            <h4 id="ml-status-phase" style="margin: 0 0 5px 0; text-align: left;">Status: Idle</h4>
                            <div class="progress-bar-container" style="width:100%; background: #334155; height: 10px; border-radius: 5px; margin: 10px 0; overflow:hidden;">
                                <div id="ml-status-progress" style="width: 0%; height: 100%; background: #10b981; transition: width 0.3s ease;"></div>
                            </div>
                            <div id="ml-status-log" style="font-family: monospace; font-size: 0.8rem; background: #0f172a; border-radius: 4px; padding: 10px; max-height: 150px; height: 100px; overflow-y: auto; white-space: pre-wrap; color: #38bdf8; text-align: left;">Log output...</div>
                        </div>
                    </div>

                    <!-- Iteration Management Card -->
                    <div class="calc-card" style="grid-column: 2;">
                        <h3>Model Iterations</h3>
                        <div class="table-container" style="max-height: 300px; overflow-y: auto; border: 1px solid var(--border); border-radius: 6px;">
                            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem;" id="ml-iterations-table">
                                <thead style="background: var(--bg-surface); position: sticky; top: 0; color: var(--text-muted);">
                                    <tr>
                                        <th style="padding: 10px; border-bottom: 1px solid var(--border);">ID</th>
                                        <th style="padding: 10px; border-bottom: 1px solid var(--border);">Label</th>
                                        <th style="padding: 10px; border-bottom: 1px solid var(--border);">Net Return</th>
                                        <th style="padding: 10px; border-bottom: 1px solid var(--border);">Win Rate</th>
                                        <th style="padding: 10px; border-bottom: 1px solid var(--border);">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="ml-iterations-body">
                                    <tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-muted);">Loading iterations...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Side-by-Side Comparison Card -->
                    <div class="calc-card full-width" id="ml-comparison-card" style="display: none; grid-column: span 2;">
                        <h3>Active Iteration Comparison</h3>
                        <div class="comparison-grid" style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-top: 15px; text-align: left;">
                            <div class="comp-col" style="background: var(--bg-surface); padding: 15px; border-radius: 8px; border: 1px solid var(--border);">
                                <h4 style="margin-top:0;">Tuned Parameters</h4>
                                <ul id="comp-params-list" style="list-style: none; padding: 0; font-size: 0.85rem; font-family: monospace; line-height: 1.6; margin:0;">
                                </ul>
                            </div>
                            <div class="comp-col" style="background: var(--bg-surface); padding: 15px; border-radius: 8px; border: 1px solid var(--border);">
                                <h4 style="margin-top:0;">Performance Metrics</h4>
                                <ul id="comp-metrics-list" style="list-style: none; padding: 0; font-size: 0.85rem; font-family: monospace; line-height: 1.6; margin:0;">
                                </ul>
                            </div>
                            <div class="comp-col" style="background: var(--bg-surface); padding: 15px; border-radius: 8px; border: 1px solid var(--border);">
                                <h4 style="margin-top:0;">Pattern Recognition Analysis</h4>
                                <ul id="comp-patterns-list" style="list-style: none; padding: 0; font-size: 0.85rem; font-family: monospace; line-height: 1.6; margin:0;">
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </main>"""

target_3 = target_3.replace("\r\n", "\n")
rep_3 = rep_3.replace("\r\n", "\n")

if target_3 in code:
    code = code.replace(target_3, rep_3)
    print("Patch 3 applied!")
else:
    print("Patch 3 not found!")

# Restore line endings
if original_crlf:
    code = code.replace("\n", "\r\n")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(code)
print("Successfully saved changes to gui.html!")

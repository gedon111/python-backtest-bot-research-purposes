document.addEventListener('DOMContentLoaded', async () => {
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    // Multi-pane instances
    let charts = [];
    let mainChart, macdChart, kdjChart, atrChart;
    let candleSeries;
    let macdHist, macdLine, signalLine;
    let kLine, dLine, jLine;
    let atrLine, atr200Line;
    let isSyncing = false;
    let timeToIndex = new Map();
    let currentData = [];
    let activeIterationId = 0;
    let loadedIterations = [];
    let activeHoveredTime = null;
    let processedObs = [];
    let processedTrades = [];

    const els = {
        o: document.getElementById('val-o'), h: document.getElementById('val-h'),
        l: document.getElementById('val-l'), c: document.getElementById('val-c'),
        macd: document.getElementById('val-macd'), k: document.getElementById('val-k'),
        d: document.getElementById('val-d'), j: document.getElementById('val-j'),
        atr: document.getElementById('val-atr'), atr200: document.getElementById('val-atr200'),
    };

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(nav => nav.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            item.classList.add('active');
            const target = document.getElementById(item.getAttribute('data-tab'));
            if (target) {
                target.classList.add('active');
            }
            if (item.getAttribute('data-tab') === 'chart-tab' && mainChart) {
                charts.forEach(c => c.timeScale().fitContent());
            }
        });
    });

    try {
        const [manifest, candles, runsByThreshold, verification] = await Promise.all([
            fetchJson('artifacts/manifest.json'),
            fetchJson('artifacts/candles.json'),
            fetchJson('artifacts/runs_by_threshold.json'),
            fetchJson('artifacts/verification_report.json'),
        ]);
        setVerificationPill(verification);
        bootCharts(manifest, candles, runsByThreshold);
        setupDragHandles();
    } catch (err) {
        document.getElementById('pane-main').innerHTML =
            `<div style="color:red; padding: 20px;">Error loading artifacts. Run export_gui_data.py then run run_dashboard.bat.<br>${err.message}</div>`;
    }

    function bootCharts(manifest, data, runsByThreshold) {
        currentData = data;
        timeToIndex = new Map(data.map((row, idx) => [row.time, idx]));
        
        const commonOptions = {
            layout: { 
                background: { type: 'solid', color: '#ffffff' }, 
                textColor: '#475569',
                fontFamily: 'Inter, sans-serif',
                fontSize: 11
            },
            grid: { 
                vertLines: { color: '#f1f5f9', style: 1 }, 
                horzLines: { color: '#f1f5f9', style: 1 } 
            },
            crosshair: { 
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#cbd5e1', style: 1 },
            },
            rightPriceScale: { 
                borderColor: '#e2e8f0',
                minimumWidth: 100
            },
            timeScale: { borderColor: '#e2e8f0', timeVisible: true }
        };

        const subChartOptions = {
            ...commonOptions,
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#cbd5e1', style: 1, visible: true },
                horzLine: { color: '#cbd5e1', style: 1, visible: true }
            },
        };

        mainChart = LightweightCharts.createChart(document.getElementById('pane-main'), commonOptions);
        macdChart = LightweightCharts.createChart(document.getElementById('pane-macd'), subChartOptions);
        kdjChart  = LightweightCharts.createChart(document.getElementById('pane-kdj'),  subChartOptions);
        atrChart  = LightweightCharts.createChart(document.getElementById('pane-atr'),  subChartOptions);
        
        charts = [mainChart, macdChart, kdjChart, atrChart];
        
        mainChart.timeScale().applyOptions({ visible: false });
        macdChart.timeScale().applyOptions({ visible: false });
        kdjChart.timeScale().applyOptions({ visible: false });

        candleSeries = addCandlestickSeriesCompat(mainChart, {
            upColor: '#ffffff',
            downColor: '#475569',
            borderUpColor: '#475569',
            borderDownColor: '#475569',
            wickUpColor: '#475569',
            wickDownColor: '#475569',
        });
        
        macdHist = addHistogramSeriesCompat(macdChart, { color: '#94a3b8', priceFormat: { type: 'volume' } });
        macdLine = addLineSeriesCompat(macdChart, { color: '#475569', lineWidth: 1.5 });
        signalLine = addLineSeriesCompat(macdChart, { color: '#cbd5e1', lineWidth: 1 });
        
        kLine = addLineSeriesCompat(kdjChart, { color: '#475569', lineWidth: 1.5 });
        dLine = addLineSeriesCompat(kdjChart, { color: '#94a3b8', lineWidth: 1.2 });
        jLine = addLineSeriesCompat(kdjChart, { color: '#cbd5e1', lineWidth: 1 });
        
        atrLine = addLineSeriesCompat(atrChart, { color: '#475569', lineWidth: 1.5 });
        atr200Line = addLineSeriesCompat(atrChart, { color: '#cbd5e1', lineWidth: 1.5 });

        // Set indicator data
        macdHist.setData(data.map(d => ({ time: d.time, value: d.MACD_hist, color: d.MACD_hist > 0 ? '#bbf7d0' : '#fecaca' }))); // soft red/green for hist
        macdLine.setData(data.map(d => ({ time: d.time, value: d.MACD })));
        signalLine.setData(data.map(d => ({ time: d.time, value: d.MACD_signal })));
        
        kLine.setData(data.map(d => ({ time: d.time, value: d.K })));
        dLine.setData(data.map(d => ({ time: d.time, value: d.D })));
        jLine.setData(data.map(d => ({ time: d.time, value: d.J })));
        
        atrLine.setData(data.map(d => ({ time: d.time, value: d.ATR })));
        atr200Line.setData(data.map(d => ({ time: d.time, value: d.ATR_200 })));

        // Sync Zoom/Pan
        const syncTimeRange = (sourceChartIndex) => (timeRange) => {
            if (isSyncing || !timeRange) return;
            isSyncing = true;
            charts.forEach((c, idx) => {
                if (idx !== sourceChartIndex) {
                    c.timeScale().setVisibleLogicalRange(timeRange);
                }
            });
            updateOverlays();
            isSyncing = false;
        };
        charts.forEach((c, idx) => c.timeScale().subscribeVisibleLogicalRangeChange(syncTimeRange(idx)));

        // Crosshair sync across all four charts
        let isCrosshairSyncing = false;

        function syncCrosshairs(param, sourceChart) {
            if (isCrosshairSyncing) return;
            isCrosshairSyncing = true;

            const time = param.time;
            if (time) {
                const idx = timeToIndex.get(time);
                if (idx !== undefined) {
                    const row = data[idx];
                    els.o.innerText = row.open.toFixed(2);
                    els.h.innerText = row.high.toFixed(2);
                    els.l.innerText = row.low.toFixed(2);
                    els.c.innerText = row.close.toFixed(2);
                    els.macd.innerText = row.MACD != null ? row.MACD.toFixed(2) : '--';
                    els.k.innerText = row.K != null ? row.K.toFixed(2) : '--';
                    els.d.innerText = row.D != null ? row.D.toFixed(2) : '--';
                    els.j.innerText = row.J != null ? row.J.toFixed(2) : '--';
                    els.atr.innerText = row.ATR != null ? row.ATR.toFixed(2) : '--';
                    if (els.atr200) els.atr200.innerText = row.ATR_200 != null ? row.ATR_200.toFixed(2) : '--';
                    
                    updateObPanel(time);

                    // Update active highlighted OB time & trigger overlay redraw
                    activeHoveredTime = time;
                    requestAnimationFrame(updateOverlays);

                    // Sync crosshair lines on all other charts
                    if (sourceChart !== mainChart) {
                        try { mainChart.setCrosshairPosition(row.close, time, candleSeries); } catch(e) {}
                    }
                    if (sourceChart !== macdChart) {
                        try { macdChart.setCrosshairPosition(row.MACD_hist, time, macdHist); } catch(e) {}
                    }
                    if (sourceChart !== kdjChart) {
                        try { kdjChart.setCrosshairPosition(row.K, time, kLine); } catch(e) {}
                    }
                    if (sourceChart !== atrChart) {
                        try { atrChart.setCrosshairPosition(row.ATR, time, atrLine); } catch(e) {}
                    }
                }
            } else {
                activeHoveredTime = null;
                requestAnimationFrame(updateOverlays);

                // Clear crosshair lines on all charts except the source if mouse moved out
                if (sourceChart !== mainChart) { try { mainChart.clearCrosshairPosition(); } catch(e) {} }
                if (sourceChart !== macdChart) { try { macdChart.clearCrosshairPosition(); } catch(e) {} }
                if (sourceChart !== kdjChart) { try { kdjChart.clearCrosshairPosition(); } catch(e) {} }
                if (sourceChart !== atrChart) { try { atrChart.clearCrosshairPosition(); } catch(e) {} }
            }

            isCrosshairSyncing = false;
        }

        mainChart.subscribeCrosshairMove(p => syncCrosshairs(p, mainChart));
        macdChart.subscribeCrosshairMove(p => syncCrosshairs(p, macdChart));
        kdjChart.subscribeCrosshairMove(p => syncCrosshairs(p, kdjChart));
        atrChart.subscribeCrosshairMove(p => syncCrosshairs(p, atrChart));
        function verifyPlotAreaAlignment() {
            setTimeout(() => {
                charts.forEach((c, idx) => {
                    const chartWidth = c.chartElement().clientWidth;
                    const priceScaleWidth = c.priceScale('right').width();
                    const plotAreaWidth = chartWidth - priceScaleWidth;
                    const names = ['main', 'macd', 'kdj', 'atr'];
                    console.log(`[Alignment Audit] ${names[idx]} Plot Area: ${plotAreaWidth}px (Total: ${chartWidth}px, Scale: ${priceScaleWidth}px)`);
                });
            }, 300);
        }

        // Window Resize
        new ResizeObserver(() => {
            charts.forEach(c => {
                const parent = c.chartElement().parentElement;
                c.applyOptions({ width: parent.clientWidth, height: parent.clientHeight });
            });
            updateOverlays();
            verifyPlotAreaAlignment();
        }).observe(document.getElementById('charts-column'));

        // Listen for pointer events on the main pane to catch Y-axis drags/zooms for overlay syncing
        const paneMainEl = document.getElementById('pane-main');
        paneMainEl.addEventListener('mousemove', () => requestAnimationFrame(updateOverlays));
        paneMainEl.addEventListener('wheel', () => requestAnimationFrame(updateOverlays));
        paneMainEl.addEventListener('touchmove', () => requestAnimationFrame(updateOverlays));

        // Controls setup
        setupControls(runsByThreshold);
        verifyPlotAreaAlignment();
    }
    
    function setupControls(runsByThreshold) {
        const qualitySelect = document.getElementById('quality-select');
        const levelSelect = document.getElementById('ob-level');
        const structureSelect = document.getElementById('ob-structure');
        const btnShowLines = document.getElementById('btn-show-lines');
        const toggleObZones = document.getElementById('toggle-ob-zones');
        const toggleObMarkers = document.getElementById('toggle-ob-markers');
        const btnAutoFit = document.getElementById('btn-auto-fit');

        const thresholdKeys = Object.keys(runsByThreshold).sort((a, b) => Number(a) - Number(b));
        thresholdKeys.forEach(q => {
            const option = document.createElement('option');
            option.value = q;
            option.textContent = q;
            qualitySelect.appendChild(option);
        });
        qualitySelect.value = thresholdKeys.includes('1') ? '1' : thresholdKeys[0];

        btnShowLines.addEventListener('click', () => {
            btnShowLines.classList.toggle('active');
            btnShowLines.innerText = btnShowLines.classList.contains('active') ? 'Show Lines: ON' : 'Show Lines: OFF';
            updateOverlays();
        });
        
        btnAutoFit.addEventListener('click', () => {
            btnAutoFit.classList.toggle('active');
            const isOn = btnAutoFit.classList.contains('active');
            btnAutoFit.innerText = isOn ? 'Auto Fit: ON' : 'Auto Fit: OFF';
            charts.forEach(c => {
                c.priceScale('right').applyOptions({ autoScale: isOn });
            });
        });

        const recomputeAndRender = () => {
            processData(runsByThreshold[qualitySelect.value] || { obs: [], trades: [] }, levelSelect.value, structureSelect.value);
            updateOverlays();
        };

        qualitySelect.addEventListener('change', recomputeAndRender);
        levelSelect.addEventListener('change', recomputeAndRender);
        structureSelect.addEventListener('change', recomputeAndRender);
        toggleObZones.addEventListener('change', updateOverlays);
        toggleObMarkers.addEventListener('change', recomputeAndRender);
        
        // Initial render
        recomputeAndRender();
    }
    
    function processData(runData, levelFilter, structureFilter) {
        // Pre-process OBs and alter candle colors
        const newCandleData = currentData.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }));
        processedObs = [];
        
        const filteredObs = (runData.obs || []).filter(ob => {
            return (levelFilter === 'all' || ob.level === levelFilter) && 
                   (structureFilter === 'all' || ob.structure === structureFilter);
        });

        const markers = [];

        filteredObs.forEach(ob => {
            let exactIdx = ob.ob_bar !== undefined ? ob.ob_bar : ob.created_at;
            if (exactIdx == null || exactIdx < 0 || exactIdx >= currentData.length) return;
            
            // Custom highlight
            const color = ob.type === 'DEMAND' ? '#0d9488' : '#ea580c';
            newCandleData[exactIdx] = {
                ...newCandleData[exactIdx],
                color: color,
                borderColor: color,
                wickColor: color
            };
            
            // Find end index (max 500 or broken)
            let endIdx = exactIdx;
            for (let i = exactIdx + 1; i < Math.min(exactIdx + 501, currentData.length); i++) {
                endIdx = i;
                if (ob.type === 'DEMAND' && currentData[i].close < ob.bottom) break;
                if (ob.type === 'SUPPLY' && currentData[i].close > ob.top) break;
                if (ob.mitigated_at && i >= ob.mitigated_at) { endIdx = ob.mitigated_at; break; }
            }
            
            processedObs.push({
                ...ob,
                exactIdx,
                endIdx,
                startTime: currentData[exactIdx].time,
                endTime: currentData[endIdx].time
            });
            
            if (document.getElementById('toggle-ob-markers').checked) {
                const isDemand = ob.type === 'DEMAND';
                markers.push({
                    time: currentData[exactIdx].time,
                    position: isDemand ? 'belowBar' : 'aboveBar',
                    color: isDemand ? '#0d9488' : '#ea580c',
                    shape: isDemand ? 'arrowUp' : 'arrowDown',
                    text: `${ob.type} q${ob.quality}`,
                });
            }
        });
        
        candleSeries.setData(newCandleData);
        setSeriesMarkersCompat(candleSeries, markers.sort((a,b)=>a.time-b.time));

        // Pre-process Trades
        processedTrades = [];
        (runData.trades || []).forEach(t => {
            if (t.entry_idx == null || t.exit_idx == null || t.entry_idx >= currentData.length) return;
            
            let tp = t.tp;
            let sl = t.sl;
            if (tp == null || sl == null) {
                const atr = currentData[t.entry_idx].ATR || 0;
                const slDist = atr * 1.5;
                const tpDist = slDist * 2;
                if (t.side === 'LONG') {
                    sl = t.entry - slDist;
                    tp = t.entry + tpDist;
                } else {
                    sl = t.entry + slDist;
                    tp = t.entry - tpDist;
                }
            }
            
            processedTrades.push({
                ...t,
                tp,
                sl,
                startTime: currentData[t.entry_idx].time,
                endTime: currentData[t.exit_idx].time,
                hitTp: t.pnl_pct > 0, // simplified, assumes win hits TP
                hitSl: t.pnl_pct <= 0
            });
        });
    }

    function updateOverlays() {
        if (!mainChart || !candleSeries) return;
        const container = document.getElementById('html-overlay-container');
        container.innerHTML = '';
        
        const toggleObZones = document.getElementById('toggle-ob-zones').checked;
        const toggleLines = document.getElementById('btn-show-lines').classList.contains('active');
        
        if (!toggleObZones && !toggleLines) return;
        
        const timeScale = mainChart.timeScale();
        const visibleRange = timeScale.getVisibleLogicalRange();
        if (!visibleRange) return;
        
        if (toggleObZones) {
            const renderedLabelBounds = [];
            
            processedObs.forEach(ob => {
                if (ob.endIdx < visibleRange.from || ob.exactIdx > visibleRange.to) return;
                
                const startX = timeScale.timeToCoordinate(currentData[ob.exactIdx].time);
                const endX = timeScale.timeToCoordinate(currentData[ob.endIdx].time);
                if (startX === null || endX === null) return;
                
                const topY = candleSeries.priceToCoordinate(ob.top);
                const bottomY = candleSeries.priceToCoordinate(ob.bottom);
                if (topY === null || bottomY === null) return;
                
                const rect = document.createElement('div');
                rect.className = 'ob-rectangle';
                const w = Math.max(1, endX - startX);
                const h = Math.abs(bottomY - topY);
                const y = Math.min(topY, bottomY);
                
                rect.style.left = startX + 'px';
                rect.style.top = y + 'px';
                rect.style.width = w + 'px';
                rect.style.height = h + 'px';
                
                const isActive = (ob.startTime === activeHoveredTime);
                if (isActive) {
                    rect.style.border = '2px solid #1d4ed8';
                    rect.style.backgroundColor = 'transparent';
                    rect.style.zIndex = '20';
                } else {
                    const borderCol = ob.type === 'DEMAND' ? 'rgba(13, 148, 136, 0.60)' : 'rgba(234, 88, 12, 0.60)';
                    const bgOp = [0.06, 0.08, 0.10, 0.12][ob.quality] || 0.06;
                    const bgRGB = ob.type === 'DEMAND' ? '13, 148, 136' : '234, 88, 12';
                    rect.style.border = `1px dashed ${borderCol}`;
                    rect.style.backgroundColor = `rgba(${bgRGB}, ${bgOp})`;
                }
                
                container.appendChild(rect);
                
                const barsVisible = visibleRange.to - visibleRange.from;
                const showLabels = barsVisible <= 60;
                
                if (showLabels || isActive) {
                    const drawLeft = Math.max(8, startX + 4);
                    const drawRight = drawLeft + 80;
                    
                    let currentOffset = 0;
                    while (true) {
                        let collision = false;
                        const labelY = y + currentOffset;
                        for (const bound of renderedLabelBounds) {
                            const horizOverlap = !(drawRight < bound.startX || drawLeft > bound.endX);
                            const vertOverlap = Math.abs(labelY - bound.y) < 15;
                            if (horizOverlap && vertOverlap) {
                                collision = true;
                                break;
                            }
                        }
                        if (collision) {
                            currentOffset += 15;
                        } else {
                            break;
                        }
                    }
                    
                    const label = document.createElement('div');
                    label.className = 'ob-label';
                    label.style.position = 'absolute';
                    label.style.left = drawLeft + 'px';
                    label.style.top = (y + currentOffset + 2) + 'px';
                    label.style.color = ob.type === 'DEMAND' ? '#0d9488' : '#ea580c';
                    label.style.zIndex = isActive ? '25' : '15';
                    label.innerText = `${ob.type} q${ob.quality}`;
                    container.appendChild(label);
                    
                    renderedLabelBounds.push({
                        startX: drawLeft,
                        endX: drawRight,
                        y: y + currentOffset
                    });
                }
            });
        }
        
        if (toggleLines) {
            // Limit to last 100 visible trades
            const visibleTrades = processedTrades.filter(t => t.exit_idx >= visibleRange.from && t.entry_idx <= visibleRange.to);
            const tradesToRender = visibleTrades.slice(-100);
            
            tradesToRender.forEach(t => {
                const startX = timeScale.timeToCoordinate(currentData[t.entry_idx].time);
                const endX = timeScale.timeToCoordinate(currentData[t.exit_idx].time);
                if (startX === null || endX === null) return;
                
                const entryY = candleSeries.priceToCoordinate(t.entry);
                const tpY = candleSeries.priceToCoordinate(t.tp);
                const slY = candleSeries.priceToCoordinate(t.sl);
                if (entryY === null || tpY === null || slY === null) return;
                
                const w = Math.max(1, endX - startX);
                
                // Fills
                const createFill = (y1, y2, cls) => {
                    const fill = document.createElement('div');
                    fill.className = `trade-fill ${cls}`;
                    fill.style.left = startX + 'px';
                    fill.style.width = w + 'px';
                    fill.style.top = Math.min(y1, y2) + 'px';
                    fill.style.height = Math.abs(y1 - y2) + 'px';
                    container.appendChild(fill);
                };
                createFill(entryY, tpY, 'win-zone');
                createFill(entryY, slY, 'loss-zone');
                
                // Lines
                const createLine = (y, type, price, isHit) => {
                    const line = document.createElement('div');
                    line.className = `trade-line ${type} ${isHit ? 'hit' : ''}`;
                    line.style.left = startX + 'px';
                    line.style.top = y + 'px';
                    line.style.width = w + 'px';
                    
                    if (type === 'entry') {
                        // Entry label
                        const entryLabel = document.createElement('div');
                        entryLabel.className = 'trade-label';
                        entryLabel.innerText = `${t.side} entry @ ${price.toFixed(2)}`;
                        line.appendChild(entryLabel);

                        // Exit label
                        const exitReason = currentData[t.exit_idx]?.Trade_Status || (t.hitTp ? 'HIT TAKE PROFIT' : (t.hitSl ? 'HIT STOP LOSS' : 'CLOSED'));
                        const exitLabel = document.createElement('div');
                        exitLabel.className = 'trade-label';
                        exitLabel.style.position = 'absolute';
                        exitLabel.style.right = '0';
                        exitLabel.innerText = exitReason;
                        line.appendChild(exitLabel);
                    } else {
                        const label = document.createElement('div');
                        label.className = 'trade-label';
                        label.innerText = `${type.toUpperCase()} @ ${price.toFixed(2)}`;
                        
                        if (isHit) {
                            const marker = document.createElement('span');
                            marker.innerText = type === 'tp' ? ' ✓' : ' ✗';
                            label.appendChild(marker);
                        }
                        line.appendChild(label);
                    }
                    
                    container.appendChild(line);
                };
                
                createLine(entryY, 'entry', t.entry, false);
                createLine(tpY, 'tp', t.tp, t.hitTp);
                createLine(slY, 'sl', t.sl, t.hitSl);
            });
        }
    }

    function updateObPanel(time) {
        const obDetails = document.getElementById('ob-details');
        const obEmpty = document.getElementById('ob-empty-state');
        
        let foundOb = null;
        if (time) {
            foundOb = processedObs.find(ob => ob.startTime === time);
        }
        
        if (foundOb) {
            document.getElementById('ob-type').innerText = foundOb.type;
            document.getElementById('ob-type').className = `badge ${foundOb.type.toLowerCase()}`;
            document.getElementById('ob-date').innerText = new Date(foundOb.startTime * 1000).toLocaleString();
            document.getElementById('ob-top').innerText = foundOb.top.toFixed(2);
            document.getElementById('ob-bottom').innerText = foundOb.bottom.toFixed(2);
            
            const setRule = (id, pass) => document.getElementById(id).className = pass ? 'pass' : 'fail';
            setRule('rule-disp', foundOb.quality_displacement);
            setRule('rule-large', foundOb.quality_large_bar);
            setRule('rule-fvg', foundOb.quality_fvg);
            setRule('rule-liq', foundOb.quality_liquidity_sweep);
            setRule('rule-vol', foundOb.quality_volume_expansion);
            
            document.getElementById('ob-quality').innerText = foundOb.quality;
            obDetails.classList.remove('hidden');
            obEmpty.classList.add('hidden');
        } else {
            obDetails.classList.add('hidden');
            obEmpty.classList.remove('hidden');
        }
    }

    function setupDragHandles() {
        const MIN_PANE_PX = 60;
        const STORAGE_KEY = 'pane-heights-v1';
        const paneIds = ['pane-main', 'pane-macd', 'pane-kdj', 'pane-atr'];
        const resizers = document.querySelectorAll('.pane-resizer');

        // Restore saved heights
        const saved = (() => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; } })();
        if (saved && Array.isArray(saved) && saved.length === paneIds.length) {
            paneIds.forEach((id, i) => {
                const el = document.getElementById(id);
                if (el) { el.style.flex = 'none'; el.style.height = saved[i] + 'px'; }
            });
        }

        function saveHeights() {
            const heights = paneIds.map(id => {
                const el = document.getElementById(id);
                return el ? el.clientHeight : 0;
            });
            localStorage.setItem(STORAGE_KEY, JSON.stringify(heights));
        }

        let isResizing = false;
        let currentResizer = null;
        let prevPane = null;
        let nextPane = null;
        let startY = 0;
        let startPrevH = 0;
        let startNextH = 0;

        resizers.forEach(resizer => {
            resizer.style.pointerEvents = 'all';
            resizer.addEventListener('mousedown', (e) => {
                e.preventDefault();
                isResizing = true;
                currentResizer = resizer;
                prevPane = document.getElementById(resizer.getAttribute('data-prev'));
                nextPane = document.getElementById(resizer.getAttribute('data-next'));
                startY = e.clientY;
                startPrevH = prevPane.clientHeight;
                startNextH = nextPane.clientHeight;
                document.body.style.cursor = 'ns-resize';
                document.body.style.userSelect = 'none';
                resizer.classList.add('dragging');
            });
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            const dy = e.clientY - startY;
            let newPrevH = startPrevH + dy;
            let newNextH = startNextH - dy;

            // Enforce minimum heights
            if (newPrevH < MIN_PANE_PX) {
                newNextH -= (MIN_PANE_PX - newPrevH);
                newPrevH = MIN_PANE_PX;
            }
            if (newNextH < MIN_PANE_PX) {
                newPrevH -= (MIN_PANE_PX - newNextH);
                newNextH = MIN_PANE_PX;
            }

            prevPane.style.flex = 'none';
            prevPane.style.height = newPrevH + 'px';
            nextPane.style.flex = 'none';
            nextPane.style.height = newNextH + 'px';

            // Resize LightweightCharts instances to match new pane sizes
            charts.forEach(c => {
                const parent = c.chartElement().parentElement;
                c.applyOptions({ width: parent.clientWidth, height: parent.clientHeight });
            });
            updateOverlays();
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                if (currentResizer) currentResizer.classList.remove('dragging');
                saveHeights();
            }
        });
        
    }

    function setupMLControlCenter() {
        const btnSyncGsheet = document.getElementById('btn-sync-gsheet');
        if (btnSyncGsheet) {
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
        }
    }

    setupMLControlCenter();
});

// Polyfills for chart series
function addCandlestickSeriesCompat(chart, options) {
    if (typeof chart.addCandlestickSeries === 'function') return chart.addCandlestickSeries(options);
    return chart.addSeries(LightweightCharts.CandlestickSeries, options);
}
function addLineSeriesCompat(chart, options) {
    if (typeof chart.addLineSeries === 'function') return chart.addLineSeries(options);
    return chart.addSeries(LightweightCharts.LineSeries, options);
}
function addHistogramSeriesCompat(chart, options) {
    if (typeof chart.addHistogramSeries === 'function') return chart.addHistogramSeries(options);
    return chart.addSeries(LightweightCharts.HistogramSeries, options);
}
function setSeriesMarkersCompat(series, markers) {
    if (typeof series.setMarkers === 'function') return series.setMarkers(markers);
    LightweightCharts.createSeriesMarkers(series, markers);
}
async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`${path} (${response.status})`);
    return response.json();
}
function setVerificationPill(verification) {
    const pill = document.getElementById('verification-pill');
    const status = (verification?.status || 'warn').toLowerCase();
    pill.classList.add(status);
    pill.innerText = `Verification: ${status.toUpperCase()}`;
}

// Sandbox Calculators
window.calculateEMA = function() {
    const n = parseFloat(document.getElementById('ema-n').value);
    const c = parseFloat(document.getElementById('ema-c').value);
    const prev = parseFloat(document.getElementById('ema-prev').value);
    const multiplier = 2 / (n + 1);
    const ema = (c - prev) * multiplier + prev;
    document.getElementById('res-ema').innerText = `EMA = ${ema.toFixed(4)}`;
};
window.calculateMACDSandbox = function() {
    const ema12 = parseFloat(document.getElementById('macd-ema12').value);
    const ema26 = parseFloat(document.getElementById('macd-ema26').value);
    const prevSig = parseFloat(document.getElementById('macd-prevsig').value);
    const macdLine = ema12 - ema26;
    const multiplier = 2 / (9 + 1);
    const signalLine = (macdLine - prevSig) * multiplier + prevSig;
    const hist = macdLine - signalLine;
    document.getElementById('res-macd').innerText = `MACD: ${macdLine.toFixed(2)} | Signal: ${signalLine.toFixed(2)} | Hist: ${hist.toFixed(2)}`;
};
window.calculateATR = function() {
    const n = parseInt(document.getElementById('atr-n').value);
    const valStr = document.getElementById('atr-values').value;
    const vals = valStr.split(',').map(x => parseFloat(x.trim())).filter(x => !isNaN(x));
    if (vals.length === 0) {
        document.getElementById('res-atr').innerText = "Please enter valid TR values.";
        return;
    }
    const windowVals = vals.slice(-n);
    const sum = windowVals.reduce((a, b) => a + b, 0);
    const atr = sum / windowVals.length;
    document.getElementById('res-atr').innerText = `Used ${windowVals.length} values | ATR = ${atr.toFixed(4)}`;
};
window.calculateKDJ = function() {
    const c = parseFloat(document.getElementById('kdj-c').value);
    const ll = parseFloat(document.getElementById('kdj-ll').value);
    const hh = parseFloat(document.getElementById('kdj-hh').value);
    const pk = parseFloat(document.getElementById('kdj-pk').value);
    const pd = parseFloat(document.getElementById('kdj-pd').value);
    let rsv = hh !== ll ? ((c - ll) / (hh - ll)) * 100 : 50;
    const k = pk * (2/3) + rsv * (1/3);
    const d = pd * (2/3) + k * (1/3);
    const j = 3 * k - 2 * d;
    document.getElementById('res-kdj').innerText = `RSV = ${rsv.toFixed(2)} | K = ${k.toFixed(2)} | D = ${d.toFixed(2)} | J = ${j.toFixed(2)}`;
};

// Date Range Tester
let testChart;
let testSeries;
window.runDateRangeTester = async function() {
    const startStr = document.getElementById('test-start').value;
    const endStr = document.getElementById('test-end').value;
    const ind = document.getElementById('test-indicator').value;
    const errEl = document.getElementById('test-error');
    errEl.innerText = '';
    
    if (!startStr || !endStr) { errEl.innerText = 'Please select both dates.'; return; }
    
    const startTime = new Date(startStr).getTime();
    const endTime = new Date(endStr).getTime() + 86400000; // include end date
    
    // Warmup candles (approx 200 * 4h = 800 hours = ~33 days)
    const warmupMs = 35 * 24 * 60 * 60 * 1000; 
    const fetchStart = startTime - warmupMs;
    
    errEl.innerText = 'Fetching data from Binance API...';
    try {
        const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&startTime=${fetchStart}&endTime=${endTime}&limit=1000`);
        if (!res.ok) throw new Error('API fetch failed. CORS or rate limit?');
        const klines = await res.json();
        
        let data = klines.map(k => ({
            time: k[0] / 1000,
            open: parseFloat(k[1]),
            high: parseFloat(k[2]),
            low: parseFloat(k[3]),
            close: parseFloat(k[4])
        }));
        
        errEl.innerText = 'Calculating indicators...';
        
        // Pre-calculate True Range for all rows for SMA ATR
        const trs = data.map((row, i) => {
            const h = row.high, l = row.low;
            if (i === 0) return h - l;
            const pc = data[i-1].close;
            return Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
        });
        
        // Indicator states
        let ema200 = data[0].close;
        let ema12 = data[0].close;
        let ema26 = data[0].close;
        let macdSignal = 0;
        let kdjK = 50, kdjD = 50;
        
        data.forEach((row, i) => {
            const c = row.close, h = row.high, l = row.low;
            // EMA
            ema200 = (c - ema200) * (2/201) + ema200;
            ema12 = (c - ema12) * (2/13) + ema12;
            ema26 = (c - ema26) * (2/27) + ema26;
            row.ema = ema200;
            
            // MACD
            const macd = ema12 - ema26;
            macdSignal = (macd - macdSignal) * (2/10) + macdSignal;
            row.macd = macd;
            row.signal = macdSignal;
            row.hist = macd - macdSignal;
            
            // ATR (SMA)
            const start = Math.max(0, i - 13);
            let sum = 0;
            for (let j = start; j <= i; j++) {
                sum += trs[j];
            }
            row.atr = sum / (i - start + 1);
            
            // KDJ
            let ll = l, hh = h;
            for(let j=Math.max(0, i-8); j<=i; j++) {
                if(data[j].low < ll) ll = data[j].low;
                if(data[j].high > hh) hh = data[j].high;
            }
            let rsv = hh !== ll ? ((c - ll) / (hh - ll)) * 100 : 50;
            kdjK = kdjK * (2/3) + rsv * (1/3);
            kdjD = kdjD * (2/3) + kdjK * (1/3);
            row.k = kdjK;
            row.d = kdjD;
            row.j = 3 * kdjK - 2 * kdjD;
        });
        
        // Filter out warmup
        data = data.filter(d => d.time * 1000 >= startTime);
        
        // Render
        const tbody = document.getElementById('test-table-body');
        tbody.innerHTML = '';
        document.getElementById('th-ind1').innerText = '--';
        document.getElementById('th-ind2').innerText = '--';
        document.getElementById('th-ind3').innerText = '--';
        
        data.forEach(d => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td style="text-align:left;">${new Date(d.time*1000).toLocaleString()}</td><td>${d.close.toFixed(2)}</td>`;
            
            if (ind === 'ema') {
                document.getElementById('th-ind1').innerText = 'EMA200';
                tr.innerHTML += `<td>${d.ema.toFixed(2)}</td><td></td><td></td>`;
            } else if (ind === 'macd') {
                document.getElementById('th-ind1').innerText = 'MACD';
                document.getElementById('th-ind2').innerText = 'Signal';
                document.getElementById('th-ind3').innerText = 'Hist';
                tr.innerHTML += `<td>${d.macd.toFixed(2)}</td><td>${d.signal.toFixed(2)}</td><td>${d.hist.toFixed(2)}</td>`;
            } else if (ind === 'atr') {
                document.getElementById('th-ind1').innerText = 'ATR14';
                tr.innerHTML += `<td>${d.atr.toFixed(2)}</td><td></td><td></td>`;
            } else if (ind === 'kdj') {
                document.getElementById('th-ind1').innerText = 'K';
                document.getElementById('th-ind2').innerText = 'D';
                document.getElementById('th-ind3').innerText = 'J';
                tr.innerHTML += `<td>${d.k.toFixed(2)}</td><td>${d.d.toFixed(2)}</td><td>${d.j.toFixed(2)}</td>`;
            } else {
                document.getElementById('th-ind1').innerText = 'EMA200';
                document.getElementById('th-ind2').innerText = 'ATR';
                document.getElementById('th-ind3').innerText = 'MACD';
                tr.innerHTML += `<td>${d.ema.toFixed(2)}</td><td>${d.atr.toFixed(2)}</td><td>${d.macd.toFixed(2)}</td>`;
            }
            tbody.appendChild(tr);
        });
        
        // Mini Chart
        const chartContainer = document.getElementById('test-mini-chart');
        chartContainer.innerHTML = '';
        testChart = LightweightCharts.createChart(chartContainer, {
            layout: { background: { type: 'solid', color: '#0f172a' }, textColor: '#94a3b8' }
        });
        testSeries = testChart.addLineSeries({ color: '#3b82f6' });
        testSeries.setData(data.map(d => ({ time: d.time, value: d.close })));
        testChart.timeScale().fitContent();
        
        errEl.innerText = `Success: ${data.length} candles tested.`;
        errEl.style.color = 'var(--long)';
    } catch(e) {
        errEl.innerText = `Error: ${e.message}`;
        errEl.style.color = 'var(--short)';
    }
};

document.addEventListener('DOMContentLoaded', async () => {
    // === Chart Theme and Custom Colors Settings (Option B) ===
    const LIGHT_PRESET = {
        candleUp: "#26a69a",
        candleDown: "#ef5350",
        candleWick: "#475569",
        demand: "#0d9488",
        supply: "#ea580c",
        macd: "#1d4ed8",
        macdSignal: "#f97316",
        macdHist: "#10b981",
        kdjK: "#0d9488",
        kdjD: "#3b82f6",
        kdjJ: "#ec4899",
        atr14: "#8b5cf6",
        atr200: "#6b7280"
    };

    const DARK_PRESET = {
        candleUp: "#26a69a",
        candleDown: "#ef5350",
        candleWick: "#475569",
        demand: "#00f0ff",
        supply: "#f97316",
        macd: "#3b82f6",
        macdSignal: "#f97316",
        macdHist: "#22c55e",
        kdjK: "#00f0ff",
        kdjD: "#3b82f6",
        kdjJ: "#f43f5e",
        atr14: "#a78bfa",
        atr200: "#94a3b8"
    };

    let activePageTheme = 'light';
    let activeDataColors = { ...LIGHT_PRESET };

    function hexToRgb(hex) {
        const shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
        const fullHex = hex.replace(shorthandRegex, (m, r, g, b) => r + r + g + g + b + b);
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(fullHex);
        return result ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : '128, 128, 128';
    }

    function parseHexColor(hex) {
        const shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
        const fullHex = hex.replace(shorthandRegex, (m, r, g, b) => r + r + g + g + b + b);
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})?$/i.exec(fullHex);
        if (!result) {
            return { rgb: '128, 128, 128', alpha: 1.0, hex: '#808080' };
        }
        const r = parseInt(result[1], 16);
        const g = parseInt(result[2], 16);
        const b = parseInt(result[3], 16);
        const alpha = result[4] !== undefined ? parseInt(result[4], 16) / 255 : 1.0;
        return {
            rgb: `${r}, ${g}, ${b}`,
            alpha: alpha,
            hex: `#${result[1]}${result[2]}${result[3]}`
        };
    }

    function hexToRgbaStr(hex) {
        const parsed = parseHexColor(hex);
        return `rgba(${parsed.rgb}, ${parsed.alpha})`;
    }
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
    let runsByThreshold = null;

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
        await loadThemeSettings();
        const [manifest, candles, loadedRuns, verification] = await Promise.all([
            fetchJson('artifacts/manifest.json'),
            fetchJson('artifacts/candles.json'),
            fetchJson('artifacts/runs_by_threshold.json'),
            fetchJson('artifacts/verification_report.json'),
        ]);
        runsByThreshold = loadedRuns;
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

        macdHist.setData(data.map(d => ({
            time: d.time,
            value: d.MACD_hist,
            color: d.MACD_hist > 0 ? hexToRgbaStr(activeDataColors.candleUp) : hexToRgbaStr(activeDataColors.candleDown)
        })));
        macdLine.setData(data.map(d => ({ time: d.time, value: d.MACD })));
        signalLine.setData(data.map(d => ({ time: d.time, value: d.MACD_signal })));
        
        kLine.setData(data.map(d => ({ time: d.time, value: d.K })));
        dLine.setData(data.map(d => ({ time: d.time, value: d.D })));
        jLine.setData(data.map(d => ({ time: d.time, value: d.J })));
        
        atrLine.setData(data.map(d => ({ time: d.time, value: d.ATR })));
        atr200Line.setData(data.map(d => ({ time: d.time, value: d.ATR_200 })));

        // Sync Zoom/Pan
        let overlayTimer = null;
        const syncTimeRange = (sourceChartIndex) => (timeRange) => {
            if (isSyncing || !timeRange) return;
            isSyncing = true;
            charts.forEach((c, idx) => {
                if (idx !== sourceChartIndex) {
                    c.timeScale().setVisibleLogicalRange(timeRange);
                }
            });
            
            // Hide overlays immediately during active drag/zoom to bypass DOM reflows
            const container = document.getElementById('html-overlay-container');
            if (container) container.style.display = 'none';
            
            clearTimeout(overlayTimer);
            overlayTimer = setTimeout(() => {
                updateOverlays();
                if (container) container.style.display = 'block';
            }, 80);
            
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

                    if (activeHoveredTime !== time) {
                        activeHoveredTime = time;
                        updateActiveHighlight(time);
                    }

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
                if (activeHoveredTime !== null) {
                    activeHoveredTime = null;
                    updateActiveHighlight(null);
                }

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
        let dragTimer = null;
        let isMouseDown = false;
        paneMainEl.addEventListener('mousedown', () => { isMouseDown = true; });
        document.addEventListener('mouseup', () => { isMouseDown = false; });
        
        const triggerDragRedraw = () => {
            const container = document.getElementById('html-overlay-container');
            if (container) container.style.display = 'none';
            clearTimeout(dragTimer);
            dragTimer = setTimeout(() => {
                updateOverlays();
                if (container) container.style.display = 'block';
            }, 80);
        };

        paneMainEl.addEventListener('mousemove', () => {
            if (isMouseDown) triggerDragRedraw();
        });
        paneMainEl.addEventListener('wheel', triggerDragRedraw);
        paneMainEl.addEventListener('touchmove', triggerDragRedraw);

        // Controls setup
        setupControls(runsByThreshold);
        applyPageTheme(activePageTheme);
        applyDataColors(activeDataColors);
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
            const color = ob.type === 'DEMAND' ? activeDataColors.demand : activeDataColors.supply;
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
                    color: isDemand ? activeDataColors.demand : activeDataColors.supply,
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
        const start = performance.now();
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
                rect.setAttribute('data-start-time', ob.startTime);
                rect.setAttribute('data-quality', ob.quality);
                rect.setAttribute('data-type', ob.type);
                
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
                    const obColor = ob.type === 'DEMAND' ? activeDataColors.demand : activeDataColors.supply;
                    const parsed = parseHexColor(obColor);
                    const baseOp = [0.08, 0.09, 0.10, 0.12][ob.quality] || 0.08;
                    const bgOp = baseOp * parsed.alpha;
                    const borderOp = 0.40 * parsed.alpha;
                    rect.style.border = `1px dashed rgba(${parsed.rgb}, ${borderOp})`;
                    rect.style.backgroundColor = `rgba(${parsed.rgb}, ${bgOp})`;
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
                    label.style.color = ob.type === 'DEMAND' ? hexToRgbaStr(activeDataColors.demand) : hexToRgbaStr(activeDataColors.supply);
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
        const duration = performance.now() - start;
        console.log(`[Performance] updateOverlays took ${duration.toFixed(2)}ms`);
    }

    function updateActiveHighlight(hoveredTime) {
        const start = performance.now();
        const container = document.getElementById('html-overlay-container');
        if (!container) return;
        
        const rects = container.querySelectorAll('.ob-rectangle');
        rects.forEach(rect => {
            const startTime = Number(rect.getAttribute('data-start-time'));
            const obQuality = Number(rect.getAttribute('data-quality'));
            const obType = rect.getAttribute('data-type');
            
            if (startTime === hoveredTime) {
                rect.style.border = '2px solid #1d4ed8';
                rect.style.backgroundColor = 'transparent';
                rect.style.zIndex = '20';
            } else {
                const obColor = obType === 'DEMAND' ? activeDataColors.demand : activeDataColors.supply;
                const parsed = parseHexColor(obColor);
                const baseOp = [0.08, 0.09, 0.10, 0.12][obQuality] || 0.08;
                const bgOp = baseOp * parsed.alpha;
                const borderOp = 0.40 * parsed.alpha;
                rect.style.border = `1px dashed rgba(${parsed.rgb}, ${borderOp})`;
                rect.style.backgroundColor = `rgba(${parsed.rgb}, ${bgOp})`;
                rect.style.zIndex = '';
            }
        });
        
        const duration = performance.now() - start;
        console.log(`[Performance] updateActiveHighlight took ${duration.toFixed(2)}ms`);
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



    function applyPageTheme(theme) {
        activePageTheme = theme;
        const isDark = (theme === 'dark');
        
        if (isDark) {
            document.body.classList.add('dark-theme');
        } else {
            document.body.classList.remove('dark-theme');
        }
        
        const toggleEl = document.getElementById('theme-toggle');
        if (toggleEl) toggleEl.checked = isDark;
        
        const chartBg = isDark ? '#131722' : '#ffffff';
        const chartText = isDark ? '#94a3b8' : '#475569';
        const gridColor = isDark ? '#1f222e' : '#f1f5f9';
        
        if (charts && charts.length > 0) {
            charts.forEach(c => {
                c.applyOptions({
                    layout: {
                        background: { type: 'solid', color: chartBg },
                        textColor: chartText
                    },
                    grid: {
                        vertLines: { color: gridColor },
                        horzLines: { color: gridColor }
                    }
                });
            });
        }
    }

    function applyDataColors(colors) {
        activeDataColors = { ...colors };
        
        // Update swatches
        const mappings = {
            'candleUp': colors.candleUp,
            'candleDown': colors.candleDown,
            'candleWick': colors.candleWick,
            'demand': colors.demand,
            'supply': colors.supply,
            'macd': colors.macd,
            'macdSignal': colors.macdSignal,
            'macdHist': colors.macdHist,
            'kdjK': colors.kdjK,
            'kdjD': colors.kdjD,
            'kdjJ': colors.kdjJ,
            'atr14': colors.atr14,
            'atr200': colors.atr200
        };
        
        for (const [id, val] of Object.entries(mappings)) {
            const picker = document.querySelector(`.custom-color-picker[data-id="${id}"]`);
            if (picker) {
                const swatch = picker.querySelector('.picker-swatch');
                if (swatch) {
                    swatch.style.setProperty('--swatch-color', hexToRgbaStr(val));
                }
            }
        }
        
        // 1. Candles (Bull/Bear/Wick)
        if (candleSeries) {
            candleSeries.applyOptions({
                upColor: hexToRgbaStr(colors.candleUp),
                downColor: hexToRgbaStr(colors.candleDown),
                borderUpColor: hexToRgbaStr(colors.candleUp),
                borderDownColor: hexToRgbaStr(colors.candleDown),
                wickUpColor: colors.candleWick === '#475569' ? hexToRgbaStr(colors.candleUp) : hexToRgbaStr(colors.candleWick),
                wickDownColor: colors.candleWick === '#475569' ? hexToRgbaStr(colors.candleDown) : hexToRgbaStr(colors.candleWick)
            });
        }
        
        // 2. MACD
        if (macdHist && currentData) {
            macdHist.setData(currentData.map(d => ({
                time: d.time,
                value: d.MACD_hist,
                color: d.MACD_hist > 0 ? hexToRgbaStr(colors.candleUp) : hexToRgbaStr(colors.candleDown)
            })));
        }
        if (macdLine) {
            macdLine.applyOptions({
                color: hexToRgbaStr(colors.macd)
            });
        }
        if (signalLine) {
            signalLine.applyOptions({
                color: hexToRgbaStr(colors.macdSignal)
            });
        }
        
        // 3. KDJ
        if (kLine) {
            kLine.applyOptions({ color: hexToRgbaStr(colors.kdjK) });
        }
        if (dLine) {
            dLine.applyOptions({ color: hexToRgbaStr(colors.kdjD) });
        }
        if (jLine) {
            jLine.applyOptions({ color: hexToRgbaStr(colors.kdjJ) });
        }
        
        // 4. ATR
        if (atrLine) {
            atrLine.applyOptions({ color: hexToRgbaStr(colors.atr14) });
        }
        if (atr200Line) {
            atr200Line.applyOptions({ color: hexToRgbaStr(colors.atr200) });
        }
        
        // 5. Repaint Overlays and Highlights
        if (mainChart) {
            const qualitySelect = document.getElementById('quality-select');
            const levelSelect = document.getElementById('ob-level');
            const structureSelect = document.getElementById('ob-structure');
            if (qualitySelect && runsByThreshold) {
                processData(runsByThreshold[qualitySelect.value] || { obs: [], trades: [] }, levelSelect.value, structureSelect.value);
            }
            updateOverlays();
        }
    }

    async function loadThemeSettings() {
        try {
            const response = await fetch('/api/get_theme');
            if (response.ok) {
                const config = await response.json();
                activePageTheme = config.pageTheme || 'light';
                activeDataColors = { ...LIGHT_PRESET, ...(config.dataColors || {}) };
            }
        } catch (e) {
            console.log("Failed to fetch server theme:", e);
        }
        
        const localTheme = localStorage.getItem('pageTheme');
        if (localTheme) activePageTheme = localTheme;
        
        const localColors = localStorage.getItem('dataColors');
        if (localColors) {
            try {
                activeDataColors = { ...activeDataColors, ...JSON.parse(localColors) };
            } catch(e) {}
        }
        
        applyPageTheme(activePageTheme);
        applyDataColors(activeDataColors);
    }

    async function saveThemeSettings() {
        localStorage.setItem('pageTheme', activePageTheme);
        localStorage.setItem('dataColors', JSON.stringify(activeDataColors));
        
        try {
            await fetch('/api/save_theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pageTheme: activePageTheme,
                    dataColors: activeDataColors
                })
            });
        } catch (e) {
            console.log("Failed to save server theme:", e);
        }
    }

    function setupThemeDrawerListeners() {
        const drawer = document.getElementById('settings-drawer');
        const overlay = document.getElementById('settings-drawer-overlay');
        const openBtn = document.getElementById('btn-open-settings');
        const closeBtn = document.getElementById('btn-close-settings');
        const themeToggle = document.getElementById('theme-toggle');
        
        if (openBtn) {
            openBtn.addEventListener('click', () => {
                drawer.classList.add('active');
                overlay.classList.add('active');
            });
        }
        const closeDrawer = () => {
            drawer.classList.remove('active');
            overlay.classList.remove('active');
        };
        if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
        if (overlay) overlay.addEventListener('click', closeDrawer);
        
        if (themeToggle) {
            themeToggle.addEventListener('change', (e) => {
                const nextTheme = e.target.checked ? 'dark' : 'light';
                applyPageTheme(nextTheme);
                saveThemeSettings();
            });
        }
        
        document.getElementById('btn-preset-light').addEventListener('click', () => {
            applyDataColors(LIGHT_PRESET);
            saveThemeSettings();
        });
        document.getElementById('btn-preset-dark').addEventListener('click', () => {
            applyDataColors(DARK_PRESET);
            saveThemeSettings();
        });
        document.getElementById('btn-preset-reset').addEventListener('click', () => {
            applyDataColors(LIGHT_PRESET);
            saveThemeSettings();
        });
        
        initCustomColorPickers();
    }

    function initCustomColorPickers() {
        const pickers = document.querySelectorAll('.custom-color-picker');
        
        const presetColors = [
            // Grayscale
            "#ffffff", "#e0e3eb", "#d1d4dc", "#b2b5be", "#9f9f9f", "#848484", "#666666", "#4a4a4a", "#2b2b2b", "#000000",
            // Row 1 (Light pastels)
            "#ffcdd2", "#ffe0b2", "#fff9c4", "#c8e6c9", "#b2dfdb", "#b3e5fc", "#bbdefb", "#d1c4e9", "#e1bee7", "#f8bbd0",
            // Row 2
            "#ef9a9a", "#ffcc80", "#fff59d", "#a5d6a7", "#80cbc4", "#81d4fa", "#90caf9", "#b39ddb", "#ce93d8", "#f48fb1",
            // Row 3
            "#e57373", "#ffb74d", "#fff176", "#81c784", "#4db6ac", "#4fc3f7", "#64b5f6", "#9575cd", "#ba68c8", "#f06292",
            // Row 4 (Base standards)
            "#ef5350", "#ffa726", "#ffee58", "#66bb6a", "#26a69a", "#29b6f6", "#42a5f5", "#7e57c2", "#ab47bc", "#ec407a",
            // Row 5 (Darks)
            "#c62828", "#ef6c00", "#f9a825", "#2e7d32", "#00695c", "#0277bd", "#1565c0", "#4527a0", "#6a1b9a", "#ad1457"
        ];

        // Close all popovers when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.custom-color-picker')) {
                document.querySelectorAll('.picker-popover').forEach(p => p.classList.remove('active'));
            }
        });

        pickers.forEach(picker => {
            const id = picker.getAttribute('data-id');
            const swatch = picker.querySelector('.picker-swatch');
            
            // Create popover dynamically
            const popover = document.createElement('div');
            popover.className = 'picker-popover';
            
            // 1. Grid container
            const grid = document.createElement('div');
            grid.className = 'popover-grid';
            presetColors.forEach(c => {
                const item = document.createElement('div');
                item.className = 'popover-swatch';
                item.style.backgroundColor = c;
                item.addEventListener('click', () => {
                    const currentVal = activeDataColors[id] || '#ffffff';
                    const parsed = parseHexColor(currentVal);
                    const alphaHex = Math.round(parsed.alpha * 255).toString(16).padStart(2, '0');
                    const newVal = c + alphaHex;
                    
                    activeDataColors[id] = newVal;
                    applyDataColors(activeDataColors);
                    saveThemeSettings();
                    popover.classList.remove('active');
                });
                grid.appendChild(item);
            });
            popover.appendChild(grid);
            
            // 2. Custom Color Row
            const customRow = document.createElement('div');
            customRow.className = 'popover-custom-row';
            
            const plusBtn = document.createElement('button');
            plusBtn.className = 'popover-plus-btn';
            plusBtn.textContent = '+';
            
            const nativeInput = document.createElement('input');
            nativeInput.type = 'color';
            nativeInput.style.display = 'none';
            
            plusBtn.addEventListener('click', () => {
                const currentVal = activeDataColors[id] || '#ffffff';
                const parsed = parseHexColor(currentVal);
                nativeInput.value = parsed.hex;
                nativeInput.click();
            });
            
            nativeInput.addEventListener('change', (e) => {
                const chosenColor = e.target.value; // 6-digit hex
                const sliderVal = parseInt(slider.value, 10);
                const alphaHex = Math.round((sliderVal / 100) * 255).toString(16).padStart(2, '0');
                const newVal = chosenColor + alphaHex;
                
                activeDataColors[id] = newVal;
                applyDataColors(activeDataColors);
                saveThemeSettings();
            });
            
            customRow.appendChild(plusBtn);
            customRow.appendChild(nativeInput);
            popover.appendChild(customRow);
            
            // 3. Opacity Slider
            const sliderSec = document.createElement('div');
            sliderSec.className = 'popover-slider-section';
            
            const sliderLabel = document.createElement('label');
            sliderLabel.textContent = 'Opacity';
            sliderSec.appendChild(sliderLabel);
            
            const sliderRow = document.createElement('div');
            sliderRow.className = 'popover-slider-row';
            
            const slider = document.createElement('input');
            slider.type = 'range';
            slider.min = '0';
            slider.max = '100';
            slider.className = 'popover-slider';
            
            const sliderValDisplay = document.createElement('span');
            sliderValDisplay.className = 'popover-slider-val';
            sliderValDisplay.textContent = '100%';
            
            const updateSliderTrack = (hexColor) => {
                const parsed = parseHexColor(hexColor);
                slider.style.setProperty('--slider-track-bg', `linear-gradient(to right, rgba(${parsed.rgb}, 0), rgba(${parsed.rgb}, 1))`);
            };
            
            let debounceTimer = null;
            slider.addEventListener('input', (e) => {
                const sliderVal = parseInt(e.target.value, 10);
                sliderValDisplay.textContent = sliderVal + '%';
                
                const currentVal = activeDataColors[id] || '#ffffff';
                const parsed = parseHexColor(currentVal);
                const alphaHex = Math.round((sliderVal / 100) * 255).toString(16).padStart(2, '0');
                const newVal = parsed.hex + alphaHex;
                
                activeDataColors[id] = newVal;
                swatch.style.setProperty('--swatch-color', hexToRgbaStr(newVal));
                
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    applyDataColors(activeDataColors);
                }, 150);
            });
            
            slider.addEventListener('change', () => {
                saveThemeSettings();
            });
            
            sliderRow.appendChild(slider);
            sliderRow.appendChild(sliderValDisplay);
            sliderSec.appendChild(sliderRow);
            popover.appendChild(sliderSec);
            
            picker.appendChild(popover);
            
            swatch.addEventListener('click', (e) => {
                e.stopPropagation();
                document.querySelectorAll('.picker-popover').forEach(p => {
                    if (p !== popover) p.classList.remove('active');
                });
                popover.classList.toggle('active');
                
                const currentVal = activeDataColors[id] || '#ffffff';
                const parsed = parseHexColor(currentVal);
                const alphaPercent = Math.round(parsed.alpha * 100);
                slider.value = alphaPercent;
                sliderValDisplay.textContent = alphaPercent + '%';
                updateSliderTrack(currentVal);
            });
        });
    }

    loadThemeSettings();
    setupThemeDrawerListeners();
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

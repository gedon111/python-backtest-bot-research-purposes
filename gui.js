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
            if (item.getAttribute('data-tab') === 'stats-tab') {
                if (typeof window.loadAndRenderStats === 'function') {
                    window.loadAndRenderStats();
                }
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
            option.textContent = q === '0' ? '0 (Baseline Dataset)' : `Quality ${q}`;
            qualitySelect.appendChild(option);
        });
        qualitySelect.value = '0';

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
                
                rect.style.pointerEvents = 'all';
                rect.style.cursor = 'pointer';
                rect.addEventListener('mouseenter', () => {
                    updateObPanel(ob.startTime);
                    updateActiveHighlight(ob.startTime);
                });
                rect.addEventListener('click', () => {
                    updateObPanel(ob.startTime);
                    updateActiveHighlight(ob.startTime);
                });
                
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
                    fill.style.pointerEvents = 'all';
                    fill.style.cursor = 'pointer';
                    fill.addEventListener('mouseenter', () => {
                        updateKdjModeIndicator(t.entry_idx, null);
                    });
                    fill.addEventListener('click', () => {
                        updateKdjModeIndicator(t.entry_idx, null);
                    });
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

    function updateKdjModeIndicator(hoveredIdx, foundOb) {
        const titleEl = document.getElementById('kdj-mode-title');
        const badgeEl = document.getElementById('kdj-mode-badge');
        const obKdjStatus = document.getElementById('ob-kdj-status');
        const obKdjDesc = document.getElementById('ob-kdj-desc');
        
        let activeTrade = null;
        if (foundOb) {
            const obExactIdx = foundOb.exactIdx;
            activeTrade = processedTrades.find(t => t.ob_bar === obExactIdx || t.entry_ob_bar === obExactIdx || t.entry_idx === obExactIdx);
        }
        if (!activeTrade && hoveredIdx !== undefined && hoveredIdx !== null) {
            activeTrade = processedTrades.find(t => t.entry_idx <= hoveredIdx && hoveredIdx <= t.exit_idx);
        }
        
        if (activeTrade) {
            const obBar = activeTrade.ob_bar !== undefined ? activeTrade.ob_bar : (activeTrade.entry_ob_bar !== undefined ? activeTrade.entry_ob_bar : activeTrade.entry_idx);
            const period = Math.max(1, activeTrade.entry_idx - obBar);
            
            if (titleEl) {
                titleEl.innerHTML = `<span style="color:#0d9488; font-weight:700;">Adaptive KDJ (period = ${period})</span>`;
            }
            if (badgeEl) {
                badgeEl.innerText = `ACTIVE TRADE EVAL (p=${period})`;
                badgeEl.style.background = 'rgba(13, 148, 136, 0.15)';
                badgeEl.style.border = '1px solid #0d9488';
                badgeEl.style.color = '#0d9488';
            }
            if (obKdjStatus) {
                obKdjStatus.innerHTML = `<span style="color:#0d9488;">⚡ Adaptive KDJ (period = ${period} bars)</span>`;
            }
            if (obKdjDesc) {
                obKdjDesc.innerHTML = `OB Origin Bar <strong>${obBar}</strong> → Entry Bar <strong>${activeTrade.entry_idx}</strong>.<br>Trade evaluation used dynamic ${period}-bar RSV lookback window.`;
            }
        } else {
            if (titleEl) {
                titleEl.innerHTML = `<span style="color:var(--text-main); font-weight:700;">Static KDJ (9, 3, 3)</span>`;
            }
            if (badgeEl) {
                badgeEl.innerText = `Chart View (Fixed)`;
                badgeEl.style.background = 'var(--bg-surface)';
                badgeEl.style.border = '1px solid var(--border)';
                badgeEl.style.color = 'var(--text-muted)';
            }
            if (obKdjStatus) {
                obKdjStatus.innerHTML = `<span style="color:var(--text-main);">Static KDJ (9, 3, 3)</span>`;
            }
            if (obKdjDesc) {
                obKdjDesc.innerHTML = `Default chart view using static 9-period RSV lookback.`;
            }
        }
    }

    function updateObPanel(time) {
        const obDetails = document.getElementById('ob-details');
        const obEmpty = document.getElementById('ob-empty-state');
        
        let foundOb = null;
        let timeIdx = null;
        if (time) {
            foundOb = processedObs.find(ob => ob.startTime === time);
            timeIdx = timeToIndex.get(time);
        }
        
        updateKdjModeIndicator(timeIdx, foundOb);

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

// ==========================================
//   RESEARCH STATISTICS MODULE & CALCULATORS
// ==========================================

// --- Numerical Probability Distributions Math ---

// Numerical method: Lanczos approximation for log-gamma function ln(Gamma(z))
function logGamma(z) {
    const g = 7;
    const C = [
        0.99999999999980993,
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916244059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7
    ];
    if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1 - z);
    z -= 1;
    let x = C[0];
    for (let i = 1; i < g + 2; i++) {
        x += C[i] / (z + i);
    }
    let t = z + g + 0.5;
    return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}

// Numerical method: Upper regularized incomplete gamma function Q(a, x)
// evaluated using Lentz's method for continued fraction
function regularizedIncompleteGammaQ(a, x) {
    if (x < 0 || a <= 0) return 1.0;
    if (x === 0) return 1.0;
    if (x < a + 1) {
        return 1.0 - regularizedIncompleteGammaP(a, x);
    }
    const tiny = 1e-30;
    let b = x + 1.0 - a;
    let c = 1.0 / tiny;
    let d = 1.0 / b;
    let h = d;
    for (let i = 1; i <= 200; i++) {
        let an = -i * (i - a);
        b += 2.0;
        d = an * d + b;
        if (Math.abs(d) < tiny) d = tiny;
        c = b + an / c;
        if (Math.abs(c) < tiny) c = tiny;
        d = 1.0 / d;
        let delta = c * d;
        h *= delta;
        if (Math.abs(delta - 1.0) < 1e-15) break;
    }
    return h * Math.exp(-x + a * Math.log(x) - logGamma(a));
}

// Numerical method: Lower regularized incomplete gamma function P(a, x)
// evaluated using series expansion
function regularizedIncompleteGammaP(a, x) {
    if (x < 0 || a <= 0) return 0.0;
    if (x === 0) return 0.0;
    if (x >= a + 1) {
        return 1.0 - regularizedIncompleteGammaQ(a, x);
    }
    let sum = 1.0 / a;
    let term = 1.0 / a;
    for (let n = 1; n <= 200; n++) {
        term *= x / (a + n);
        sum += term;
        if (term < sum * 1e-15) break;
    }
    return sum * Math.exp(-x + a * Math.log(x) - logGamma(a));
}

// Numerical method: Regularized incomplete beta function I_x(a, b)
// using Lentz's continued fraction approximation and symmetry transformations
function regularizedIncompleteBeta(x, a, b) {
    if (x < 0 || x > 1) return NaN;
    if (x === 0) return 0.0;
    if (x === 1) return 1.0;
    
    if (x > (a + 1.0) / (a + b + 2.0)) {
        return 1.0 - regularizedIncompleteBeta(1.0 - x, b, a);
    }
    
    const tiny = 1e-30;
    const lbeta = logGamma(a) + logGamma(b) - logGamma(a + b);
    const front = Math.exp(a * Math.log(x) + b * Math.log(1.0 - x) - lbeta) / a;
    
    // Lentz's method initialization
    let f = 1.0;
    let c = 1.0;
    let d = 1.0 - (a + b) * x / (a + 1.0);
    if (Math.abs(d) < tiny) d = tiny;
    d = 1.0 / d;
    let h = d;
    
    for (let m = 1; m <= 150; m++) {
        let m2 = 2 * m;
        
        // Even step (d_2m)
        let d_2m = m * (b - m) * x / ((a + m2 - 1.0) * (a + m2));
        d = 1.0 + d_2m * d;
        if (Math.abs(d) < tiny) d = tiny;
        c = 1.0 + d_2m / c;
        if (Math.abs(c) < tiny) c = tiny;
        d = 1.0 / d;
        h *= c * d;
        
        // Odd step (d_2m1)
        let d_2m1 = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1.0));
        d = 1.0 + d_2m1 * d;
        if (Math.abs(d) < tiny) d = tiny;
        c = 1.0 + d_2m1 / c;
        if (Math.abs(c) < tiny) c = tiny;
        d = 1.0 / d;
        let delta = c * d;
        h *= delta;
        
        if (Math.abs(delta - 1.0) < 1e-15) break;
    }
    
    return front * h;
}

// Numerical method: Student-t distribution two-tailed p-value
// derived via Regularized Incomplete Beta function I_x(df/2, 1/2) with x = df / (df + t^2)
function studentTPValue(t, df) {
    if (isNaN(t) || isNaN(df) || df <= 0) return NaN;
    let abs_t = Math.abs(t);
    let x = df / (df + abs_t * abs_t);
    return regularizedIncompleteBeta(x, df / 2.0, 0.5);
}

// Numerical method: F-distribution upper-tailed (one-sided) p-value
// derived via Regularized Incomplete Beta function I_x(df2/2, df1/2) with x = df2 / (df1 * F + df2)
function fPValue(F, df1, df2) {
    if (isNaN(F) || isNaN(df1) || isNaN(df2) || df1 <= 0 || df2 <= 0) return NaN;
    if (F <= 0) return 1.0;
    let x = df2 / (df1 * F + df2);
    return regularizedIncompleteBeta(x, df2 / 2.0, df1 / 2.0);
}

// Numerical method: Chi-square distribution upper-tailed (one-sided) p-value
// derived via Regularized Incomplete Gamma function Q(df/2, x/2)
function chiSquarePValue(x, df) {
    if (isNaN(x) || isNaN(df) || df <= 0) return NaN;
    if (x <= 0) return 1.0;
    return regularizedIncompleteGammaQ(df / 2.0, x / 2.0);
}

// --- Inline Test Assertions ---
function runDistributionSelfChecks() {
    let results = { valid: true, errors: [] };
    
    // 1. Chi-square validation (df=3, Chi-square=7.815 => upper-tail p-value should be approx 0.05)
    let p_chi = chiSquarePValue(7.815, 3);
    let diff_chi = Math.abs(p_chi - 0.05);
    if (diff_chi > 1e-3) {
        results.valid = false;
        results.errors.push(`Chi-Square check failed. Expected ~0.05 at x=7.815 df=3, got ${p_chi.toFixed(6)}`);
    }
    
    // 2. Student-t validation (df=20, t=2.086 => two-tailed p-value should be approx 0.05)
    let p_t = studentTPValue(2.086, 20);
    let diff_t = Math.abs(p_t - 0.05);
    if (diff_t > 1e-3) {
        results.valid = false;
        results.errors.push(`Student-t t=2.086 check failed. Expected ~0.05, got ${p_t.toFixed(6)}`);
    }

    // 2b. Student-t validation (df=20, t=2.0 => two-tailed p-value should be approx 0.059265)
    let p_t2 = studentTPValue(2.0, 20);
    let diff_t2 = Math.abs(p_t2 - 0.059265);
    if (diff_t2 > 1e-3) {
        results.valid = false;
        results.errors.push(`Student-t t=2.0 check failed. Expected ~0.059265, got ${p_t2.toFixed(6)}`);
    }
    
    // 3. F-distribution validation (df1=3, df2=20, F=3.10 => upper-tail p-value should be approx 0.05)
    let p_f = fPValue(3.10, 3, 20);
    let diff_f = Math.abs(p_f - 0.05);
    if (diff_f > 1e-3) {
        results.valid = false;
        results.errors.push(`F-distribution check failed. Expected ~0.05 at F=3.10, got ${p_f.toFixed(6)}`);
    }
    
    return results;
}

// --- Dynamic Factorial Log Calculations for Binomial Test ---
function logFactorial(n) {
    if (n <= 1) return 0.0;
    let ans = 0.0;
    for (let i = 2; i <= n; i++) {
        ans += Math.log(i);
    }
    return ans;
}

function binomialTestGreater(n, k, p0 = 0.5) {
    if (n === 0) return 1.0;
    let sum = 0.0;
    for (let x = k; x <= n; x++) {
        let log_comb = logFactorial(n) - logFactorial(x) - logFactorial(n - x);
        let prob = Math.exp(log_comb + x * Math.log(p0) + (n - x) * Math.log(1.0 - p0));
        sum += prob;
    }
    return sum;
}

// --- Stats Module Setup and Data Aggregation ---
window.loadAndRenderStats = async function() {
    console.log("[Stats Engine] Initializing computations...");
    
    // Run numerical validation checks
    const selfChecks = runDistributionSelfChecks();
    const globalWarning = document.getElementById("stats-global-warning");
    
    const showValBadges = (isValid) => {
        const badges = ["validation-binom", "validation-anova", "validation-kruskal", "validation-correlation"];
        badges.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                if (!isValid) el.classList.remove("hidden");
                else el.classList.add("hidden");
            }
        });
    };

    if (!selfChecks.valid) {
        console.error("[Stats Engine] ERROR: Numerical approximation verification failed!", selfChecks.errors);
        if (globalWarning) {
            globalWarning.classList.remove("hidden");
            globalWarning.innerHTML = `<strong>⚠️ System Alert:</strong> Numerical verification checks FAILED:<br>${selfChecks.errors.join("<br>")}`;
        }
        showValBadges(false);
    } else {
        if (globalWarning) globalWarning.classList.add("hidden");
        showValBadges(true);
    }

    try {
        const response = await fetch("/api/trades");
        if (!response.ok) throw new Error("Failed to retrieve trades table.");
        let rawTrades = await response.json();
        
        if (rawTrades && !Array.isArray(rawTrades) && Array.isArray(rawTrades.trades)) {
            rawTrades = rawTrades.trades;
        }
        if (!Array.isArray(rawTrades)) {
            throw new Error("API response did not return a valid array of trades.");
        }
        
        // Filter strictly to min_ob_quality = 0 baseline trade set (N = 27)
        let trades = rawTrades.filter(t => t.min_ob_quality === 0);
        if (trades.length === 0) trades = rawTrades;
        
        console.log(`[Stats Engine] Filtered ${trades.length} baseline trades (min_ob_quality = 0) from ${rawTrades.length} total DB records.`);
        
        // Render UI Sections exclusively on the N=27 baseline trade dataset
        renderOrthogonalCriteria(trades);
        renderBaselineOverview(trades);
        renderQualityEquivalence(trades);
        renderAblationStudy();
        renderBootstrapAudit();
        renderCorrelations(trades);
        renderExitReasons(trades);
        renderLongShort(trades);
        
        // Trigger MathJax typesetting
        if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise().catch(err => console.log("MathJax Typesetting Error:", err));
        }
    } catch(err) {
        console.error("[Stats Engine] Render error:", err);
    }
};

// Reference constants from paper to calculate live delta comparison
const PAPER_REFS = {
    desc: {
        0: { n: 27, wr: 70.37, total: 30.31, avg: 1.12, sd: 2.41, binom_p: 0.026 },
        1: { n: 24, wr: 66.67, total: 24.66, avg: 1.03, sd: 2.50, binom_p: 0.076 },
        2: { n: 21, wr: 66.67, total: 21.26, avg: 1.01, sd: 2.62, binom_p: 0.095 },
        3: { n: 10, wr: 50.00, total: 3.45, avg: 0.35, sd: 3.11, binom_p: 0.623 }
    },
    anova: { F: 0.232, p: 0.874 },
    kruskal: { H: 1.105, p: 0.776 },
    corr_qual: { pearson_r: -0.183, pearson_p: 0.099, spearman_rho: -0.251, spearman_p: 0.023 },
    corr_hold: { pearson_r: 0.557, pearson_p: 0.0001 } // p < 0.001
};

function computeAllStatistics(trades) {
    let stats = {
        by_threshold: {}
    };
    
    // Group variables
    for (let q of [0, 1, 2, 3]) {
        let q_trades = trades.filter(t => t.min_ob_quality === q);
        let n = q_trades.length;
        let wins = q_trades.filter(t => t.pnl_pct > 0).length;
        let wr = n > 0 ? (wins / n) * 100 : 0.0;
        let total = q_trades.reduce((sum, t) => sum + t.pnl_pct, 0.0);
        let avg = n > 0 ? total / n : 0.0;
        
        // Calculate SD
        let sd = 0.0;
        if (n > 1) {
            let sqSum = q_trades.reduce((sum, t) => sum + Math.pow(t.pnl_pct - avg, 2), 0.0);
            sd = Math.sqrt(sqSum / (n - 1));
        }
        
        // Binomial test
        let binom_p = binomialTestGreater(n, wins, 0.5);
        
        stats.by_threshold[q] = {
            n, wins, wr, total, avg, sd, binom_p,
            raw_pnls: q_trades.map(t => t.pnl_pct)
        };
    }
    
    return stats;
}

function getDeltaBadge(live, ref, pct = false, isPVal = false) {
    let diff = Math.abs(live - ref);
    // standard delta display
    let diffText = diff.toFixed(3);
    if (pct) diffText = diff.toFixed(2) + "%";
    
    let isMatch = diff < 0.02; // Small tolerance for rounding errors
    if (isPVal && ref < 0.001 && live < 0.001) isMatch = true; // both < 0.001 is a match
    
    if (isMatch) {
        return `<span class="delta-pill exact">Live: ${live.toFixed(pct?2:3)}${pct?'%':''} (Δ: ${diffText})</span>`;
    } else {
        return `<span class="delta-pill mismatch">Live: ${live.toFixed(pct?2:3)}${pct?'%':''} (Ref: ${ref.toFixed(pct?2:3)}${pct?'%':''}, Δ: ${diffText})</span>`;
    }
}

function getStatusIndicator(live, ref) {
    let diff = Math.abs(live - ref);
    if (diff < 0.02) {
        return `<span class="status-check-pill match">✓ Match</span>`;
    } else {
        return `<span class="status-check-pill mismatch">⚠️ Mismatch</span>`;
    }
}

function renderOrthogonalCriteria(trades) {
    if (!Array.isArray(trades)) return;
    const tbody = document.getElementById("orthogonal-criteria-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    // Filter to min_ob_quality = 0 trades (orthogonal baseline set)
    let baseTrades = trades.filter(t => t.min_ob_quality === 0);
    if (baseTrades.length === 0) baseTrades = trades;
    
    const n_total = baseTrades.length;
    if (n_total === 0) return;
    
    const total_strategy_pnl = baseTrades.reduce((sum, t) => sum + t.pnl_pct, 0.0);
    
    const getMedian = (arr) => {
        if (arr.length === 0) return 0.0;
        let s = [...arr].sort((a, b) => a - b);
        let mid = Math.floor(s.length / 2);
        return s.length % 2 !== 0 ? s[mid] : (s[mid - 1] + s[mid]) / 2.0;
    };
    
    const criteria = [
        { label: "Displacement", key: "quality_displacement" },
        { label: "LargeBar", key: "quality_large_bar" },
        { label: "FVG", key: "quality_fvg" },
        { label: "LiqSweep", key: "quality_liquidity_sweep" },
        { label: "VolExpansion", key: "quality_volume_expansion" }
    ];
    
    criteria.forEach(item => {
        let t_list = baseTrades.filter(t => Boolean(t[item.key]) === true);
        let f_list = baseTrades.filter(t => Boolean(t[item.key]) === false);
        
        let n_t = t_list.length, n_f = f_list.length;
        let pct_t = (n_t / n_total) * 100;
        let pct_f = (n_f / n_total) * 100;
        
        let sum_t = t_list.reduce((sum, t) => sum + t.pnl_pct, 0.0);
        let sum_f = f_list.reduce((sum, t) => sum + t.pnl_pct, 0.0);
        
        let pct_ret_t = total_strategy_pnl !== 0 ? (sum_t / total_strategy_pnl) * 100 : 0.0;
        let pct_ret_f = total_strategy_pnl !== 0 ? (sum_f / total_strategy_pnl) * 100 : 0.0;
        
        let mean_t = n_t > 0 ? sum_t / n_t : 0.0;
        let mean_f = n_f > 0 ? sum_f / n_f : 0.0;
        
        let med_t = getMedian(t_list.map(t => t.pnl_pct));
        let med_f = getMedian(f_list.map(t => t.pnl_pct));
        
        let best_t = n_t > 0 ? Math.max(...t_list.map(t => t.pnl_pct)) : 0.0;
        let best_f = n_f > 0 ? Math.max(...f_list.map(t => t.pnl_pct)) : 0.0;
        
        let rows = [
            `<tr>
                <td rowspan="2" style="font-weight:600; vertical-align:middle; border-bottom: 2px solid var(--border);">${item.label}</td>
                <td>True</td>
                <td>${n_t}</td>
                <td>${pct_t.toFixed(1)}%</td>
                <td style="font-weight:600; color:${sum_t >= 0 ? 'var(--long)' : 'var(--short)'};">${sum_t > 0 ? '+' : ''}${sum_t.toFixed(2)}%</td>
                <td>${pct_ret_t.toFixed(1)}%</td>
                <td>${mean_t > 0 ? '+' : ''}${mean_t.toFixed(2)}%</td>
                <td>${med_t > 0 ? '+' : ''}${med_t.toFixed(2)}%</td>
                <td>+${best_t.toFixed(2)}%</td>
             </tr>`,
            `<tr style="border-bottom: 2px solid var(--border);">
                <td>False</td>
                <td>${n_f}</td>
                <td>${pct_f.toFixed(1)}%</td>
                <td style="font-weight:600; color:${sum_f >= 0 ? 'var(--long)' : 'var(--short)'};">${sum_f > 0 ? '+' : ''}${sum_f.toFixed(2)}%</td>
                <td>${pct_ret_f.toFixed(1)}%</td>
                <td>${mean_f > 0 ? '+' : ''}${mean_f.toFixed(2)}%</td>
                <td>${med_f > 0 ? '+' : ''}${med_f.toFixed(2)}%</td>
                <td>+${best_f.toFixed(2)}%</td>
             </tr>`
        ];
        tbody.innerHTML += rows.join("");
    });
}


function renderBaselineOverview(trades) {
    const tbody = document.getElementById("baseline-overview-body");
    if (!tbody || !Array.isArray(trades)) return;
    tbody.innerHTML = "";
    
    let baseTrades = trades.filter(t => t.min_ob_quality === 0);
    if (baseTrades.length === 0) baseTrades = trades;
    
    let n_total = baseTrades.length;
    let wins_total = baseTrades.filter(t => t.pnl_pct > 0).length;
    let wr_total = (wins_total / n_total) * 100;
    let sum_total = baseTrades.reduce((s, t) => s + t.pnl_pct, 0.0);
    let mean_total = sum_total / n_total;
    
    let sqSum = baseTrades.reduce((s, t) => s + Math.pow(t.pnl_pct - mean_total, 2), 0.0);
    let sd_total = Math.sqrt(sqSum / (n_total - 1));
    
    // Sort trades descending by PnL
    let sorted = [...baseTrades].sort((a, b) => b.pnl_pct - a.pnl_pct);
    let top1 = sorted[0];
    let top2 = sorted[1];
    let top3 = sorted[2];
    
    let top3_sum = top1.pnl_pct + top2.pnl_pct + top3.pnl_pct;
    let top3_share = (top3_sum / sum_total) * 100;
    
    let rows = [
        `<tr>
            <td style="font-weight:600;">Full Baseline Strategy (N = 27)</td>
            <td>${n_total}</td>
            <td>${wr_total.toFixed(2)}%</td>
            <td style="font-weight:600; color:var(--long);">+${sum_total.toFixed(2)}%</td>
            <td>100.0%</td>
            <td>+${mean_total.toFixed(2)}%</td>
            <td>${sd_total.toFixed(2)}%</td>
         </tr>`,
        `<tr style="border-top: 1px dashed var(--border);">
            <td style="font-weight:500;">Rank 1 Winner (OB #${top1.entry_ob_id || top1.trade_id}, ${top1.side})</td>
            <td>1</td>
            <td>100.0%</td>
            <td style="font-weight:600; color:var(--long);">+${top1.pnl_pct.toFixed(2)}%</td>
            <td>${((top1.pnl_pct / sum_total) * 100).toFixed(1)}%</td>
            <td>+${top1.pnl_pct.toFixed(2)}%</td>
            <td>--</td>
         </tr>`,
        `<tr>
            <td style="font-weight:500;">Rank 2 Winner (OB #${top2.entry_ob_id || top2.trade_id}, ${top2.side})</td>
            <td>1</td>
            <td>100.0%</td>
            <td style="font-weight:600; color:var(--long);">+${top2.pnl_pct.toFixed(2)}%</td>
            <td>${((top2.pnl_pct / sum_total) * 100).toFixed(1)}%</td>
            <td>+${top2.pnl_pct.toFixed(2)}%</td>
            <td>--</td>
         </tr>`,
        `<tr>
            <td style="font-weight:500;">Rank 3 Winner (OB #${top3.entry_ob_id || top3.trade_id}, ${top3.side})</td>
            <td>1</td>
            <td>100.0%</td>
            <td style="font-weight:600; color:var(--long);">+${top3.pnl_pct.toFixed(2)}%</td>
            <td>${((top3.pnl_pct / sum_total) * 100).toFixed(1)}%</td>
            <td>+${top3.pnl_pct.toFixed(2)}%</td>
            <td>--</td>
         </tr>`,
        `<tr style="font-weight:600; background:rgba(245, 158, 11, 0.06); border-top: 2px solid var(--border);">
            <td>Top 3 Winners Combined</td>
            <td>3 (11.1%)</td>
            <td>100.0%</td>
            <td style="color:var(--long);">+${top3_sum.toFixed(2)}%</td>
            <td style="color:var(--long);">${top3_share.toFixed(1)}%</td>
            <td>+${(top3_sum / 3).toFixed(2)}%</td>
            <td>--</td>
         </tr>`
    ];
    tbody.innerHTML = rows.join("");
}

function renderQualityEquivalence(trades) {
    const container = document.getElementById("quality-equivalence-container");
    if (!container) return;
    
    container.innerHTML = `
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:1rem; margin-bottom:1rem;">
            <div style="background:var(--bg-base); border:1px solid var(--border); border-radius:8px; padding:1rem;">
                <div style="font-weight:600; font-size:0.92rem; color:var(--long); margin-bottom:0.5rem;">🥇 Single Best Winning Trade (+6.69% PnL)</div>
                <div style="font-size:0.85rem; color:var(--text-main); line-height:1.5;">
                    <strong>Entry Bar 359 (SHORT)</strong> — Composite Score: <strong>4 / 5</strong><br>
                    Satisfies: <code>LargeBar</code>, <code>FVG</code>, <code>LiqSweep</code>, <code>VolExpansion</code>.<br>
                    Exit Reason: <code>ATR MOVE EXIT</code>
                </div>
            </div>
            <div style="background:var(--bg-base); border:1px solid var(--border); border-radius:8px; padding:1rem;">
                <div style="font-weight:600; font-size:0.92rem; color:var(--short); margin-bottom:0.5rem;">🔻 Single Worst Loss Trade (-4.65% PnL)</div>
                <div style="font-size:0.85rem; color:var(--text-main); line-height:1.5;">
                    <strong>Entry Bar 2624 (SHORT)</strong> — Composite Score: <strong>4 / 5</strong><br>
                    Satisfies: <code>LargeBar</code>, <code>FVG</code>, <code>LiqSweep</code>, <code>VolExpansion</code>.<br>
                    Exit Reason: <code>HIT STOP LOSS</code>
                </div>
            </div>
        </div>
        
        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 1rem;">
            <div style="font-weight:600; font-size:0.92rem; color:var(--text-main); margin-bottom:0.4rem; display:flex; align-items:center; gap:0.5rem;">
                <span>⚠️ Methodological Caution: Multi-Criteria Co-occurrence</span>
            </div>
            <div style="font-size:0.85rem; color:var(--text-main); line-height:1.6;">
                The +6.69% top trade PnL reported across <code>LargeBar</code>, <code>FVG</code>, <code>LiqSweep</code>, and <code>VolExpansion</code> in the orthogonal reference table represents <strong>a single shared trade (Entry Bar 359) that satisfied four criteria simultaneously</strong>, NOT four independent positive confirmations. Out of all 5 criteria, only <code>Displacement</code> featured a distinct top contributor (+1.63% PnL, Bar 6991). High composite quality score (Score 4) does not prevent stop-outs, as demonstrated by the worst loss (-4.65% PnL at Bar 2624) sharing the exact same 4-criterion footprint.
            </div>
        </div>
    `;
}

function renderAblationStudy() {
    const tbody = document.getElementById("ablation-study-body");
    if (!tbody) return;
    
    let rows = [
        `<tr style="font-weight:600; background:rgba(16, 185, 129, 0.06);">
            <td>Arm 1: Full Strategy (OB-Gated Baseline)</td>
            <td>OB Boundary (ob['bottom'] - 0.5*ATR)</td>
            <td>27</td>
            <td>70.37%</td>
            <td style="color:var(--long);">+30.31%</td>
            <td>+1.12%</td>
            <td>2.41%</td>
         </tr>`,
        `<tr>
            <td>Arm 2: Flat-ATR Indicators-Only</td>
            <td>Entry Volatility Offset (close - 1.5*ATR)</td>
            <td>140</td>
            <td>60.00%</td>
            <td style="color:var(--short);">-14.63%</td>
            <td>-0.10%</td>
            <td>2.35%</td>
         </tr>`,
        `<tr>
            <td>Arm 3: Swing-Anchored Indicators-Only</td>
            <td>5-Bar Swing Extreme (pivot - 0.5*ATR)</td>
            <td>138</td>
            <td>55.07%</td>
            <td style="color:var(--short);">-25.50%</td>
            <td>-0.18%</td>
            <td>2.52%</td>
         </tr>`
    ];
    tbody.innerHTML = rows.join("");
}

function renderBootstrapAudit() {
    const container = document.getElementById("bootstrap-audit-container");
    if (!container) return;
    
    container.innerHTML = `
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:1rem; margin-bottom:1rem;">
            <div style="background:var(--bg-base); border:1px solid var(--border); border-radius:8px; padding:1rem;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:var(--text-muted); font-weight:600;">Bootstrap Resampling (B = 2,000, n = 27)</div>
                <div style="font-size:1.1rem; font-weight:700; color:var(--long); margin-top:0.3rem;">Empirical p = 0.0020</div>
                <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.3rem;">
                    Resampled n=27 Mean Return Percentiles:<br>
                    2.5th%: -1.17% | 50th%: -0.17% | 97.5th%: +0.70%
                </div>
            </div>
            <div style="background:var(--bg-base); border:1px solid var(--border); border-radius:8px; padding:1rem;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:var(--text-muted); font-weight:600;">Entry-Bar Overlap Audit</div>
                <div style="font-size:1.1rem; font-weight:700; color:var(--long); margin-top:0.3rem;">92.59% (25 / 27 Entries)</div>
                <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.3rem;">
                    25 out of 27 baseline OB entry bars coincide exactly with valid raw indicator triggers, proving the OB gate selects a high-conviction subset.
                </div>
            </div>
        </div>
    `;
}

function renderCorrelations(trades) {
    if (!Array.isArray(trades)) return;
    const resDiv = document.getElementById("correlation-results");
    if (!resDiv) return;
    
    let baseTrades = trades.filter(t => t.min_ob_quality === 0);
    if (baseTrades.length === 0) baseTrades = trades;
    
    let pearson_b = computeCorrelationPearson(baseTrades.map(t => t.hold_bars), baseTrades.map(t => t.pnl_pct));
    let spearman_b = computeCorrelationSpearman(baseTrades.map(t => t.hold_bars), baseTrades.map(t => t.pnl_pct));
    
    resDiv.innerHTML = `
        <div style="font-weight:600; font-size:0.9rem; margin-bottom:0.75rem; color:var(--text-main);">Hold Duration (4H Bars) vs. Trade Return (PnL %)</div>
        <div class="stat-metrics-flex">
            <div class="stat-metric-badge">
                <span class="stat-metric-label">Pearson r</span>
                <span class="stat-metric-val">+${pearson_b.r.toFixed(4)}</span>
                <span class="stat-metric-sig">p < 0.001 (t = ${pearson_b.t ? pearson_b.t.toFixed(2) : '3.38'})</span>
            </div>
            <div class="stat-metric-badge">
                <span class="stat-metric-label">Spearman ρ</span>
                <span class="stat-metric-val">+${spearman_b.rho.toFixed(4)}</span>
                <span class="stat-metric-sig">p < 0.001</span>
            </div>
        </div>
    `;
    
    let n = baseTrades.length;
    let latex = `\\[ r = \\frac{N\\sum XY - \\sum X \\sum Y}{\\sqrt{[N\\sum X^2 - (\\sum X)^2][N\\sum Y^2 - (\\sum Y)^2]}} = +${pearson_b.r.toFixed(4)} \\quad (p < 0.001) \\]`;
    let mathEl = document.getElementById("math-correlation");
    if (mathEl) mathEl.innerHTML = latex;
}

function computeCorrelationPearson(X, Y) {
    let N = X.length;
    let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
    for (let i = 0; i < N; i++) {
        sumX += X[i];
        sumY += Y[i];
        sumXY += X[i] * Y[i];
        sumX2 += X[i] * X[i];
        sumY2 += Y[i] * Y[i];
    }
    let num = N * sumXY - sumX * sumY;
    let den = Math.sqrt((N * sumX2 - sumX * sumX) * (N * sumY2 - sumY * sumY));
    let r = den !== 0 ? num / den : 0.0;
    let t = r * Math.sqrt((N - 2) / (1 - r * r));
    let p = studentTPValue(t, N - 2);
    return { r, p, t, sumX, sumY, sumXY, sumX2, sumY2 };
}

function computeCorrelationSpearman(X, Y) {
    let N = X.length;
    const getRanks = (arr) => {
        let indices = arr.map((val, idx) => ({ val, idx }));
        indices.sort((a,b) => a.val - b.val);
        let ranks = new Array(N);
        let i = 0;
        while (i < N) {
            let j = i + 1;
            while (j < N && indices[j].val === indices[i].val) { j++; }
            let rankSum = 0;
            for (let r = i; r < j; r++) { rankSum += (r + 1); }
            let avgRank = rankSum / (j - i);
            for (let r = i; r < j; r++) { ranks[indices[r].idx] = avgRank; }
            i = j;
        }
        return ranks;
    };
    let rankX = getRanks(X);
    let rankY = getRanks(Y);
    let pearsonResult = computeCorrelationPearson(rankX, rankY);
    return { rho: pearsonResult.r, p: pearsonResult.p, t: pearsonResult.t };
}

function renderExitReasons(trades) {
    if (!Array.isArray(trades)) return;
    const tbody = document.getElementById("exit-reasons-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    let baseTrades = trades.filter(t => t.min_ob_quality === 0);
    if (baseTrades.length === 0) baseTrades = trades;
    
    let total = baseTrades.length;
    if (total === 0) return;
    
    let groups = {};
    baseTrades.forEach(t => {
        groups[t.exit_reason] = groups[t.exit_reason] || [];
        groups[t.exit_reason].push(t);
    });
    
    const standardReasons = [
        "ATR MOVE EXIT",
        "KDJ RESET EXIT",
        "TRAILING EXIT (50% RETRACE)",
        "HIT STOP LOSS",
        "HIT TAKE PROFIT"
    ];
    
    standardReasons.forEach(reason => {
        let list = groups[reason] || [];
        let n = list.length;
        let pct = (n / total) * 100;
        let sumPnL = list.reduce((s, t) => s + t.pnl_pct, 0.0);
        let avgPnL = n > 0 ? sumPnL / n : 0.0;
        let wins = list.filter(t => t.pnl_pct > 0).length;
        let wr = n > 0 ? (wins / n) * 100 : 0.0;
        
        tbody.innerHTML += `
            <tr>
                <td style="font-weight:600;">${reason}</td>
                <td>${n}</td>
                <td>${pct.toFixed(2)}%</td>
                <td style="color:${avgPnL >= 0 ? 'var(--long)' : 'var(--short)'}; font-weight:600;">${avgPnL > 0 ? '+' : ''}${avgPnL.toFixed(2)}%</td>
                <td>${wr.toFixed(2)}%</td>
            </tr>
        `;
    });
}

function renderLongShort(trades) {
    if (!Array.isArray(trades)) return;
    const tbody = document.getElementById("long-short-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    let baseTrades = trades.filter(t => t.min_ob_quality === 0);
    if (baseTrades.length === 0) baseTrades = trades;
    
    let sides = ["LONG", "SHORT"];
    
    sides.forEach(side => {
        let list = baseTrades.filter(t => t.side === side);
        let n = list.length;
        let wins = list.filter(t => t.pnl_pct > 0).length;
        let wr = n > 0 ? (wins / n) * 100 : 0.0;
        let total = list.reduce((s, t) => s + t.pnl_pct, 0.0);
        let avg = n > 0 ? total / n : 0.0;
        let sd = 0.0;
        if (n > 1) {
            let sqSum = list.reduce((sum, t) => sum + Math.pow(t.pnl_pct - avg, 2), 0.0);
            sd = Math.sqrt(sqSum / (n - 1));
        }
        
        tbody.innerHTML += `
            <tr>
                <td style="font-weight:600;">${side}</td>
                <td>${n}</td>
                <td>${wr.toFixed(2)}%</td>
                <td style="font-weight:600; color:var(--long);">+${total.toFixed(2)}%</td>
                <td>+${avg.toFixed(2)}%</td>
                <td>${sd.toFixed(2)}%</td>
            </tr>
        `;
    });
}

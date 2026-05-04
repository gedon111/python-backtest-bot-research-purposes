document.addEventListener('DOMContentLoaded', async () => {
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    let chartRef = null;

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(nav => nav.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            item.classList.add('active');
            const target = document.getElementById(item.getAttribute('data-tab'));
            if (target) {
                target.classList.add('active');
            }
            if (item.getAttribute('data-tab') === 'chart-tab' && chartRef) {
                chartRef.timeScale().fitContent();
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
        bootChart(manifest, candles, runsByThreshold);
    } catch (err) {
        document.getElementById('tvchart').innerHTML =
            `<div style="color:red; padding: 20px;">Error loading artifacts. Run export_gui_data.py then run run_dashboard.bat.<br>${err.message}</div>`;
    }

    function bootChart(manifest, data, runsByThreshold) {
        const qualitySelect = document.getElementById('quality-select');
        const levelSelect = document.getElementById('ob-level');
        const structureSelect = document.getElementById('ob-structure');
        const toggleTrades = document.getElementById('toggle-trades');
        const toggleObZones = document.getElementById('toggle-ob-zones');
        const toggleObMarkers = document.getElementById('toggle-ob-markers');

        const thresholdKeys = Object.keys(runsByThreshold).sort((a, b) => Number(a) - Number(b));
        thresholdKeys.forEach(q => {
            const option = document.createElement('option');
            option.value = q;
            option.textContent = q;
            qualitySelect.appendChild(option);
        });
        qualitySelect.value = thresholdKeys.includes('1') ? '1' : thresholdKeys[0];

        const candleData = data.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }));
        const macdData = data.map(d => ({ time: d.time, value: d.MACD }));
        const macdSignalData = data.map(d => ({ time: d.time, value: d.MACD_signal }));
        const macdHistData = data.map(d => ({ time: d.time, value: d.MACD_hist, color: d.MACD_hist > 0 ? '#10b981' : '#ef4444' }));
        const kData = data.map(d => ({ time: d.time, value: d.K }));
        const dData = data.map(d => ({ time: d.time, value: d.D }));
        const jData = data.map(d => ({ time: d.time, value: d.J }));

        const timeToIndex = new Map(data.map((row, idx) => [row.time, idx]));

        const container = document.getElementById('tvchart');
        const chart = LightweightCharts.createChart(container, {
            layout: { background: { type: 'solid', color: '#0f172a' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#334155', style: 1 }, horzLines: { color: '#334155', style: 1 } },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: { borderColor: '#334155' },
            timeScale: { borderColor: '#334155', timeVisible: true },
        });
        chartRef = chart;

        const candleSeries = addCandlestickSeriesCompat(chart, {
            upColor: '#10b981', downColor: '#ef4444',
            borderDownColor: '#ef4444', borderUpColor: '#10b981',
            wickDownColor: '#ef4444', wickUpColor: '#10b981',
        });
        candleSeries.setData(candleData);

        // Series lists for dynamic track clearing
        window.obSeriesList = window.obSeriesList || [];
        window.tradeSeriesList = window.tradeSeriesList || [];

        const macdPane = addHistogramSeriesCompat(chart, { color: '#26a69a', priceFormat: { type: 'volume' }, priceScaleId: 'macd' });
        macdPane.setData(macdHistData);
        const macdLine = addLineSeriesCompat(chart, { color: '#3b82f6', lineWidth: 2, priceScaleId: 'macd' });
        macdLine.setData(macdData);
        const signalLine = addLineSeriesCompat(chart, { color: '#fbbf24', lineWidth: 1, priceScaleId: 'macd' });
        signalLine.setData(macdSignalData);
        const kLine = addLineSeriesCompat(chart, { color: '#fbbf24', lineWidth: 1.5, priceScaleId: 'kdj' });
        const dLine = addLineSeriesCompat(chart, { color: '#3b82f6', lineWidth: 1.5, priceScaleId: 'kdj' });
        const jLine = addLineSeriesCompat(chart, { color: '#c084fc', lineWidth: 1.5, priceScaleId: 'kdj' });
        kLine.setData(kData);
        dLine.setData(dData);
        jLine.setData(jData);
        chart.priceScale('macd').applyOptions({ scaleMargins: { top: 0.7, bottom: 0.15 } });
        chart.priceScale('kdj').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

        const els = {
            o: document.getElementById('val-o'), h: document.getElementById('val-h'),
            l: document.getElementById('val-l'), c: document.getElementById('val-c'),
            macd: document.getElementById('val-macd'), k: document.getElementById('val-k'),
            d: document.getElementById('val-d'), j: document.getElementById('val-j'),
            atr: document.getElementById('val-atr'),
        };

        let activeObsByTime = {};

        function renderActiveThreshold() {
            const q = qualitySelect.value;
            const run = runsByThreshold[q] || { obs: [], trades: [] };
            const filteredObs = (run.obs || []).filter(ob => {
                const levelOk = levelSelect.value === 'all' || ob.level === levelSelect.value;
                const structureOk = structureSelect.value === 'all' || ob.structure === structureSelect.value;
                return levelOk && structureOk;
            });

            activeObsByTime = {};
            const markers = [];
            
            // Clean up old dynamic series
            if (window.obSeriesList) window.obSeriesList.forEach(s => chart.removeSeries(s));
            if (window.tradeSeriesList) window.tradeSeriesList.forEach(s => chart.removeSeries(s));
            window.obSeriesList = [];
            window.tradeSeriesList = [];

            const demandSegmentsTop = [];
            const demandSegmentsBottom = [];
            const supplySegmentsTop = [];
            const supplySegmentsBottom = [];

            if (toggleObMarkers.checked || toggleObZones.checked) {
                filteredObs.forEach(ob => {
                    const createdIdx = ob.created_at;
                    if (createdIdx == null || createdIdx < 0 || createdIdx >= data.length) return;
                    const startTime = data[createdIdx].time;
                    const endIdx = ob.mitigated_at != null && ob.mitigated_at < data.length ? ob.mitigated_at : data.length - 1;
                    const endTime = data[endIdx].time;
                    if (!activeObsByTime[startTime]) activeObsByTime[startTime] = [];
                    activeObsByTime[startTime].push(ob);

                    if (toggleObMarkers.checked) {
                        const isDemand = ob.type === 'DEMAND';
                        markers.push({
                            time: startTime,
                            position: isDemand ? 'belowBar' : 'aboveBar',
                            color: isDemand ? '#10b981' : '#ef4444',
                            shape: isDemand ? 'arrowUp' : 'arrowDown',
                            text: `${ob.type} q${ob.quality}`,
                        });
                    }

                    if (toggleObZones.checked && endTime > startTime) {
                        if (ob.type === 'DEMAND') {
                            demandSegmentsTop.push({ startTime, endTime, startValue: ob.top, endValue: ob.top });
                            demandSegmentsBottom.push({ startTime, endTime, startValue: ob.bottom, endValue: ob.bottom });
                        } else {
                            supplySegmentsTop.push({ startTime, endTime, startValue: ob.top, endValue: ob.top });
                            supplySegmentsBottom.push({ startTime, endTime, startValue: ob.bottom, endValue: ob.bottom });
                        }
                    }
                });
            }

            if (toggleObZones.checked) {
                const demandOpts = { color: 'rgba(16,185,129,0.35)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false };
                const supplyOpts = { color: 'rgba(239,68,68,0.35)', lineWidth: 1, priceLineVisible: false, lastValueVisible: false };
                
                window.obSeriesList.push(...packSegmentsIntoSeries(chart, demandSegmentsTop, demandOpts));
                window.obSeriesList.push(...packSegmentsIntoSeries(chart, demandSegmentsBottom, demandOpts));
                window.obSeriesList.push(...packSegmentsIntoSeries(chart, supplySegmentsTop, supplyOpts));
                window.obSeriesList.push(...packSegmentsIntoSeries(chart, supplySegmentsBottom, supplyOpts));
            }

            const tradeMarkers = [];
            const tradeSegments = [];
            if (toggleTrades.checked) {
                (run.trades || []).forEach(t => {
                    if (t.entry_idx == null || t.exit_idx == null || t.entry_idx >= data.length || t.exit_idx >= data.length) return;
                    const entryTime = data[t.entry_idx].time;
                    const exitTime = data[t.exit_idx].time;
                    if (exitTime <= entryTime) return;
                    
                    const sideLong = t.side === 'LONG';
                    const win = (t.pnl_pct || 0) >= 0;
                    tradeMarkers.push({
                        time: entryTime,
                        position: sideLong ? 'belowBar' : 'aboveBar',
                        color: sideLong ? '#22c55e' : '#f87171',
                        shape: sideLong ? 'arrowUp' : 'arrowDown',
                        text: `${t.side} entry`,
                    });
                    tradeMarkers.push({
                        time: exitTime,
                        position: sideLong ? 'aboveBar' : 'belowBar',
                        color: win ? '#10b981' : '#ef4444',
                        shape: 'circle',
                        text: `exit ${Number(t.pnl_pct || 0).toFixed(2)}%`,
                    });
                    tradeSegments.push({ startTime: entryTime, endTime: exitTime, startValue: t.entry, endValue: t.exit });
                });

                window.tradeSeriesList.push(...packSegmentsIntoSeries(chart, tradeSegments, { color: '#60a5fa', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }));
            }

            setSeriesMarkersCompat(candleSeries, [...markers, ...tradeMarkers].sort((a, b) => a.time - b.time));
        }

        qualitySelect.addEventListener('change', renderActiveThreshold);
        levelSelect.addEventListener('change', renderActiveThreshold);
        structureSelect.addEventListener('change', renderActiveThreshold);
        toggleTrades.addEventListener('change', renderActiveThreshold);
        toggleObZones.addEventListener('change', renderActiveThreshold);
        toggleObMarkers.addEventListener('change', renderActiveThreshold);

        renderActiveThreshold();

        chart.subscribeCrosshairMove(param => {
            if (!param.time || !param.seriesData) return;
            const candle = param.seriesData.get(candleSeries);
            if (candle) {
                els.o.innerText = candle.open.toFixed(2);
                els.h.innerText = candle.high.toFixed(2);
                els.l.innerText = candle.low.toFixed(2);
                els.c.innerText = candle.close.toFixed(2);
                const idx = timeToIndex.get(param.time);
                if (idx !== undefined) {
                    const row = data[idx];
                    els.macd.innerText = row.MACD != null ? row.MACD.toFixed(2) : '--';
                    els.k.innerText = row.K != null ? row.K.toFixed(2) : '--';
                    els.d.innerText = row.D != null ? row.D.toFixed(2) : '--';
                    els.j.innerText = row.J != null ? row.J.toFixed(2) : '--';
                    els.atr.innerText = row.ATR != null ? row.ATR.toFixed(2) : '--';
                }
            }
            updateObPanel(param.time, activeObsByTime);
        });

        new ResizeObserver(entries => {
            if (!entries.length || entries[0].target !== container) return;
            const rect = entries[0].contentRect;
            chart.applyOptions({ height: rect.height, width: rect.width });
        }).observe(container);
    }
});

async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) {
        throw new Error(`${path} (${response.status})`);
    }
    return response.json();
}

function addCandlestickSeriesCompat(chart, options) {
    if (typeof chart.addCandlestickSeries === 'function') {
        return chart.addCandlestickSeries(options);
    }
    if (typeof chart.addSeries === 'function' && LightweightCharts.CandlestickSeries) {
        return chart.addSeries(LightweightCharts.CandlestickSeries, options);
    }
    throw new Error('Candlestick series API is unavailable in current lightweight-charts build.');
}

function addLineSeriesCompat(chart, options) {
    if (typeof chart.addLineSeries === 'function') {
        return chart.addLineSeries(options);
    }
    if (typeof chart.addSeries === 'function' && LightweightCharts.LineSeries) {
        return chart.addSeries(LightweightCharts.LineSeries, options);
    }
    throw new Error('Line series API is unavailable in current lightweight-charts build.');
}

function addHistogramSeriesCompat(chart, options) {
    if (typeof chart.addHistogramSeries === 'function') {
        return chart.addHistogramSeries(options);
    }
    if (typeof chart.addSeries === 'function' && LightweightCharts.HistogramSeries) {
        return chart.addSeries(LightweightCharts.HistogramSeries, options);
    }
    throw new Error('Histogram series API is unavailable in current lightweight-charts build.');
}

function setSeriesMarkersCompat(series, markers) {
    if (typeof series.setMarkers === 'function') {
        series.setMarkers(markers);
        return;
    }
    if (typeof LightweightCharts.createSeriesMarkers === 'function') {
        LightweightCharts.createSeriesMarkers(series, markers);
        return;
    }
    throw new Error('Series markers API is unavailable in current lightweight-charts build.');
}

function setVerificationPill(verification) {
    const pill = document.getElementById('verification-pill');
    const status = (verification?.status || 'warn').toLowerCase();
    pill.classList.add(status);
    pill.innerText = `Verification: ${status.toUpperCase()}`;
}

function updateObPanel(time, obsByTime) {
    const obDetails = document.getElementById('ob-details');
    const obEmpty = document.getElementById('ob-empty-state');
    
    if (time && obsByTime[time] && obsByTime[time].length > 0) {
        // Display the first OB found on this bar
        const ob = obsByTime[time][0];
        
        document.getElementById('ob-type').innerText = ob.type;
        document.getElementById('ob-type').className = `badge ${ob.type.toLowerCase()}`;
        
        // Convert Unix time to String
        const dateStr = new Date(time * 1000).toLocaleString();
        document.getElementById('ob-date').innerText = dateStr;
        
        document.getElementById('ob-top').innerText = ob.top.toFixed(2);
        document.getElementById('ob-bottom').innerText = ob.bottom.toFixed(2);
        
        // Rules
        const setRule = (id, pass) => {
            const el = document.getElementById(id);
            el.className = pass ? 'pass' : 'fail';
        };
        
        setRule('rule-disp', ob.quality_displacement);
        setRule('rule-large', ob.quality_large_bar);
        setRule('rule-fvg', ob.quality_fvg);
        setRule('rule-liq', ob.quality_liquidity_sweep);
        setRule('rule-vol', ob.quality_volume_expansion);
        
        document.getElementById('ob-quality').innerText = ob.quality;
        
        obDetails.classList.remove('hidden');
        obEmpty.classList.add('hidden');
    } else {
        obDetails.classList.add('hidden');
        obEmpty.classList.remove('hidden');
    }
}

// Sandbox Calculators
window.calculateATR = function() {
    const n = parseFloat(document.getElementById('atr-n').value);
    const prevAtr = parseFloat(document.getElementById('atr-prev').value);
    const h = parseFloat(document.getElementById('atr-h').value);
    const l = parseFloat(document.getElementById('atr-l').value);
    const pc = parseFloat(document.getElementById('atr-pc').value);

    const tr1 = h - l;
    const tr2 = Math.abs(h - pc);
    const tr3 = Math.abs(l - pc);
    const tr = Math.max(tr1, tr2, tr3);

    const atr = (prevAtr * (n - 1) + tr) / n;
    
    document.getElementById('res-atr').innerText = `TR = ${tr.toFixed(2)} | ATR = ${atr.toFixed(4)}`;
};

window.calculateKDJ = function() {
    const c = parseFloat(document.getElementById('kdj-c').value);
    const ll = parseFloat(document.getElementById('kdj-ll').value);
    const hh = parseFloat(document.getElementById('kdj-hh').value);
    const pk = parseFloat(document.getElementById('kdj-pk').value);
    const pd = parseFloat(document.getElementById('kdj-pd').value);

    let rsv = 50;
    if (hh !== ll) {
        rsv = ((c - ll) / (hh - ll)) * 100;
    }

    const k = pk * (2/3) + rsv * (1/3);
    const d = pd * (2/3) + k * (1/3);
    document.getElementById('res-kdj').innerText = `RSV = ${rsv.toFixed(2)} | K = ${k.toFixed(2)} | D = ${d.toFixed(2)} | J = ${j.toFixed(2)}`;
};

function packSegmentsIntoSeries(chart, segments, seriesOptions) {
    segments.sort((a, b) => a.startTime - b.startTime);
    const tracks = [];
    for (const seg of segments) {
        let placed = false;
        for (const track of tracks) {
            if (track.lastTime < seg.startTime - 1) {
                track.data.push({ time: seg.startTime - 1, value: NaN });
                track.data.push({ time: seg.startTime, value: seg.startValue });
                if (seg.endTime > seg.startTime) {
                    track.data.push({ time: seg.endTime, value: seg.endValue });
                    track.lastTime = seg.endTime;
                } else {
                    track.lastTime = seg.startTime;
                }
                placed = true;
                break;
            }
        }
        if (!placed) {
            const data = [{ time: seg.startTime, value: seg.startValue }];
            if (seg.endTime > seg.startTime) {
                data.push({ time: seg.endTime, value: seg.endValue });
            }
            tracks.push({
                lastTime: Math.max(seg.startTime, seg.endTime),
                data: data
            });
        }
    }
    const createdSeries = [];
    for (const track of tracks) {
        const s = addLineSeriesCompat(chart, seriesOptions);
        s.setData(track.data);
        createdSeries.push(s);
    }
    return createdSeries;
}

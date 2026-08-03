import { useEffect, useRef } from 'react';
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type IPriceLine,
  type Time,
} from 'lightweight-charts';
import type { Candle, DashboardTheme } from '../../types/artifacts';
import type { ProcessedOb, ProcessedTrade } from './chartProcessing';
import { hexToRgbaStr, parseHexColor } from './colorUtils';

export interface ChartHoverInfo {
  time: number | null;
  idx: number | null;
  row: Candle | null;
  ob: ProcessedOb | null;
  trade: ProcessedTrade | null;
}

interface MultiPaneChartProps {
  candles: Candle[];
  processedObs: ProcessedOb[];
  processedTrades: ProcessedTrade[];
  dataColors: DashboardTheme['dataColors'];
  pageTheme: 'light' | 'dark';
  showObZones: boolean;
  showObMarkers: boolean;
  showTradeLines: boolean;
  autoFit: boolean;
  onHoverChange: (info: ChartHoverInfo) => void;
}

const OB_FILL_OPACITY = [0.08, 0.09, 0.1, 0.12, 0.14, 0.16];

/** Chart + series instances live in a ref, not React state -- lightweight-charts is imperative. */
interface ChartBundle {
  charts: IChartApi[];
  mainChart: IChartApi;
  macdChart: IChartApi;
  kdjStaticChart: IChartApi;
  kdjAdaptiveChart: IChartApi;
  atrChart: IChartApi;
  candleSeries: ISeriesApi<'Candlestick'>;
  candleMarkers: ISeriesMarkersPluginApi<Time>;
  macdHist: ISeriesApi<'Histogram'>;
  macdLine: ISeriesApi<'Line'>;
  signalLine: ISeriesApi<'Line'>;
  kStatic: ISeriesApi<'Line'>;
  dStatic: ISeriesApi<'Line'>;
  jStatic: ISeriesApi<'Line'>;
  kAdaptive: ISeriesApi<'Line'>;
  dAdaptive: ISeriesApi<'Line'>;
  jAdaptive: ISeriesApi<'Line'>;
  atrLine: ISeriesApi<'Line'>;
  atr200Line: ISeriesApi<'Line'>;
  activeTradeLines: IPriceLine[];
  timeToIndex: Map<number, number>;
}

export function MultiPaneChart({
  candles,
  processedObs,
  processedTrades,
  dataColors,
  pageTheme,
  showObZones,
  showObMarkers,
  showTradeLines,
  autoFit,
  onHoverChange,
}: MultiPaneChartProps) {
  const mainRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const kdjStaticRef = useRef<HTMLDivElement>(null);
  const kdjAdaptiveRef = useRef<HTMLDivElement>(null);
  const atrRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const columnRef = useRef<HTMLDivElement>(null);
  const bundleRef = useRef<ChartBundle | null>(null);
  const hoveredTimeRef = useRef<number | null>(null);

  // Latest prop values, readable from event handlers set up once on mount.
  const propsRef = useRef({
    processedObs,
    processedTrades,
    dataColors,
    showObZones,
    showObMarkers,
    showTradeLines,
    onHoverChange,
  });
  propsRef.current = {
    processedObs,
    processedTrades,
    dataColors,
    showObZones,
    showObMarkers,
    showTradeLines,
    onHoverChange,
  };

  // --- Mount: create charts once candles are available ---
  useEffect(() => {
    if (candles.length === 0) return;
    if (!mainRef.current || !macdRef.current || !kdjStaticRef.current || !kdjAdaptiveRef.current || !atrRef.current) {
      return;
    }

    const commonOptions = {
      layout: {
        textColor: '#475569',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, Roboto, sans-serif',
        fontSize: 11,
      },
      grid: { vertLines: { color: '#f1f5f9' }, horzLines: { color: '#f1f5f9' } },
      rightPriceScale: { borderColor: '#e2e8f0', minimumWidth: 100 },
      timeScale: { borderColor: '#e2e8f0', timeVisible: true },
    };

    const mainChart = createChart(mainRef.current, commonOptions);
    const macdChart = createChart(macdRef.current, commonOptions);
    const kdjStaticChart = createChart(kdjStaticRef.current, commonOptions);
    const kdjAdaptiveChart = createChart(kdjAdaptiveRef.current, commonOptions);
    const atrChart = createChart(atrRef.current, commonOptions);
    const charts = [mainChart, macdChart, kdjStaticChart, kdjAdaptiveChart, atrChart];

    mainChart.timeScale().applyOptions({ visible: false });
    macdChart.timeScale().applyOptions({ visible: false });
    kdjStaticChart.timeScale().applyOptions({ visible: false });
    kdjAdaptiveChart.timeScale().applyOptions({ visible: false });
    atrChart.timeScale().applyOptions({ visible: true });

    const candleSeries = mainChart.addSeries(CandlestickSeries, {});
    const candleMarkers = createSeriesMarkers(candleSeries, []);
    const macdHist = macdChart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' } });
    const macdLine = macdChart.addSeries(LineSeries, { lineWidth: 2 });
    const signalLine = macdChart.addSeries(LineSeries, { lineWidth: 1 });
    const kStatic = kdjStaticChart.addSeries(LineSeries, { lineWidth: 2 });
    const dStatic = kdjStaticChart.addSeries(LineSeries, { lineWidth: 1 });
    const jStatic = kdjStaticChart.addSeries(LineSeries, { lineWidth: 1 });
    const kAdaptive = kdjAdaptiveChart.addSeries(LineSeries, { lineWidth: 2 });
    const dAdaptive = kdjAdaptiveChart.addSeries(LineSeries, { lineWidth: 2 });
    const jAdaptive = kdjAdaptiveChart.addSeries(LineSeries, { lineWidth: 1 });
    const atrLine = atrChart.addSeries(LineSeries, { lineWidth: 2 });
    const atr200Line = atrChart.addSeries(LineSeries, { lineWidth: 1 });

    macdLine.setData(candles.map((d) => ({ time: d.time as Time, value: d.MACD })));
    signalLine.setData(candles.map((d) => ({ time: d.time as Time, value: d.MACD_signal })));
    kStatic.setData(candles.map((d) => ({ time: d.time as Time, value: d.K })));
    dStatic.setData(candles.map((d) => ({ time: d.time as Time, value: d.D })));
    jStatic.setData(candles.map((d) => ({ time: d.time as Time, value: d.J })));
    atrLine.setData(candles.map((d) => ({ time: d.time as Time, value: d.ATR })));
    atr200Line.setData(candles.map((d) => ({ time: d.time as Time, value: d.ATR_200 })));

    const timeToIndex = new Map(candles.map((row, idx) => [row.time, idx]));

    const bundle: ChartBundle = {
      charts,
      mainChart,
      macdChart,
      kdjStaticChart,
      kdjAdaptiveChart,
      atrChart,
      candleSeries,
      candleMarkers,
      macdHist,
      macdLine,
      signalLine,
      kStatic,
      dStatic,
      jStatic,
      kAdaptive,
      dAdaptive,
      jAdaptive,
      atrLine,
      atr200Line,
      activeTradeLines: [],
      timeToIndex,
    };
    bundleRef.current = bundle;

    // --- Zoom/pan sync ---
    let isSyncing = false;
    let overlayTimer: ReturnType<typeof setTimeout>;
    charts.forEach((chart, idx) => {
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (isSyncing || !range) return;
        isSyncing = true;
        charts.forEach((c, i) => {
          if (i !== idx) c.timeScale().setVisibleLogicalRange(range);
        });
        isSyncing = false;
        clearTimeout(overlayTimer);
        overlayTimer = setTimeout(() => redrawOverlays(bundle, hoveredTimeRef.current), 60);
      });
    });

    // --- Crosshair sync ---
    let isCrosshairSyncing = false;
    const findActiveTrade = (idx: number) =>
      propsRef.current.processedTrades.find((t) => t.entry_idx <= idx && idx <= t.exit_idx) ?? null;
    const findObAtTime = (time: number) => propsRef.current.processedObs.find((ob) => ob.startTime === time) ?? null;

    const seriesBySourceChart = new Map<IChartApi, { series: ISeriesApi<never>; valueOf: (row: Candle) => number }>([
      [mainChart, { series: candleSeries as unknown as ISeriesApi<never>, valueOf: (r) => r.close }],
      [macdChart, { series: macdHist as unknown as ISeriesApi<never>, valueOf: (r) => r.MACD_hist }],
      [kdjStaticChart, { series: kStatic as unknown as ISeriesApi<never>, valueOf: (r) => r.K }],
      [kdjAdaptiveChart, { series: kAdaptive as unknown as ISeriesApi<never>, valueOf: (r) => r.K }],
      [atrChart, { series: atrLine as unknown as ISeriesApi<never>, valueOf: (r) => r.ATR }],
    ]);

    function syncCrosshairs(time: Time | undefined, sourceChart: IChartApi) {
      if (isCrosshairSyncing) return;
      isCrosshairSyncing = true;

      if (time != null) {
        const idx = timeToIndex.get(time as number);
        if (idx !== undefined) {
          const row = candles[idx];
          const trade = findActiveTrade(idx);
          const ob = findObAtTime(time as number);
          hoveredTimeRef.current = time as number;

          renderAdaptiveKdjPane(bundle, trade);
          propsRef.current.onHoverChange({ time: time as number, idx, row, ob, trade });

          for (const [chart, target] of seriesBySourceChart) {
            if (chart !== sourceChart) {
              try {
                chart.setCrosshairPosition(target.valueOf(row), time, target.series);
              } catch {
                /* series may not have data at this time yet */
              }
            }
          }
          redrawOverlays(bundle, time as number);
        }
      } else {
        hoveredTimeRef.current = null;
        renderAdaptiveKdjPane(bundle, null);
        propsRef.current.onHoverChange({ time: null, idx: null, row: null, ob: null, trade: null });
        for (const [chart] of seriesBySourceChart) {
          if (chart !== sourceChart) {
            try {
              chart.clearCrosshairPosition();
            } catch {
              /* no-op */
            }
          }
        }
        redrawOverlays(bundle, null);
      }
      isCrosshairSyncing = false;
    }

    charts.forEach((chart) => chart.subscribeCrosshairMove((p) => syncCrosshairs(p.time, chart)));

    // --- Resize ---
    const resizeObserver = new ResizeObserver(() => {
      charts.forEach((c) => {
        const parent = c.chartElement().parentElement;
        if (parent) c.applyOptions({ width: parent.clientWidth, height: parent.clientHeight });
      });
      redrawOverlays(bundle, hoveredTimeRef.current);
    });
    if (columnRef.current) resizeObserver.observe(columnRef.current);

    return () => {
      resizeObserver.disconnect();
      charts.forEach((c) => c.remove());
      bundleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles]);

  // --- Candle coloring + markers + overlay redraw when filters/data change ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle || candles.length === 0) return;

    const colored = candles.map((d) => ({ time: d.time as Time, open: d.open, high: d.high, low: d.low, close: d.close }));
    const markers: Parameters<typeof bundle.candleMarkers.setMarkers>[0] = [];

    for (const ob of processedObs) {
      const color = ob.type === 'DEMAND' ? dataColors.demand : dataColors.supply;
      (colored[ob.exactIdx] as { color?: string; borderColor?: string; wickColor?: string }).color = color;
      (colored[ob.exactIdx] as { color?: string; borderColor?: string; wickColor?: string }).borderColor = color;
      (colored[ob.exactIdx] as { color?: string; borderColor?: string; wickColor?: string }).wickColor = color;

      if (showObMarkers) {
        markers.push({
          time: ob.startTime as Time,
          position: ob.type === 'DEMAND' ? 'belowBar' : 'aboveBar',
          color,
          shape: ob.type === 'DEMAND' ? 'arrowUp' : 'arrowDown',
          text: `${ob.type} q${ob.quality}`,
        });
      }
    }

    bundle.candleSeries.setData(colored);
    bundle.candleMarkers.setMarkers(markers.sort((a, b) => (a.time as number) - (b.time as number)));

    redrawOverlays(bundle, hoveredTimeRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, processedObs, processedTrades, showObMarkers, showObZones, showTradeLines, dataColors]);

  // --- Series colors ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle) return;
    bundle.candleSeries.applyOptions({
      upColor: hexToRgbaStr(dataColors.candleUp),
      downColor: hexToRgbaStr(dataColors.candleDown),
      borderUpColor: hexToRgbaStr(dataColors.candleUp),
      borderDownColor: hexToRgbaStr(dataColors.candleDown),
      wickUpColor: hexToRgbaStr(dataColors.candleWick),
      wickDownColor: hexToRgbaStr(dataColors.candleWick),
    });
    bundle.macdHist.setData(
      candles.map((d) => ({
        time: d.time as Time,
        value: d.MACD_hist,
        color: d.MACD_hist > 0 ? hexToRgbaStr(dataColors.candleUp) : hexToRgbaStr(dataColors.candleDown),
      })),
    );
    bundle.macdLine.applyOptions({ color: hexToRgbaStr(dataColors.macd) });
    bundle.signalLine.applyOptions({ color: hexToRgbaStr(dataColors.macdSignal) });
    bundle.kStatic.applyOptions({ color: hexToRgbaStr(dataColors.kdjK) });
    bundle.dStatic.applyOptions({ color: hexToRgbaStr(dataColors.kdjD) });
    bundle.jStatic.applyOptions({ color: hexToRgbaStr(dataColors.kdjJ) });
    bundle.kAdaptive.applyOptions({ color: hexToRgbaStr(dataColors.kdjK) });
    bundle.dAdaptive.applyOptions({ color: hexToRgbaStr(dataColors.kdjD) });
    bundle.jAdaptive.applyOptions({ color: hexToRgbaStr(dataColors.kdjJ) });
    bundle.atrLine.applyOptions({ color: hexToRgbaStr(dataColors.atr14) });
    bundle.atr200Line.applyOptions({ color: hexToRgbaStr(dataColors.atr200) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataColors, candles]);

  // --- Theme (page chrome vs chart background) ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle) return;
    const isDark = pageTheme === 'dark';
    const chartBg = isDark ? '#131722' : '#ffffff';
    const chartText = isDark ? '#94a3b8' : '#475569';
    const gridColor = isDark ? '#1f222e' : '#f1f5f9';
    bundle.charts.forEach((c) => {
      c.applyOptions({
        layout: { background: { color: chartBg }, textColor: chartText },
        grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
      });
    });
  }, [pageTheme]);

  // --- Autofit / autoscale ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle) return;
    bundle.charts.forEach((c) => c.priceScale('right').applyOptions({ autoScale: autoFit }));
  }, [autoFit]);

  /** Places native dashed entry/TP/SL price lines for the given trade -- lightweight-charts'
   * own createPriceLine gives the TradingView-style dashed line + axis tag "for free". */
  function setActiveTradeLines(bundle: ChartBundle, trade: ProcessedTrade | null) {
    bundle.activeTradeLines.forEach((line) => bundle.candleSeries.removePriceLine(line));
    bundle.activeTradeLines = [];
    if (!trade) return;

    bundle.activeTradeLines.push(
      bundle.candleSeries.createPriceLine({
        price: trade.entry,
        color: trade.side === 'LONG' ? '#10b981' : '#ef4444',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: `${trade.side} entry`,
      }),
      bundle.candleSeries.createPriceLine({
        price: trade.take_profit,
        color: '#10b981',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'TP',
      }),
      bundle.candleSeries.createPriceLine({
        price: trade.stop_loss,
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'SL',
      }),
    );
  }

  function renderAdaptiveKdjPane(bundle: ChartBundle, trade: ProcessedTrade | null) {
    if (trade && trade.adaptiveKdjK.length > 0) {
      bundle.kAdaptive.setData(trade.adaptiveKdjK.map((p) => ({ time: p.time as Time, value: p.value })));
      bundle.dAdaptive.setData(trade.adaptiveKdjD.map((p) => ({ time: p.time as Time, value: p.value })));
      bundle.jAdaptive.setData(trade.adaptiveKdjJ.map((p) => ({ time: p.time as Time, value: p.value })));
    } else {
      bundle.kAdaptive.setData([]);
      bundle.dAdaptive.setData([]);
      bundle.jAdaptive.setData([]);
    }
    if (propsRef.current.showTradeLines) setActiveTradeLines(bundle, trade);
  }

  /** Draws OB zone rectangles + passive per-trade win/loss shading into the plain
   * (non-React-managed) overlay div. Imperative by design -- diffing this through
   * React on every pan/zoom/crosshair tick would be far too slow. */
  function redrawOverlays(bundle: ChartBundle, hoveredTime: number | null) {
    const container = overlayRef.current;
    if (!container) return;
    container.innerHTML = '';

    const { processedObs, processedTrades, showObZones, showTradeLines, dataColors } = propsRef.current;
    if (!showObZones && !showTradeLines) return;

    const timeScale = bundle.mainChart.timeScale();
    const visibleRange = timeScale.getVisibleLogicalRange();
    if (!visibleRange) return;

    if (showObZones) {
      // Label collision avoidance: skip (not offset) a label that would overlap
      // one already placed -- the zone rectangle itself always still renders.
      const placedLabels: { left: number; right: number; top: number; bottom: number }[] = [];
      const LABEL_WIDTH = 70;
      const LABEL_HEIGHT = 14;

      for (const ob of processedObs) {
        if (ob.endIdx < visibleRange.from || ob.exactIdx > visibleRange.to) continue;
        const startX = timeScale.timeToCoordinate(candles[ob.exactIdx].time as Time);
        const endX = timeScale.timeToCoordinate(candles[ob.endIdx].time as Time);
        if (startX === null || endX === null) continue;
        const topY = bundle.candleSeries.priceToCoordinate(ob.top);
        const bottomY = bundle.candleSeries.priceToCoordinate(ob.bottom);
        if (topY === null || bottomY === null) continue;

        const isActive = ob.startTime === hoveredTime;
        const color = ob.type === 'DEMAND' ? dataColors.demand : dataColors.supply;
        const parsed = parseHexColor(color);
        const rect = document.createElement('div');
        rect.className = 'ob-rect';
        rect.style.left = `${startX}px`;
        rect.style.top = `${Math.min(topY, bottomY)}px`;
        rect.style.width = `${Math.max(1, endX - startX)}px`;
        rect.style.height = `${Math.abs(bottomY - topY)}px`;
        if (isActive) {
          rect.style.border = '2px solid var(--accent)';
          rect.style.background = 'transparent';
          rect.style.zIndex = '20';
        } else {
          const op = (OB_FILL_OPACITY[ob.quality] ?? 0.08) * parsed.alpha;
          rect.style.border = `1px dashed rgba(${parsed.rgb}, ${0.4 * parsed.alpha})`;
          rect.style.background = `rgba(${parsed.rgb}, ${op})`;
        }
        container.appendChild(rect);

        const labelLeft = Math.max(4, startX + 3);
        const labelTop = Math.min(topY, bottomY) + 2;
        const labelBox = { left: labelLeft, right: labelLeft + LABEL_WIDTH, top: labelTop, bottom: labelTop + LABEL_HEIGHT };
        const collides = placedLabels.some(
          (b) => labelBox.left < b.right && labelBox.right > b.left && labelBox.top < b.bottom && labelBox.bottom > b.top,
        );
        if (collides && !isActive) continue;
        placedLabels.push(labelBox);

        const label = document.createElement('div');
        label.className = 'ob-label';
        label.style.left = `${labelLeft}px`;
        label.style.top = `${labelTop}px`;
        label.style.color = hexToRgbaStr(color);
        label.textContent = `${ob.type} q${ob.quality}`;
        container.appendChild(label);
      }
    }

    if (showTradeLines) {
      const visible = processedTrades.filter((t) => t.exit_idx >= visibleRange.from && t.entry_idx <= visibleRange.to);
      for (const t of visible.slice(-100)) {
        const startX = timeScale.timeToCoordinate(candles[t.entry_idx].time as Time);
        const endX = timeScale.timeToCoordinate(candles[t.exit_idx].time as Time);
        if (startX === null || endX === null) continue;
        const entryY = bundle.candleSeries.priceToCoordinate(t.entry);
        const tpY = bundle.candleSeries.priceToCoordinate(t.take_profit);
        const slY = bundle.candleSeries.priceToCoordinate(t.stop_loss);
        if (entryY === null || tpY === null || slY === null) continue;
        const width = Math.max(1, endX - startX);
        const isActiveTrade = hoveredTime != null && t.startTime <= hoveredTime && hoveredTime <= t.endTime;

        const zone = document.createElement('div');
        zone.className = `trade-zone ${t.hitTp ? 'win' : 'loss'}${isActiveTrade ? ' active' : ''}`;
        zone.style.left = `${startX}px`;
        zone.style.width = `${width}px`;
        zone.style.top = `${Math.min(entryY, t.hitTp ? tpY : slY)}px`;
        zone.style.height = `${Math.abs(entryY - (t.hitTp ? tpY : slY))}px`;
        container.appendChild(zone);
      }
    }
  }

  return (
    <div className="charts-column" ref={columnRef}>
      <div className="chart-pane" style={{ flex: 48, position: 'relative' }} ref={mainRef}>
        <div className="html-overlay-container" ref={overlayRef} />
        <div className="pane-header-overlay">BTCUSDT 4H Main Chart</div>
      </div>
      <div className="chart-pane" style={{ flex: 13, position: 'relative' }} ref={macdRef}>
        <div className="pane-header-overlay">MACD (12, 26, 9)</div>
      </div>
      <div className="chart-pane" style={{ flex: 13, position: 'relative' }} ref={kdjStaticRef}>
        <div className="pane-header-overlay">KDJ (9, 3, 3) — Static</div>
      </div>
      <div className="chart-pane" style={{ flex: 14, position: 'relative' }} ref={kdjAdaptiveRef}>
        <div className="pane-header-overlay">Adaptive KDJ (Trade-Active Only)</div>
      </div>
      <div className="chart-pane" style={{ flex: 12, position: 'relative' }} ref={atrRef}>
        <div className="pane-header-overlay">ATR (14 / 200)</div>
      </div>
    </div>
  );
}

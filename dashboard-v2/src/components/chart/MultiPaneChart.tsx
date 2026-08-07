import { useEffect, useRef } from 'react';
import {
  CandlestickSeries,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
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
  showTradeZones: boolean;
  autoFit: boolean;
  onHoverChange: (info: ChartHoverInfo) => void;
}

/** Chart + series instances live in a ref, not React state -- lightweight-charts is imperative. */
interface ChartBundle {
  charts: IChartApi[];
  mainChart: IChartApi;
  macdChart: IChartApi;
  kdjStaticChart: IChartApi;
  kdjAdaptiveChart: IChartApi;
  atrChart: IChartApi;
  candleSeries: ISeriesApi<'Candlestick'>;
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
  showTradeZones,
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
  const lastHoveredIdxRef = useRef<number | null>(null);

  // Latest prop values, readable from event handlers set up once on mount.
  const propsRef = useRef({ processedObs, processedTrades, dataColors, showObZones, showTradeZones, onHoverChange });
  propsRef.current = { processedObs, processedTrades, dataColors, showObZones, showTradeZones, onHoverChange };

  // --- Mount: create charts once candles are available ---
  useEffect(() => {
    if (candles.length === 0) return;
    if (!mainRef.current || !macdRef.current || !kdjStaticRef.current || !kdjAdaptiveRef.current || !atrRef.current) {
      return;
    }

    const isDark = pageTheme === 'dark';
    const commonOptions = {
      layout: {
        background: { color: isDark ? '#0e0f12' : '#ffffff' },
        textColor: isDark ? '#a3a6b0' : '#4c4b43',
        fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: isDark ? '#1a1c22' : '#eae9e3' },
        horzLines: { color: isDark ? '#1a1c22' : '#eae9e3' },
      },
      rightPriceScale: { borderColor: isDark ? '#26282f' : '#d3d1c7', minimumWidth: 90 },
      timeScale: { borderColor: isDark ? '#26282f' : '#d3d1c7', timeVisible: true },
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
    // isSyncing clears on the next animation frame, not synchronously: the other
    // panes' own range-change notifications can land a frame late, and if the
    // guard is already false by then, that late echo re-triggers the sync loop
    // unguarded (observed and fixed in a prior build of this component).
    let isSyncing = false;
    let overlayTimer: ReturnType<typeof setTimeout>;
    charts.forEach((chart, idx) => {
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (isSyncing || !range) return;
        isSyncing = true;
        charts.forEach((c, i) => {
          if (i !== idx) c.timeScale().setVisibleLogicalRange(range);
        });
        requestAnimationFrame(() => {
          isSyncing = false;
        });
        clearTimeout(overlayTimer);
        overlayTimer = setTimeout(() => redrawOverlays(bundle, hoveredTimeRef.current), 60);
      });
    });

    // --- Crosshair sync ---
    // Same next-frame-clear discipline as isSyncing above, for the same reason.
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
          hoveredTimeRef.current = time as number;

          // Any per-bar work (adaptive-KDJ rebuild, overlay redraw, the
          // React callback) is gated on the hovered bar index actually
          // changing -- a drag fires many crosshair-move events per
          // bar-width, and redoing this work on every one of them (not just
          // when the bar changes) is both wasted work and, for the overlay
          // redraw specifically, a full innerHTML clear + rebuild on every
          // pixel of mouse movement.
          if (idx !== lastHoveredIdxRef.current) {
            lastHoveredIdxRef.current = idx;
            const trade = findActiveTrade(idx);
            const ob = findObAtTime(time as number);
            renderAdaptiveKdjPane(bundle, trade);
            propsRef.current.onHoverChange({ time: time as number, idx, row, ob, trade });
            redrawOverlays(bundle, time as number);
          }

          for (const [chart, target] of seriesBySourceChart) {
            if (chart !== sourceChart) {
              try {
                chart.setCrosshairPosition(target.valueOf(row), time, target.series);
              } catch {
                /* series may not have data at this time yet */
              }
            }
          }
        }
      } else {
        hoveredTimeRef.current = null;
        lastHoveredIdxRef.current = null;
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
      requestAnimationFrame(() => {
        isCrosshairSyncing = false;
      });
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
  }, [candles, pageTheme]);

  // --- Candle coloring + overlay redraw when filters/data change ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle || candles.length === 0) return;

    const colored = candles.map((d) => ({ time: d.time as Time, open: d.open, high: d.high, low: d.low, close: d.close }));
    for (const ob of processedObs) {
      const color = ob.type === 'DEMAND' ? dataColors.demand : dataColors.supply;
      Object.assign(colored[ob.exactIdx], { color, borderColor: color, wickColor: color });
    }
    bundle.candleSeries.setData(colored);
    redrawOverlays(bundle, hoveredTimeRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, processedObs, processedTrades, showObZones, showTradeZones, dataColors]);

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

  // --- Autofit / autoscale ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle) return;
    bundle.charts.forEach((c) => c.priceScale('right').applyOptions({ autoScale: autoFit }));
  }, [autoFit]);

  function setActiveTradeLines(bundle: ChartBundle, trade: ProcessedTrade | null) {
    bundle.activeTradeLines.forEach((line) => bundle.candleSeries.removePriceLine(line));
    bundle.activeTradeLines = [];
    if (!trade) return;
    bundle.activeTradeLines.push(
      bundle.candleSeries.createPriceLine({
        price: trade.entry,
        color: trade.side === 'LONG' ? '#2ecc71' : '#ff4d4f',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: `${trade.side} entry`,
      }),
      bundle.candleSeries.createPriceLine({
        price: trade.take_profit,
        color: '#2ecc71',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'TP',
      }),
      bundle.candleSeries.createPriceLine({
        price: trade.stop_loss,
        color: '#ff4d4f',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'SL',
      }),
    );
  }

  function renderAdaptiveKdjPane(bundle: ChartBundle, trade: ProcessedTrade | null) {
    // setData() re-fits this pane's own time scale, and a trade's adaptive-KDJ
    // window can sit anywhere in the dataset's history; since this pane's time
    // scale is synced to the other four, an unguarded re-fit here drags every
    // pane's view along with it. Snapshot and restore the visible range.
    const adaptiveTimeScale = bundle.kdjAdaptiveChart.timeScale();
    const preservedRange = adaptiveTimeScale.getVisibleLogicalRange();

    if (trade && trade.adaptiveKdjK.length > 0) {
      bundle.kAdaptive.setData(trade.adaptiveKdjK.map((p) => ({ time: p.time as Time, value: p.value })));
      bundle.dAdaptive.setData(trade.adaptiveKdjD.map((p) => ({ time: p.time as Time, value: p.value })));
      bundle.jAdaptive.setData(trade.adaptiveKdjJ.map((p) => ({ time: p.time as Time, value: p.value })));
    } else {
      bundle.kAdaptive.setData([]);
      bundle.dAdaptive.setData([]);
      bundle.jAdaptive.setData([]);
    }

    if (preservedRange) adaptiveTimeScale.setVisibleLogicalRange(preservedRange);
    setActiveTradeLines(bundle, trade);
  }

  /**
   * Draws OB zone rectangles + trade win/loss zones into the plain (non-React)
   * overlay div -- imperative by design, diffing this through React on every
   * pan/zoom/crosshair tick would be far too slow. An Order Block is drawn as a
   * single rectangle anchored at its origin candle and extending forward to
   * where the zone ends (mitigated or aged out) -- there is no separate arrow/
   * marker representation.
   */
  function redrawOverlays(bundle: ChartBundle, hoveredTime: number | null) {
    const container = overlayRef.current;
    if (!container) return;
    container.innerHTML = '';

    const { processedObs, processedTrades, showObZones, showTradeZones, dataColors } = propsRef.current;
    if (!showObZones && !showTradeZones) return;

    const timeScale = bundle.mainChart.timeScale();
    const visibleRange = timeScale.getVisibleLogicalRange();
    if (!visibleRange) return;

    if (showObZones) {
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
          rect.style.border = '1.5px solid var(--accent)';
          rect.style.background = `rgba(${parsed.rgb}, 0.14)`;
        } else {
          rect.style.border = `1px dashed rgba(${parsed.rgb}, ${0.45 * parsed.alpha})`;
          rect.style.background = `rgba(${parsed.rgb}, ${0.07 * parsed.alpha})`;
        }
        container.appendChild(rect);
      }
    }

    if (showTradeZones) {
      const visible = processedTrades.filter((t) => t.exit_idx >= visibleRange.from && t.entry_idx <= visibleRange.to);
      for (const t of visible.slice(-100)) {
        const startX = timeScale.timeToCoordinate(candles[t.entry_idx].time as Time);
        const endX = timeScale.timeToCoordinate(candles[t.exit_idx].time as Time);
        if (startX === null || endX === null) continue;
        const entryY = bundle.candleSeries.priceToCoordinate(t.entry);
        const exitLevelY = bundle.candleSeries.priceToCoordinate(t.hitTp ? t.take_profit : t.stop_loss);
        if (entryY === null || exitLevelY === null) continue;
        const isActiveTrade = hoveredTime != null && t.startTime <= hoveredTime && hoveredTime <= t.endTime;

        const zone = document.createElement('div');
        zone.className = `trade-zone ${t.hitTp ? 'win' : 'loss'}${isActiveTrade ? ' active' : ''}`;
        zone.style.left = `${startX}px`;
        zone.style.width = `${Math.max(1, endX - startX)}px`;
        zone.style.top = `${Math.min(entryY, exitLevelY)}px`;
        zone.style.height = `${Math.abs(entryY - exitLevelY)}px`;
        container.appendChild(zone);
      }
    }
  }

  return (
    <div className="charts-column" ref={columnRef}>
      <div className="chart-pane" style={{ flex: 48, position: 'relative' }} ref={mainRef}>
        <div className="html-overlay-container" ref={overlayRef} />
        <div className="pane-header-overlay">BTCUSDT 4H</div>
      </div>
      <div className="chart-pane" style={{ flex: 13, position: 'relative' }} ref={macdRef}>
        <div className="pane-header-overlay">MACD (12, 26, 9)</div>
      </div>
      <div className="chart-pane" style={{ flex: 13, position: 'relative' }} ref={kdjStaticRef}>
        <div className="pane-header-overlay">KDJ (9, 3, 3) STATIC</div>
      </div>
      <div className="chart-pane" style={{ flex: 14, position: 'relative' }} ref={kdjAdaptiveRef}>
        <div className="pane-header-overlay">ADAPTIVE KDJ (TRADE-ACTIVE)</div>
      </div>
      <div className="chart-pane" style={{ flex: 12, position: 'relative' }} ref={atrRef}>
        <div className="pane-header-overlay">ATR (14 / 200)</div>
      </div>
    </div>
  );
}

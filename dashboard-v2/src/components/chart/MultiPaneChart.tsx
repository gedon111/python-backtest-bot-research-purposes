import { useEffect, useRef } from 'react';
import {
  CandlestickSeries,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type IPaneApi,
  type ISeriesApi,
  type IPriceLine,
  type ITimeScaleApi,
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
  /** Non-null to force the time scale to a specific window (e.g. from the Chart
   * tab's date-range inputs); applied via setVisibleRange, never by re-slicing
   * `candles` -- see the effect below for why. */
  visibleRange?: { from: Time; to: Time } | null;
  /** Locked-backtest window boundaries (from the always-loaded locked candle
   * set, regardless of which array is currently mounted here) -- used to shade
   * and label the pre-2022/post-2026 regions as "not part of the locked
   * backtest" whenever a wider array is mounted. Null suppresses the bands. */
  lockedWindowStart?: number | null;
  lockedWindowEnd?: number | null;
}

// Pane indices within the single chart -- one real chart with 5 native
// panes (lightweight-charts 5's Panes API), not 5 separate chart instances.
// Panes of one chart share a single time scale and a single crosshair
// natively, which is what guarantees they stay pixel-aligned -- the prior
// 5-separate-instances architecture required hand-written sync code (pan
// sync, crosshair sync, range-preservation snapshotting) that was the
// actual source of several bugs this session, including this one: each
// independent chart auto-sized its own price axis to its own content's
// digit width, so plot areas landed at different pixel offsets even with
// numerically-synced time ranges.
const PANE = { main: 0, macd: 1, kdjStatic: 2, kdjAdaptive: 3, atr: 4 } as const;

/** Chart + series instances live in a ref, not React state -- lightweight-charts is imperative. */
interface ChartBundle {
  chart: IChartApi;
  candleSeries: ISeriesApi<'Candlestick'>;
  macdHist: ISeriesApi<'Histogram'>;
  macdLine: ISeriesApi<'Line'>;
  signalLine: ISeriesApi<'Line'>;
  kStatic: ISeriesApi<'Line'>;
  dStatic: ISeriesApi<'Line'>;
  jStatic: ISeriesApi<'Line'>;
  atrLine: ISeriesApi<'Line'>;
  atr200Line: ISeriesApi<'Line'>;
  activeTradeLines: IPriceLine[];
  timeToIndex: Map<number, number>;
  adaptiveKSeriesList: ISeriesApi<'Line'>[];
  adaptiveDSeriesList: ISeriesApi<'Line'>[];
  adaptiveJSeriesList: ISeriesApi<'Line'>[];
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
  visibleRange = null,
  lockedWindowStart = null,
  lockedWindowEnd = null,
}: MultiPaneChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayElRef = useRef<HTMLDivElement | null>(null);
  const bundleRef = useRef<ChartBundle | null>(null);
  const hoveredTimeRef = useRef<number | null>(null);
  const lastHoveredIdxRef = useRef<number | null>(null);

  // Latest prop values, readable from event handlers set up once on mount.
  const propsRef = useRef({
    processedObs,
    processedTrades,
    dataColors,
    showObZones,
    showTradeZones,
    onHoverChange,
    lockedWindowStart,
    lockedWindowEnd,
  });
  propsRef.current = {
    processedObs,
    processedTrades,
    dataColors,
    showObZones,
    showTradeZones,
    onHoverChange,
    lockedWindowStart,
    lockedWindowEnd,
  };

  // --- Mount: create the chart + panes once candles are available ---
  useEffect(() => {
    if (candles.length === 0) return;
    if (!containerRef.current) return;

    const isDark = pageTheme === 'dark';
    const borderColor = isDark ? '#26282f' : '#d3d1c7';
    const commonOptions = {
      layout: {
        background: { color: isDark ? '#0e0f12' : '#ffffff' },
        textColor: isDark ? '#a3a6b0' : '#4c4b43',
        fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
        fontSize: 11,
        panes: { separatorColor: borderColor },
      },
      grid: {
        vertLines: { color: isDark ? '#1a1c22' : '#eae9e3' },
        horzLines: { color: isDark ? '#1a1c22' : '#eae9e3' },
      },
      rightPriceScale: { borderColor, minimumWidth: 90 },
      timeScale: { borderColor, timeVisible: true },
    };

    const chart = createChart(containerRef.current, commonOptions);
    const mainPane = chart.panes()[0];
    const macdPane = chart.addPane();
    const kdjStaticPane = chart.addPane();
    const kdjAdaptivePane = chart.addPane();
    const atrPane = chart.addPane();
    mainPane.setStretchFactor(48);
    macdPane.setStretchFactor(13);
    kdjStaticPane.setStretchFactor(13);
    kdjAdaptivePane.setStretchFactor(14);
    atrPane.setStretchFactor(12);

    // priceLineVisible: false everywhere -- removes lightweight-charts'
    // automatic dashed last-value line on every pane; it's a separate
    // mechanism from the entry/TP/SL lines (those use createPriceLine).
    const candleSeries = chart.addSeries(CandlestickSeries, { priceLineVisible: false }, PANE.main);
    const macdHist = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'volume' }, priceLineVisible: false },
      PANE.macd,
    );
    const macdLine = chart.addSeries(LineSeries, { lineWidth: 2, priceLineVisible: false }, PANE.macd);
    const signalLine = chart.addSeries(LineSeries, { lineWidth: 1, priceLineVisible: false }, PANE.macd);
    const kStatic = chart.addSeries(LineSeries, { lineWidth: 2, priceLineVisible: false }, PANE.kdjStatic);
    const dStatic = chart.addSeries(LineSeries, { lineWidth: 1, priceLineVisible: false }, PANE.kdjStatic);
    const jStatic = chart.addSeries(LineSeries, { lineWidth: 1, priceLineVisible: false }, PANE.kdjStatic);
    const atrLine = chart.addSeries(LineSeries, { lineWidth: 2, priceLineVisible: false }, PANE.atr);
    const atr200Line = chart.addSeries(LineSeries, { lineWidth: 1, priceLineVisible: false }, PANE.atr);

    macdLine.setData(candles.map((d) => ({ time: d.time as Time, value: d.MACD })));
    signalLine.setData(candles.map((d) => ({ time: d.time as Time, value: d.MACD_signal })));
    kStatic.setData(candles.map((d) => ({ time: d.time as Time, value: d.K })));
    dStatic.setData(candles.map((d) => ({ time: d.time as Time, value: d.D })));
    jStatic.setData(candles.map((d) => ({ time: d.time as Time, value: d.J })));
    atrLine.setData(candles.map((d) => ({ time: d.time as Time, value: d.ATR })));
    atr200Line.setData(candles.map((d) => ({ time: d.time as Time, value: d.ATR_200 })));

    const timeToIndex = new Map(candles.map((row, idx) => [row.time, idx]));

    const bundle: ChartBundle = {
      chart,
      candleSeries,
      macdHist,
      macdLine,
      signalLine,
      kStatic,
      dStatic,
      jStatic,
      atrLine,
      atr200Line,
      activeTradeLines: [],
      timeToIndex,
      adaptiveKSeriesList: [],
      adaptiveDSeriesList: [],
      adaptiveJSeriesList: [],
    };
    bundleRef.current = bundle;

    // --- Overlay div + pane header labels: plain DOM children of each
    // pane's own element (not React-rendered), matching redrawOverlays'
    // existing imperative style. Each pane manages its own price axis/plot
    // area, so timeToCoordinate()/priceToCoordinate() stay relative to it. ---
    const overlayEl = document.createElement('div');
    overlayEl.className = 'html-overlay-container';
    const mainPaneEl = mainPane.getHTMLElement();
    if (mainPaneEl) {
      mainPaneEl.style.position = 'relative';
      mainPaneEl.appendChild(overlayEl);
    }
    overlayElRef.current = overlayEl;

    const paneLabels: [IPaneApi<Time>, string][] = [
      [mainPane, 'BTCUSDT 4H'],
      [macdPane, 'MACD (12, 26, 9)'],
      [kdjStaticPane, 'KDJ (9, 3, 3) STATIC'],
      [kdjAdaptivePane, 'ADAPTIVE KDJ (PER TRADE)'],
      [atrPane, 'ATR (14 / 200)'],
    ];
    for (const [pane, label] of paneLabels) {
      const el = pane.getHTMLElement();
      if (!el) continue;
      el.style.position = 'relative';
      const headerEl = document.createElement('div');
      headerEl.className = 'pane-header-overlay';
      headerEl.textContent = label;
      el.appendChild(headerEl);
    }

    // --- Pan/zoom: one shared time scale, nothing to broadcast/sync ---
    let overlayTimer: ReturnType<typeof setTimeout>;
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      clearTimeout(overlayTimer);
      // Clear immediately, not just debounce the redraw: the OB/trade-zone
      // rectangles are absolutely-positioned divs computed from a point-in-
      // time timeToCoordinate() read, so leaving stale ones on screen during
      // a drag makes them appear frozen/lagging while candles (native canvas
      // rendering) keep moving underneath. Candles stay visible throughout;
      // only this overlay disappears until the pan/zoom settles.
      if (overlayElRef.current) overlayElRef.current.innerHTML = '';
      overlayTimer = setTimeout(() => redrawOverlays(bundle, hoveredTimeRef.current), 60);
    });

    // --- Crosshair: one shared crosshair, nothing to manually position
    // across panes -- only the hover-settle work below (price-line rebuild,
    // inspection-panel callback, overlay redraw) needs debouncing. ---
    let hoverUpdateTimer: ReturnType<typeof setTimeout> | undefined;
    // Entry/TP/SL price lines only need rebuilding when the *trade* actually
    // changes, not on every settled bar within the same trade's span -- a
    // wide trade window (adaptive periods run 14-439 bars, median 74) was
    // re-tearing-down and recreating these lines on every bar crossed while
    // dragging through it, which read as flicker/"glitching."
    let lastActiveTradeEntryIdxRef: number | null = null;
    // Time-based, not entry_idx/exit_idx-based: those indices were computed
    // against the LOCKED candle array (see chartProcessing.ts), which may not
    // be the array currently mounted here (e.g. the Chart tab's "Full
    // History" extended view prepends/appends bars). startTime/endTime are
    // absolute Unix-second timestamps, stable regardless of which array is
    // mounted -- comparing against those instead of raw indices keeps this
    // correct in both view modes with no offset math required.
    const findActiveTrade = (time: number) =>
      propsRef.current.processedTrades.find((t) => t.startTime <= time && time <= t.endTime) ?? null;
    const findObAtTime = (time: number) => propsRef.current.processedObs.find((ob) => ob.startTime === time) ?? null;

    chart.subscribeCrosshairMove((param) => {
      const time = param.time as number | undefined;
      if (time != null) {
        const idx = timeToIndex.get(time);
        if (idx === undefined) return;
        const row = candles[idx];
        hoveredTimeRef.current = time;

        // Any per-bar work (price-line rebuild, overlay redraw, the React
        // callback) is gated on the hovered bar index actually changing -- a
        // drag fires many crosshair-move events per bar-width, and redoing
        // this work on every one of them (not just when the bar changes) is
        // both wasted work and, for the overlay redraw specifically, a full
        // innerHTML clear + rebuild on every pixel of mouse movement.
        if (idx !== lastHoveredIdxRef.current) {
          lastHoveredIdxRef.current = idx;
          clearTimeout(hoverUpdateTimer);
          hoverUpdateTimer = setTimeout(() => {
            const trade = findActiveTrade(time);
            const ob = findObAtTime(time);
            if ((trade?.entry_idx ?? null) !== lastActiveTradeEntryIdxRef) {
              lastActiveTradeEntryIdxRef = trade?.entry_idx ?? null;
              setActiveTradeLines(bundle, trade);
            }
            propsRef.current.onHoverChange({ time, idx, row, ob, trade });
            redrawOverlays(bundle, time);
          }, 30);
        }
      } else {
        hoveredTimeRef.current = null;
        lastHoveredIdxRef.current = null;
        clearTimeout(hoverUpdateTimer);
        hoverUpdateTimer = setTimeout(() => {
          if (lastActiveTradeEntryIdxRef !== null) {
            lastActiveTradeEntryIdxRef = null;
            setActiveTradeLines(bundle, null);
          }
          propsRef.current.onHoverChange({ time: null, idx: null, row: null, ob: null, trade: null });
          redrawOverlays(bundle, null);
        }, 30);
      }
    });

    // --- Resize ---
    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.resize(containerRef.current.clientWidth, containerRef.current.clientHeight);
      }
      redrawOverlays(bundle, hoveredTimeRef.current);
    });
    if (containerRef.current) resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      clearTimeout(overlayTimer);
      clearTimeout(hoverUpdateTimer);
      chart.remove();
      bundleRef.current = null;
      overlayElRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, pageTheme]);

  // --- Candle coloring + overlay redraw when filters/data change ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle || candles.length === 0) return;

    const colored = candles.map((d) => ({ time: d.time as Time, open: d.open, high: d.high, low: d.low, close: d.close }));
    for (const ob of processedObs) {
      // ob.exactIdx is an index into the LOCKED candle array (see
      // chartProcessing.ts), not necessarily this array -- resolve via the
      // time->index map for whichever array is actually mounted. Skips
      // (correctly) if this OB's bar isn't present in the mounted array.
      const idx = bundle.timeToIndex.get(ob.startTime);
      if (idx === undefined) continue;
      const color = ob.type === 'DEMAND' ? dataColors.demand : dataColors.supply;
      Object.assign(colored[idx], { color, borderColor: color, wickColor: color });
    }
    bundle.candleSeries.setData(colored);
    redrawOverlays(bundle, hoveredTimeRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, processedObs, processedTrades, showObZones, showTradeZones, dataColors]);

  // --- Adaptive KDJ pane: always shows every trade's segment, not just the
  // hovered one. Separate from the effect above (keyed on fewer deps) since
  // this doesn't need to re-run on showObZones/showTradeZones/dataColors. ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle || candles.length === 0) return;
    rebuildAdaptiveKdjSeries(bundle, processedTrades);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, processedTrades]);

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
    bundle.adaptiveKSeriesList.forEach((s) => s.applyOptions({ color: hexToRgbaStr(dataColors.kdjK) }));
    bundle.adaptiveDSeriesList.forEach((s) => s.applyOptions({ color: hexToRgbaStr(dataColors.kdjD) }));
    bundle.adaptiveJSeriesList.forEach((s) => s.applyOptions({ color: hexToRgbaStr(dataColors.kdjJ) }));
    bundle.atrLine.applyOptions({ color: hexToRgbaStr(dataColors.atr14) });
    bundle.atr200Line.applyOptions({ color: hexToRgbaStr(dataColors.atr200) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataColors, candles]);

  // --- Autofit / autoscale ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle) return;
    for (const paneIndex of Object.values(PANE)) {
      bundle.chart.priceScale('right', paneIndex).applyOptions({ autoScale: autoFit });
    }
  }, [autoFit]);

  // --- Forced date-range window (Chart tab's date inputs) ---
  // Uses the time scale's own setVisibleRange, not a re-slice of `candles` --
  // re-slicing would change the `candles` prop's identity and force the mount
  // effect above to tear down and rebuild every pane/series on every
  // date-picker keystroke. This just moves the viewport within whatever is
  // already mounted.
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle || !visibleRange) return;
    bundle.chart.timeScale().setVisibleRange(visibleRange);
  }, [visibleRange]);

  // --- Locked-window boundary bands (redraw trigger only -- the actual
  // drawing happens in redrawOverlays, sharing its pan/zoom/resize triggers) ---
  useEffect(() => {
    const bundle = bundleRef.current;
    if (!bundle) return;
    redrawOverlays(bundle, hoveredTimeRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lockedWindowStart, lockedWindowEnd]);

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
        axisLabelVisible: false,
        title: `${trade.side} entry`,
      }),
      bundle.candleSeries.createPriceLine({
        price: trade.take_profit,
        color: '#2ecc71',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
        title: 'TP',
      }),
      bundle.candleSeries.createPriceLine({
        price: trade.stop_loss,
        color: '#ff4d4f',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
        title: 'SL',
      }),
    );
  }

  /**
   * One real LineSeries per trade per K/D/J, each set to just that trade's
   * own adaptiveKdjK/D/J points -- not one series spanning the whole
   * timeline. lightweight-charts' "whitespace data" does NOT create a visual
   * gap in a Line series (confirmed: TradingView/lightweight-charts issues
   * #700, #699, #1042 -- known library limitation, not a config mistake); a
   * single series with whitespace between two trades' real points still
   * draws one continuous line straight from the last point to the next.
   * Separate series per trade is the documented workaround and guarantees no
   * line ever connects two different trades, by construction.
   *
   * No range-preservation snapshot needed here (unlike a prior version of
   * this function): with one shared chart time scale instead of 5
   * independent per-pane ones, there's no separate time scale left that
   * could auto-fit-from-empty and drag the others along.
   */
  function rebuildAdaptiveKdjSeries(bundle: ChartBundle, trades: ProcessedTrade[]) {
    for (const s of bundle.adaptiveKSeriesList) bundle.chart.removeSeries(s);
    for (const s of bundle.adaptiveDSeriesList) bundle.chart.removeSeries(s);
    for (const s of bundle.adaptiveJSeriesList) bundle.chart.removeSeries(s);
    bundle.adaptiveKSeriesList = [];
    bundle.adaptiveDSeriesList = [];
    bundle.adaptiveJSeriesList = [];

    const { dataColors } = propsRef.current;
    for (const t of trades) {
      const kSeries = bundle.chart.addSeries(
        LineSeries,
        { lineWidth: 2, color: hexToRgbaStr(dataColors.kdjK), priceLineVisible: false },
        PANE.kdjAdaptive,
      );
      kSeries.setData(t.adaptiveKdjK.map((p) => ({ time: p.time as Time, value: p.value })));
      const dSeries = bundle.chart.addSeries(
        LineSeries,
        { lineWidth: 1, color: hexToRgbaStr(dataColors.kdjD), priceLineVisible: false },
        PANE.kdjAdaptive,
      );
      dSeries.setData(t.adaptiveKdjD.map((p) => ({ time: p.time as Time, value: p.value })));
      const jSeries = bundle.chart.addSeries(
        LineSeries,
        { lineWidth: 1, color: hexToRgbaStr(dataColors.kdjJ), priceLineVisible: false },
        PANE.kdjAdaptive,
      );
      jSeries.setData(t.adaptiveKdjJ.map((p) => ({ time: p.time as Time, value: p.value })));
      bundle.adaptiveKSeriesList.push(kSeries);
      bundle.adaptiveDSeriesList.push(dSeries);
      bundle.adaptiveJSeriesList.push(jSeries);
    }
  }

  /**
   * Shades the main pane wherever the currently-mounted candle array extends
   * outside the locked 2022-2026 backtest window (the "Full History" extended
   * view), with a boundary line + label at each edge that's actually present.
   * OB zones/trade markers never appear in these bands on their own --
   * processedObs/processedTrades only ever contain locked-window data (see
   * ChartTab.tsx), so this is purely a visual disclosure, not a filter.
   */
  function drawFormulationPeriodBands(container: HTMLDivElement, timeScale: ITimeScaleApi<Time>) {
    if (candles.length === 0) return;
    const { lockedWindowStart, lockedWindowEnd } = propsRef.current;
    const paneHeight = container.clientHeight;

    const drawBand = (outerTime: number, boundaryTime: number, label: string) => {
      const outerX = timeScale.timeToCoordinate(outerTime as Time);
      const boundaryX = timeScale.timeToCoordinate(boundaryTime as Time);
      if (outerX === null || boundaryX === null) return;

      const band = document.createElement('div');
      band.className = 'formulation-band';
      band.style.left = `${Math.min(outerX, boundaryX)}px`;
      band.style.top = '0px';
      band.style.width = `${Math.max(1, Math.abs(boundaryX - outerX))}px`;
      band.style.height = `${paneHeight}px`;
      container.appendChild(band);

      const line = document.createElement('div');
      line.className = 'formulation-boundary-line';
      line.style.left = `${boundaryX}px`;
      line.style.height = `${paneHeight}px`;
      container.appendChild(line);

      const tag = document.createElement('div');
      tag.className = 'formulation-boundary-label';
      tag.style.left = `${boundaryX}px`;
      tag.textContent = label;
      container.appendChild(tag);
    };

    if (lockedWindowStart != null && candles[0].time < lockedWindowStart) {
      drawBand(candles[0].time, lockedWindowStart, 'FORMULATION PERIOD (PRE-2022) -- NOT PART OF LOCKED BACKTEST');
    }
    const lastCandle = candles[candles.length - 1];
    if (lockedWindowEnd != null && lastCandle.time > lockedWindowEnd) {
      drawBand(lastCandle.time, lockedWindowEnd, 'FORWARD DATA (POST-2026) -- NOT PART OF LOCKED BACKTEST');
    }
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
    const container = overlayElRef.current;
    if (!container) return;
    container.innerHTML = '';

    const timeScale = bundle.chart.timeScale();
    const visibleRange = timeScale.getVisibleLogicalRange();
    if (!visibleRange) return;

    drawFormulationPeriodBands(container, timeScale);

    const { processedObs, processedTrades, showObZones, showTradeZones, dataColors } = propsRef.current;
    if (!showObZones && !showTradeZones) return;

    if (showObZones) {
      for (const ob of processedObs) {
        // ob.exactIdx/endIdx are indices into the LOCKED array -- resolve
        // against whichever array is actually mounted via timeToIndex before
        // comparing to the mounted chart's own visible logical range. Skip
        // (not draw) an OB whose bar isn't present in the mounted array,
        // rather than culling/drawing it at the wrong position.
        const startIdx = bundle.timeToIndex.get(ob.startTime);
        const endIdx = bundle.timeToIndex.get(ob.endTime);
        if (startIdx === undefined || endIdx === undefined) continue;
        if (endIdx < visibleRange.from || startIdx > visibleRange.to) continue;
        const startX = timeScale.timeToCoordinate(ob.startTime as Time);
        const endX = timeScale.timeToCoordinate(ob.endTime as Time);
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
      // Same resolve-by-time-before-comparing-to-logical-range fix as the OB
      // block above -- t.entry_idx/exit_idx are indices into the LOCKED array.
      const visible = processedTrades.filter((t) => {
        const startIdx = bundle.timeToIndex.get(t.startTime);
        const endIdx = bundle.timeToIndex.get(t.endTime);
        return startIdx !== undefined && endIdx !== undefined && endIdx >= visibleRange.from && startIdx <= visibleRange.to;
      });
      for (const t of visible.slice(-100)) {
        const startX = timeScale.timeToCoordinate(t.startTime as Time);
        const endX = timeScale.timeToCoordinate(t.endTime as Time);
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

  return <div className="charts-column" ref={containerRef} />;
}

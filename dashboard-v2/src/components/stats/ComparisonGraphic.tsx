import { useEffect, useMemo, useRef, useState } from 'react';
import './ComparisonGraphic.css';
import { useBenchmarkMtm, useBenchmarkVsPassive, useCandles } from '../../api/hooks';
import type { TradeRecord } from '../../types/artifacts';
import { computeBenchmarkCurves } from './benchmarkCurves';

const DURATION_MS = 7000;
const W = 960;
const H = 380;
const PAD = { l: 78, r: 150, t: 24, b: 40 };

const money = (v: number) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const money0 = (v: number) => `$${Math.round(v).toLocaleString('en-US')}`;
const ease = (x: number) => 1 - Math.pow(1 - x, 3);
const monthYear = (t: number) =>
  new Date(t * 1000).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }).toUpperCase();

/** Plays 0 -> 1 over DURATION_MS once the graphic scrolls into view; replayable. */
function useProgress(target: React.RefObject<HTMLElement | null>, runId: number, ready: boolean) {
  const [p, setP] = useState(0);
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setP(1);
      return;
    }
    if (!ready) return;
    let raf = 0;
    let start = 0;
    const tick = (now: number) => {
      if (!start) start = now;
      const x = Math.min((now - start) / DURATION_MS, 1);
      setP(x);
      if (x < 1) raf = requestAnimationFrame(tick);
    };
    setP(0);
    const el = target.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          io.disconnect();
          raf = requestAnimationFrame(tick);
        }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [target, runId, ready]);
  return p;
}

export function ComparisonGraphic({ baseTrades }: { baseTrades: TradeRecord[] }) {
  const candles = useCandles();
  const vsPassive = useBenchmarkVsPassive();
  const mtm = useBenchmarkMtm();
  const rootRef = useRef<HTMLElement>(null);
  const [runId, setRunId] = useState(0);

  const published = useMemo(() => {
    if (!vsPassive.data || !mtm.data) return null;
    const gross = vsPassive.data.main_window.gross;
    const arms = mtm.data.main_window.gross.arms;
    const find = <T extends { arm: string }>(xs: T[], name: string) => {
      const a = xs.find((x) => x.arm === name);
      if (!a) throw new Error(`arm "${name}" missing from benchmark artifact`);
      return a;
    };
    return {
      start: vsPassive.data.starting_capital,
      strat: find(gross, 'OB-gated strategy'),
      dca: find(gross, 'Weekly DCA into BTC'),
      stratMtm: find(arms, 'OB-gated strategy'),
      dcaMtm: find(arms, 'Weekly DCA into BTC'),
    };
  }, [vsPassive.data, mtm.data]);

  const curves = useMemo(() => {
    if (!candles.data || !published || baseTrades.length === 0) return null;
    return computeBenchmarkCurves(candles.data, baseTrades, published.start);
  }, [candles.data, published, baseTrades]);

  const progress = useProgress(rootRef, runId, curves != null);

  const wins = baseTrades.filter((t) => t.pnl_pct > 0).length;
  const winRate = baseTrades.length ? (wins / baseTrades.length) * 100 : 0;

  const loadError = candles.error ?? vsPassive.error ?? mtm.error;
  if (loadError) return <section className="cmp panel">Failed to load comparison data: {loadError.message}</section>;
  if (!curves || !published) return <section className="cmp panel text-muted">Loading comparison...</section>;

  // Cross-check: the browser's curves must land on the published finals.
  const stratOk = Math.abs(curves.strategyFinal - published.strat.final_capital) < 0.01;
  const dcaOk = Math.abs(curves.dcaFinalAtLastBuy - published.dca.final_capital) < 0.01;

  const pts = curves.points;
  const maxV = Math.max(...pts.map((p) => Math.max(p.strategy, p.dca))) * 1.05;
  const minV = Math.min(...pts.map((p) => Math.min(p.strategy, p.dca))) * 0.9;
  const x = (i: number) => PAD.l + (i / (pts.length - 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - minV) / (maxV - minV)) * (H - PAD.t - PAD.b);
  const shown = Math.max(1, Math.round(ease(progress) * (pts.length - 1)));
  const visible = pts.slice(0, shown + 1);
  const path = (key: 'strategy' | 'dca') => visible.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join('');
  const head = visible[visible.length - 1];
  const done = progress >= 1;
  const ticks = [10000, 15000, 20000, 25000, 30000].filter((v) => v >= minV && v <= maxV);
  const yearMarks = pts
    .map((p, i) => ({ i, d: new Date(p.time * 1000) }))
    .filter(({ d, i }) => i > 0 && d.getUTCMonth() === 0 && d.getUTCDate() === 1);

  const barP = Math.min(Math.max((progress - 0.55) / 0.45, 0), 1);
  const rows: { label: string; note: string; s: number; d: number; fmt: (v: number) => string; better: 'high' | 'low' }[] = [
    { label: 'ENDING VALUE', note: 'from $10,000', s: published.strat.final_capital, d: published.dca.final_capital, fmt: money0, better: 'high' },
    {
      label: 'WORST DROP',
      note: 'daily closes',
      s: Math.abs(published.stratMtm.max_drawdown_daily_pct),
      d: Math.abs(published.dcaMtm.max_drawdown_daily_pct),
      fmt: (v) => `−${v.toFixed(2)}%`,
      better: 'low',
    },
    { label: 'TIME IN MARKET', note: 'share of 4h candles', s: published.strat.time_in_market_pct, d: published.dca.time_in_market_pct, fmt: (v) => `${v.toFixed(2)}%`, better: 'low' },
    { label: 'SHARPE RATIO', note: 'risk-adjusted, daily', s: published.stratMtm.sharpe_daily_mtm, d: published.dcaMtm.sharpe_daily_mtm, fmt: (v) => v.toFixed(2), better: 'high' },
  ];

  return (
    <section className="cmp panel" ref={rootRef}>
      <div className="cmp-spec">
        <span>FIG. 01 / HEAD-TO-HEAD</span>
        <span>BTCUSDT · 4H · 2022–2026 · $10,000 EACH · BEFORE COSTS</span>
      </div>
      <h2 className="cmp-headline">
        DCA ends <span className="cmp-hl-dca">richer.</span>
        <br />
        The strategy <span className="cmp-hl-strat">falls less.</span>
      </h2>
      <p className="cmp-sub">
        {published.strat.final_capital < published.dca.final_capital ? 'Weekly DCA finishes with more money' : 'The strategy finishes with more money'}, but the
        rule-based strategy's worst drop is {Math.abs(published.stratMtm.max_drawdown_daily_pct).toFixed(2)}% against DCA's{' '}
        {Math.abs(published.dcaMtm.max_drawdown_daily_pct).toFixed(2)}%, while holding Bitcoin only{' '}
        {published.strat.time_in_market_pct.toFixed(2)}% of the time.
      </p>

      <div className="cmp-chart-wrap">
        <div className="cmp-clock">{monthYear(head.time)}</div>
        <svg viewBox={`0 0 ${W} ${H}`} className="cmp-chart" role="img" aria-label="Account value over time, strategy versus weekly DCA">
          {ticks.map((v) => (
            <g key={v}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="cmp-grid" />
              <text x={PAD.l - 8} y={y(v) + 4} className="cmp-axis" textAnchor="end">
                {`$${v / 1000}K`}
              </text>
            </g>
          ))}
          {yearMarks.map(({ i, d }) => (
            <text key={i} x={x(i)} y={H - 12} className="cmp-axis" textAnchor="middle">
              {d.getUTCFullYear()}
            </text>
          ))}
          <line x1={PAD.l} x2={W - PAD.r} y1={y(published.start)} y2={y(published.start)} className="cmp-start" />
          <path d={path('dca')} className="cmp-line cmp-line-dca" />
          <path d={path('strategy')} className="cmp-line cmp-line-strat" />
          <circle cx={x(visible.length - 1)} cy={y(head.dca)} r={6} className="cmp-dot-dca" />
          <circle cx={x(visible.length - 1)} cy={y(head.strategy)} r={6} className="cmp-dot-strat" />
          <text x={x(visible.length - 1) + 12} y={y(head.dca) + 5} className="cmp-val cmp-val-dca">
            DCA {money0(head.dca)}
          </text>
          <text x={x(visible.length - 1) + 12} y={y(head.strategy) + (head.strategy > head.dca - 1500 ? 22 : 5)} className="cmp-val cmp-val-strat">
            STRATEGY {money0(head.strategy)}
          </text>
        </svg>
      </div>

      <div className="cmp-legend">
        <span className="cmp-key cmp-key-strat">Rule-based strategy</span>
        <span className="cmp-key cmp-key-dca">Weekly DCA ({curves.nWeeks} buys)</span>
        <button type="button" className="cmp-replay" onClick={() => setRunId((r) => r + 1)}>
          Replay
        </button>
      </div>

      <div className="cmp-bars">
        {rows.map((r) => {
          const max = Math.max(r.s, r.d);
          const stratWins = r.better === 'high' ? r.s > r.d : r.s < r.d;
          return (
            <div className="cmp-row" key={r.label}>
              <div className="cmp-row-label">
                {r.label}
                <small>{r.note}</small>
              </div>
              <div className="cmp-row-bars">
                {(['s', 'd'] as const).map((k) => (
                  <div className="cmp-bar-line" key={k}>
                    <div className={`cmp-bar cmp-bar-${k === 's' ? 'strat' : 'dca'}`} style={{ width: `${(r[k] / max) * 100 * ease(barP)}%` }} />
                    <span className="cmp-bar-val">
                      {r.fmt(r[k] * (done ? 1 : ease(barP)))}
                      {done && (k === 's') === stratWins && <span className="cmp-win">BETTER</span>}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
        <div className="cmp-row">
          <div className="cmp-row-label">
            WIN RATE<small>strategy only</small>
          </div>
          <div className="cmp-winrate">
            <strong>{(winRate * (done ? 1 : ease(barP))).toFixed(2)}%</strong> {wins} of {baseTrades.length} trades closed in profit. DCA never sells, so it has no
            win rate.
          </div>
        </div>
      </div>

      {done && <div className="cmp-scrawl">safer, not richer</div>}

      <p className="cmp-foot text-muted">
        Ending values, worst drops and Sharpe ratios are the published figures from <code>artifacts/benchmark_vs_passive.json</code> and{' '}
        <code>artifacts/benchmark_mtm.json</code>. The lines are recomputed in your browser from candles and /api/trades; the DCA line counts cash not
        yet invested so both start at $10,000. Both lines end at DCA's last weekly buy (29 Dec 2025), where DCA's published value is taken; the strategy's last trade closed 6 Dec 2025. Cross-check vs published finals:{' '}
        <span className={stratOk ? 'text-good' : 'text-critical'}>strategy {stratOk ? 'MATCH' : `MISMATCH ${money(curves.strategyFinal)}`}</span>,{' '}
        <span className={dcaOk ? 'text-good' : 'text-critical'}>DCA {dcaOk ? 'MATCH' : `MISMATCH ${money(curves.dcaFinalAtLastBuy)}`}</span>.
      </p>
    </section>
  );
}

import * as React from "react";
import { Link } from "react-router";
import { SERIES } from "../lib/chartPalette";
import { cn } from "../lib/utils";

/*
 * Small, dependency-free SVG charts following the dataviz rules:
 * thin marks with rounded data-ends on the baseline, recessive grid,
 * hover tooltips (hit areas larger than the marks), a legend for >= 2
 * series, direct labels, and a screen-reader table for every chart.
 * Colours: SERIES in fixed order (validated; see lib/chartPalette.ts).
 * Values and labels use text colours, never the series colour.
 */

export interface Point {
  label: string;
  value: number;
  /** Optional link (BarList rows become links to the matching list). */
  to?: string;
}

/** Measured width of a container, so charts draw in real pixels and their
 * text stays a constant, readable size at any card width. */
function useWidth<T extends HTMLElement>(fallback = 0): [React.RefObject<T>, number] {
  const ref = React.useRef<T>(null);
  // Starts at 0 (nothing drawn) so the chart never widens its container before measuring.
  const [width, setWidth] = React.useState(fallback);
  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [fallback]);
  return [ref, width];
}

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const pow = 10 ** Math.floor(Math.log10(v));
  const n = v / pow;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * pow;
}

function SrTable({ caption, headers, rows }: { caption: string; headers: string[]; rows: (string | number)[][] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}

function Tooltip({ x, y, children }: { x: number; y: number; children: React.ReactNode }) {
  return (
    <div
      className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg bg-ink px-2.5 py-1.5 text-xs font-medium text-white shadow-pop"
      style={{ left: x, top: y - 8 }}
    >
      {children}
    </div>
  );
}

/** Change over time, one series: line + soft area + crosshair tooltip. */
export function AreaChart({ data, caption, unit = "" }: { data: Point[]; caption: string; unit?: string }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = React.useState<number | null>(null);
  // Not measured yet: hold the space, draw nothing (avoids widening the container).
  if (W === 0) return <div ref={ref} aria-hidden className="w-full min-w-0" style={{ height: 220 }} />;
  const H = 220, padL = 32, padR = 12, padT = 12, padB = 26;
  const max = niceMax(Math.max(...data.map((d) => d.value)));
  const every = Math.max(1, Math.ceil(data.length / Math.max(2, Math.floor(W / 80))));
  const x = (i: number) => padL + (i * (W - padL - padR)) / Math.max(1, data.length - 1);
  const y = (v: number) => padT + (1 - v / max) * (H - padT - padB);
  const line = data.map((d, i) => `${i ? "L" : "M"}${x(i)},${y(d.value)}`).join(" ");
  const area = `${line} L${x(data.length - 1)},${y(0)} L${x(0)},${y(0)} Z`;
  const ticks = [0, max / 2, max];
  const last = data.length - 1;

  return (
    <div ref={ref} className="relative w-full min-w-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="block overflow-visible"
        role="img"
        aria-label={caption}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const i = Math.round(((px - padL) / (W - padL - padR)) * last);
          setHover(Math.max(0, Math.min(last, i)));
        }}
      >
        <defs>
          <linearGradient id="area-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={SERIES[0]} stopOpacity="0.18" />
            <stop offset="100%" stopColor={SERIES[0]} stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeDasharray={t ? "3 4" : undefined} />
            <text x={padL - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-[var(--color-faint)] text-[11px] tabular">
              {t}
            </text>
          </g>
        ))}
        {data.map((d, i) =>
          (i % every === 0 && last - i >= every / 2) || i === last ? (
            <text key={d.label} x={x(i)} y={H - 6} textAnchor="middle" className="fill-[var(--color-faint)] text-[11px]">
              {d.label}
            </text>
          ) : null,
        )}
        <path d={area} fill="url(#area-fill)" />
        <path d={line} fill="none" stroke={SERIES[0]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {/* Direct label on the latest point. */}
        <circle cx={x(last)} cy={y(data[last].value)} r="4" fill={SERIES[0]} stroke="var(--color-surface)" strokeWidth="2" />
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={padT} y2={y(0)} stroke="var(--color-line-strong)" />
            <circle cx={x(hover)} cy={y(data[hover].value)} r="5" fill={SERIES[0]} stroke="var(--color-surface)" strokeWidth="2" />
          </g>
        )}
      </svg>
      {hover !== null && (
        <Tooltip x={x(hover)} y={y(data[hover].value)}>
          {data[hover].label}: <span className="tabular">{data[hover].value}</span>
          {unit}
        </Tooltip>
      )}
      <SrTable caption={caption} headers={["Period", "Value"]} rows={data.map((d) => [d.label, d.value])} />
    </div>
  );
}

export interface StackRow {
  label: string;
  values: number[];
}

/** Composition per period: stacked columns, 2px surface gap, legend, totals. */
export function StackedColumns({ rows, series, caption }: { rows: StackRow[]; series: string[]; caption: string }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = React.useState<number | null>(null);
  // Not measured yet: hold the space, draw nothing (avoids widening the container).
  if (W === 0) return <div ref={ref} aria-hidden className="w-full min-w-0" style={{ height: 220 }} />;
  const H = 220, padL = 32, padR = 8, padT = 18, padB = 26;
  const totals = rows.map((r) => r.values.reduce((a, b) => a + b, 0));
  const max = niceMax(Math.max(...totals));
  const band = (W - padL - padR) / rows.length;
  const bw = Math.min(34, band * 0.56);
  const y = (v: number) => padT + (1 - v / max) * (H - padT - padB);
  return (
    <div ref={ref} className="relative w-full min-w-0">
      <Legend series={series} />
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="mt-3 block overflow-visible" role="img" aria-label={caption} onMouseLeave={() => setHover(null)}>
        {[0, max / 2, max].map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeDasharray={t ? "3 4" : undefined} />
            <text x={padL - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-[var(--color-faint)] text-[11px] tabular">
              {t}
            </text>
          </g>
        ))}
        {rows.map((r, i) => {
          const cx = padL + band * i + band / 2;
          let acc = 0;
          return (
            <g key={r.label} onMouseEnter={() => setHover(i)}>
              <rect x={cx - band / 2} y={padT} width={band} height={H - padT - padB} fill="transparent" />
              {r.values.map((v, s) => {
                const y0 = y(acc), y1 = y(acc + v);
                acc += v;
                const h = Math.max(0, y0 - y1 - (s ? 2 : 0));
                return v > 0 ? (
                  <rect key={s} x={cx - bw / 2} y={y1} width={bw} height={h} rx={s === r.values.length - 1 ? 4 : 0} fill={SERIES[s]} opacity={hover === null || hover === i ? 1 : 0.45} />
                ) : null;
              })}
              <text x={cx} y={y(totals[i]) - 6} textAnchor="middle" className="fill-[var(--color-muted)] text-[11px] font-semibold tabular">
                {totals[i]}
              </text>
              <text x={cx} y={H - 6} textAnchor="middle" className="fill-[var(--color-faint)] text-[11px]">
                {r.label}
              </text>
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <Tooltip x={padL + band * hover + band / 2} y={y(totals[hover]) + 22}>
          <span className="font-semibold">{rows[hover].label}</span>
          {series.map((s, i) => (
            <span key={s} className="ml-2">
              {s}: <span className="tabular">{rows[hover].values[i]}</span>
            </span>
          ))}
        </Tooltip>
      )}
      <SrTable caption={caption} headers={["Period", ...series]} rows={rows.map((r) => [r.label, ...r.values])} />
    </div>
  );
}

export function Legend({ series }: { series: string[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
      {series.map((s, i) => (
        <li key={s} className="inline-flex items-center gap-2">
          <span aria-hidden className="size-2.5 rounded-sm" style={{ background: SERIES[i] }} />
          {s}
        </li>
      ))}
    </ul>
  );
}

/** Magnitude by category: horizontal bars with values (one series). */
export function BarList({ data, caption, className }: { data: Point[]; caption: string; className?: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className={cn("space-y-3", className)}>
      <ul className="space-y-3" aria-label={caption}>
        {data.map((d) => {
          const row = (
            <>
              <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                <span className={cn("truncate text-ink-2", d.to && "group-hover:text-brand group-hover:underline")}>{d.label}</span>
                <span className="tabular font-semibold text-ink">{d.value}</span>
              </div>
              <div className="h-2 rounded-full bg-subtle">
                <div
                  className="h-2 rounded-full transition-[width] duration-500"
                  style={{ width: `${(d.value / max) * 100}%`, background: SERIES[0], minWidth: d.value ? 6 : 0 }}
                />
              </div>
            </>
          );
          return (
            <li key={d.label}>
              {d.to ? (
                <Link to={d.to} className="group -mx-2 block rounded-lg px-2 py-1 transition-colors hover:bg-subtle/60">
                  {row}
                </Link>
              ) : (
                row
              )}
            </li>
          );
        })}
      </ul>
      <SrTable caption={caption} headers={["Category", "Count"]} rows={data.map((d) => [d.label, d.value])} />
    </div>
  );
}

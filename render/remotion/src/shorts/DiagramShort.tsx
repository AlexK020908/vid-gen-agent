import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CODE_TONES, D, DBadge, DEdge, DiagramShortProps, DKey, DNode, NODE_TONES, TEXT_TONES} from './diagram';
import {Icon} from './DiagramIcons';
import {FONT, loadFonts, MONO} from './fonts';

loadFonts();

// A systems short (SHORTS.md, "How a systems short is made"): a dark frame with the title, the subtitle and the stat
// pills, the diagram with its requests moving, the caption, the code panel and the end card, which crossfades back to
// the first frame so the short loops. Everything here is drawn from the timeline diagram/sim.py worked out, as a
// function of the time, so the first frame can be drawn again on top of the last.

const EPS = 1e-6;
const RESIZE = 0.25;   // seconds the code panel takes to grow or shrink to the next block's lines
const ease = Easing.inOut(Easing.cubic);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const stepAt = <T,>(steps: [number, T][], t: number, fallback: T): [number, T] => {
  let cur: [number, T] = [0, fallback];
  for (const s of steps) {
    if (s[0] <= t + EPS) cur = s;
    else break;
  }
  return cur;
};

const keyAt = (keys: DKey[], t: number): [number, number, number] => {
  if (!keys.length) return [0, 0, 0];
  if (t <= keys[0][0]) return [keys[0][1], keys[0][2], keys[0][3]];
  for (let i = 0; i < keys.length - 1; i++) {
    const [ta, xa, ya, oa] = keys[i];
    const [tb, xb, yb, ob] = keys[i + 1];
    if (t >= ta && t < tb) {
      const u = tb - ta < EPS ? 1 : ease((t - ta) / (tb - ta));
      return [xa + (xb - xa) * u, ya + (yb - ya) * u, oa + (ob - oa) * u];
    }
  }
  const last = keys[keys.length - 1];
  return [last[1], last[2], last[3]];
};

const edgeOpacity = (e: DEdge, t: number): number => {
  const k = e.keys;
  if (!k.length) return 0;
  if (t <= k[0][0]) return k[0][1];
  for (let i = 0; i < k.length - 1; i++) {
    if (t >= k[i][0] && t < k[i + 1][0]) {
      const span = k[i + 1][0] - k[i][0];
      return k[i][1] + (k[i + 1][1] - k[i][1]) * (span < EPS ? 1 : ease((t - k[i][0]) / span));
    }
  }
  return k[k.length - 1][1];
};

// in over `inS` from `from`, out over `outS` before `to`
const shownFor = (t: number, from: number, to: number, inS: number, outS: number): number => {
  if (t < from - EPS || t >= to) return 0;
  const a = inS > 0 ? interpolate(t, [from, from + inS], [0, 1], clamp) : 1;
  const b = outS > 0 ? interpolate(t, [to - outS, to], [1, 0], clamp) : 1;
  return Math.min(a, b);
};

const fmt = (v: number | null): string => (v === null || v === undefined ? '—' : Number.isInteger(v)
  ? v.toLocaleString('en-US') : String(v));

type Pos = {x: number; y: number; o: number};

const Scene: React.FC<{p: DiagramShortProps; t: number}> = ({p, t}) => {
  const g = p.geometry;
  const pos: Record<string, Pos> = {};
  for (const n of p.nodes) {
    const [x, y, o] = keyAt(n.keys, t);
    pos[n.id] = {x, y, o};
  }
  const ends = (a: string, b: string): [number, number, number, number] | null => {
    const A = pos[a];
    const B = pos[b];
    if (!A || !B) return null;
    const dx = B.x - A.x;
    const dy = B.y - A.y;
    const len = Math.max(EPS, Math.hypot(dx, dy));
    const ux = dx / len;
    const uy = dy / len;
    const trim = Math.min(g.trim, len / 2 - 2);
    return [A.x + ux * trim, A.y + uy * trim, B.x - ux * trim, B.y - uy * trim];
  };
  const end = p.end;
  const dim = end ? interpolate(t, [end.from, end.from + 0.4], [1, 0.08], clamp) : 1;
  const [, by0, , by1] = g.box;

  return (
    <AbsoluteFill style={{backgroundColor: D.bg}}>
      {/* the title, the subtitle and the pills */}
      <div style={{position: 'absolute', left: g.head_left, width: g.head_right - g.head_left, top: g.title_top,
        textAlign: 'center', fontFamily: FONT, fontWeight: 900, fontSize: g.title_size, lineHeight: 1.1,
        color: '#ffffff', whiteSpace: 'nowrap'}}>
        {p.title}
      </div>
      {p.subtitles.map((s, i) => {
        const o = shownFor(t, s.from, s.to, s.from > EPS ? 0.3 : 0, i < p.subtitles.length - 1 ? 0.3 : 0);
        return o > 0 ? (
          <div key={`sub${i}`} style={{position: 'absolute', left: g.head_left, width: g.head_right - g.head_left,
            top: g.subtitle_top, textAlign: 'center', fontFamily: MONO, fontWeight: 400, fontSize: s.size,
            letterSpacing: 1.5, color: D.grey, whiteSpace: 'nowrap', opacity: o}}>
            {s.text}
          </div>
        ) : null;
      })}
      <div style={{position: 'absolute', left: g.head_left, width: g.head_right - g.head_left, top: g.pills_top,
        display: 'flex', justifyContent: 'center', gap: g.pill_gap, opacity: dim < 1 ? 0.25 + 0.75 * dim : 1}}>
        {p.stats.map((s) => {
          const shown = Math.max(0, ...s.spans.map(([a, b]) => shownFor(t, a, b, a > EPS ? 0.25 : 0, 0)));
          let cur: [number, number | null, string] = [0, null, 'grey'];
          for (const st of s.steps) {
            if (st[0] <= t + EPS) cur = st;
            else break;
          }
          const [at, v, tone] = cur;
          const color = TEXT_TONES[tone] ?? TEXT_TONES.white;
          const bump = 1 + 0.12 * interpolate(t - at, [0, 0.18], [1, 0], clamp) * (at > EPS ? 1 : 0);
          return (
            <div key={s.name} style={{height: g.pill_h, borderRadius: g.pill_h / 2, padding: `0 ${g.pill_pad}px`,
              display: 'flex', alignItems: 'center', gap: 14, backgroundColor: D.pillBg, opacity: shown,
              border: `1.5px solid ${color}55`, boxShadow: `0 0 18px ${color}33`}}>
              <span style={{fontFamily: MONO, fontWeight: 500, fontSize: g.pill_text, letterSpacing: 2.5,
                color: D.pillName}}>{s.name}</span>
              <span style={{display: 'flex', alignItems: 'baseline', gap: 6}}>
                <span style={{fontFamily: MONO, fontWeight: 800, fontSize: g.pill_value, color, display: 'inline-block',
                  transform: `scale(${bump})`}}>{fmt(v)}</span>
                {s.unit ? <span style={{fontFamily: MONO, fontWeight: 500, fontSize: g.pill_text, color,
                  opacity: 0.75}}>{s.unit}</span> : null}
              </span>
            </div>
          );
        })}
      </div>

      {/* the diagram */}
      <AbsoluteFill style={{opacity: dim}}>
        <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0}}>
          {p.edges.map((e, i) => {
            const o = Math.min(edgeOpacity(e, t), pos[e.a]?.o ?? 0, pos[e.b]?.o ?? 0);
            const seg = ends(e.a, e.b);
            if (o <= 0.01 || !seg) return null;
            const dashed = stepAt(e.dashed, t, false)[1];
            return <line key={`e${i}`} x1={seg[0]} y1={seg[1]} x2={seg[2]} y2={seg[3]} stroke={dashed ? D.edgeDead : D.edge}
              strokeWidth={3} strokeDasharray={dashed ? '12 12' : undefined} strokeLinecap="round" opacity={o} />;
          })}
          {p.nodes.filter((n) => n.ring).map((n) => {
            const q = pos[n.id];
            if (q.o <= 0.01) return null;
            const state = stepAt(n.states, t, 'healthy')[1];
            const color = state === 'dead' ? NODE_TONES.red : state === 'failing' || state === 'warning' ? NODE_TONES.orange
              : state === 'cold' ? NODE_TONES.grey : NODE_TONES.green;
            return <circle key={`r${n.id}`} cx={q.x} cy={q.y} r={g.ring} fill="none" stroke={color} strokeWidth={2}
              opacity={q.o * (state === 'dead' ? 0.42 : 0.26)} />;
          })}
          {p.nodes.map((n) => {
            const q = pos[n.id];
            const waiting = stepAt(n.queue, t, 0)[1];
            if (q.o <= 0.01 || waiting <= 0) return null;
            const color = NODE_TONES[n.tone] ?? NODE_TONES.orange;
            const shown = Math.min(waiting, g.queue_dots);
            const top = q.y - g.icon / 2 - 12;
            return (
              <g key={`q${n.id}`} opacity={q.o}>
                {Array.from({length: shown}, (_, i) => (
                  <circle key={i} cx={q.x} cy={top - i * g.queue_step} r={g.queue_dot} fill={color} />
                ))}
                {waiting > g.queue_dots ? (
                  <text x={q.x + 14} y={top - (shown - 1) * g.queue_step + 10} fill={color} fontFamily={FONT}
                    fontWeight={800} fontSize={g.queue_more}>{`+${waiting - g.queue_dots}`}</text>
                ) : null}
              </g>
            );
          })}
          {p.dots.map((d, i) => {
            const [a, b, t0, t1, kind, followed] = d;
            if (t < t0 - EPS || t > t1 + EPS) return null;
            const seg = ends(a, b);
            if (!seg) return null;
            const u = t1 - t0 < EPS ? 1 : (t - t0) / (t1 - t0);
            const x = seg[0] + (seg[2] - seg[0]) * u;
            const y = seg[1] + (seg[3] - seg[1]) * u;
            const color = kind === 'back' ? D.back : D.dot;
            return (
              <g key={`d${i}`}>
                <circle cx={x} cy={y} r={17} fill={color} opacity={0.18} />
                <circle cx={x} cy={y} r={followed ? 10 : 8.5} fill={color} />
                {followed ? <circle cx={x} cy={y} r={16} fill="none" stroke="#ffffff" strokeWidth={3} opacity={0.9} /> : null}
              </g>
            );
          })}
          {p.flashes.map(([node, t0], i) => {
            if (t < t0 - EPS || t > t0 + 0.45) return null;
            const q = pos[node];
            if (!q) return null;
            const u = (t - t0) / 0.45;
            return <circle key={`f${i}`} cx={q.x} cy={q.y} r={g.icon * (0.5 + 0.5 * u)} fill="none"
              stroke={NODE_TONES.red} strokeWidth={5 * (1 - u) + 1} opacity={0.9 * (1 - u)} />;
          })}
        </svg>
        {p.nodes.map((n) => <NodeView key={n.id} n={n} q={pos[n.id]} t={t} g={g} />)}
        {p.badges.map((b, i) => <Badge key={`bd${i}`} b={b} q={pos[b[0]]} t={t} g={g} />)}
      </AbsoluteFill>

      {/* the caption */}
      {p.captions.map((c, i) => {
        const o = shownFor(t, c.from, c.to, 0.18, i < p.captions.length - 1 ? 0.22 : 0.3);
        if (o <= 0) return null;
        const rise = (1 - interpolate(t, [c.from, c.from + 0.25], [0, 1], clamp)) * 12;
        const total = c.lines.length * c.size * 1.15;
        return (
          <div key={`c${i}`} style={{position: 'absolute', left: g.left, width: g.right - g.left,
            top: g.caption_top + (g.caption_h - total) / 2 + rise, textAlign: 'center', fontFamily: FONT, fontWeight: 800,
            fontSize: c.size, lineHeight: 1.15, color: TEXT_TONES[c.tone] ?? TEXT_TONES.white, opacity: o}}>
            {c.lines.map((l, j) => <div key={j} style={{whiteSpace: 'nowrap'}}>{l}</div>)}
          </div>
        );
      })}

      {/* the code panel */}
      {p.code && g.code_top !== null ? <CodePanel p={p} t={t} /> : null}

      {/* the end card */}
      {end && t >= end.from - EPS ? (() => {
        const o = interpolate(t, [end.from + 0.1, end.from + 0.45], [0, 1], clamp);
        const grow = 0.92 + 0.08 * ease(Math.min(1, Math.max(0, (t - end.from - 0.1) / 0.4)));
        // in the middle of the space between the pills and the code panel
        const cy = (by0 + (g.code_top ?? by1 + 120)) / 2;
        return (
          <div style={{position: 'absolute', left: g.left, width: g.right - g.left, top: cy - g.end_big * 1.2, opacity: o,
            transform: `scale(${grow})`, textAlign: 'center'}}>
            <div style={{fontFamily: MONO, fontWeight: 800, fontSize: g.end_big, lineHeight: 1.2, whiteSpace: 'nowrap'}}>
              <span style={{color: TEXT_TONES[end.before.tone] ?? TEXT_TONES.red}}>{end.before.text}</span>
              <span style={{color: D.grey, fontSize: g.end_big * 0.6, margin: '0 18px'}}>→</span>
              <span style={{color: TEXT_TONES[end.after.tone] ?? TEXT_TONES.green}}>{end.after.text}</span>
            </div>
            <div style={{marginTop: 26, fontFamily: FONT, fontWeight: 800, fontSize: g.end_claim, lineHeight: 1.2,
              color: '#ffffff'}}>
              {end.claim_lines.map((l, j) => <div key={j} style={{whiteSpace: 'nowrap'}}>{l}</div>)}
            </div>
            {end.note ? (
              <div style={{marginTop: 22, fontFamily: MONO, fontWeight: 400, fontSize: g.end_note, letterSpacing: 1,
                color: D.grey, whiteSpace: 'nowrap'}}>{end.note}</div>
            ) : null}
          </div>
        );
      })() : null}
    </AbsoluteFill>
  );
};

const NodeView: React.FC<{n: DNode; q: Pos; t: number; g: DiagramShortProps['geometry']}> = ({n, q, t, g}) => {
  if (q.o <= 0.01) return null;
  const [since, state] = stepAt(n.states, t, 'healthy');
  const tone = NODE_TONES[n.tone] ?? NODE_TONES.blue;
  const into = t - since;
  let color = tone;
  let iconO = 1;
  let glow = 'none';
  if (state === 'dead') color = NODE_TONES.red;
  else if (state === 'failing') iconO = interpolate(into, [0, 0.3], [1, 0.4], clamp);
  else if (state === 'cold') {
    color = NODE_TONES.grey;
    iconO = 0.55;
  } else if (state === 'busy') glow = `drop-shadow(0 0 14px ${tone})`;
  else if (state === 'warning') glow = `drop-shadow(0 0 ${8 + 8 * Math.abs(Math.sin(t * Math.PI * 2))}px ${NODE_TONES.orange})`;
  const count = stepAt(n.counts, t, 0);
  const bump = 1 + 0.16 * interpolate(t - count[0], [0, 0.16], [1, 0], clamp) * (count[1] > 0 ? 1 : 0);
  const cross = state === 'dead' ? interpolate(into, [0, 0.25], [0, 1], clamp) : 0;
  const half = g.icon / 2;
  return (
    <div style={{position: 'absolute', left: 0, top: 0, opacity: q.o}}>
      <div style={{position: 'absolute', left: q.x - half, top: q.y - half, width: g.icon, height: g.icon, opacity: iconO,
        filter: glow}}>
        <Icon name={n.icon} size={g.icon} color={color} />
        {cross > 0 ? (
          <svg width={g.icon} height={g.icon} viewBox="0 0 64 64" style={{position: 'absolute', left: 0, top: 0,
            overflow: 'visible'}}>
            <path d={`M10 10L${10 + 44 * cross} ${10 + 44 * cross}`} stroke={NODE_TONES.red} strokeWidth={5}
              strokeLinecap="round" />
            <path d={`M54 10L${54 - 44 * cross} ${10 + 44 * cross}`} stroke={NODE_TONES.red} strokeWidth={5}
              strokeLinecap="round" />
          </svg>
        ) : null}
      </div>
      {n.counter ? (
        <div style={{position: 'absolute', left: q.x + half + 12, top: q.y - half - 6, fontFamily: FONT, fontWeight: 800,
          fontSize: g.counter, lineHeight: 1, color: tone, opacity: state === 'failing' ? 0.55 : 1,
          transform: `scale(${bump})`, transformOrigin: 'left center'}}>
          {count[1]}
        </div>
      ) : null}
      <div style={{position: 'absolute', left: q.x - 200, width: 400, top: q.y + half + 10, textAlign: 'center',
        fontFamily: FONT, fontWeight: 700, fontSize: g.label, lineHeight: 1.25, color: tone, whiteSpace: 'nowrap',
        WebkitTextStroke: `12px ${D.bg}`, paintOrder: 'stroke fill'}}>
        {n.label}
      </div>
    </div>
  );
};

// What just happened at a node, under its label: HIT, MISS, LOST, or how long it took. It pops in, and the next one at
// the node replaces it
const Badge: React.FC<{b: DBadge; q: Pos | undefined; t: number; g: DiagramShortProps['geometry']}> = ({b, q, t, g}) => {
  const [, from, to, text, tone, side] = b;
  if (!q || q.o <= 0.01 || t < from - EPS || t >= to) return null;
  const color = TEXT_TONES[tone] ?? TEXT_TONES.white;
  const pop = 1 + 0.18 * interpolate(t - from, [0, 0.14], [1, 0], clamp);
  const o = q.o * interpolate(t, [to - 0.12, to], [1, 0], clamp);
  const right = side === 'right';     // beside the icon, under its counter, where nodes are stacked in a column
  return (
    <div style={{position: 'absolute', left: right ? q.x + g.icon / 2 + 12 : q.x - 200, width: right ? 400 : 400,
      top: right ? q.y + 4 : q.y + g.icon / 2 + 10 + g.label * 1.25 + 8, display: 'flex',
      justifyContent: right ? 'flex-start' : 'center', opacity: o, transformOrigin: right ? 'left center' : 'center'}}>
      <div style={{height: g.badge_h, padding: `0 ${g.badge_pad}px`, borderRadius: g.badge_h / 2, display: 'flex',
        alignItems: 'center', fontFamily: MONO, fontWeight: 800, fontSize: g.badge, color, backgroundColor: D.pillBg,
        border: `1.5px solid ${color}88`, boxShadow: `0 0 14px ${color}44`, transform: `scale(${pop})`,
        whiteSpace: 'nowrap'}}>
        {text}
      </div>
    </div>
  );
};

const CodePanel: React.FC<{p: DiagramShortProps; t: number}> = ({p, t}) => {
  const g = p.geometry;
  const top = g.code_top as number;
  const blocks = p.code?.blocks ?? [];
  const end = p.end;
  const green = end ? interpolate(t, [end.from, end.from + 0.4], [0, 1], clamp) : 0;
  const tall = (b: {lines: unknown[]}): number => (b.lines.length ? b.lines.length * g.code_line + 2 * g.code_pad : 0);
  // the code switches on the frame its phase starts, so a line lit there is never faded out; the panel grows to a
  // longer block just before and shrinks to a shorter one just after, so no line that runs is ever cut off
  let height = blocks.length ? tall(blocks[0]) : 0;
  for (let i = 1; i < blocks.length; i++) {
    const [a, b] = [tall(blocks[i - 1]), tall(blocks[i])];
    const from = blocks[i].from;
    const span: [number, number] = b > a ? [from - RESIZE, from] : [from, from + RESIZE];
    if (t >= span[0]) height = interpolate(t, span, [a, b], {...clamp, easing: ease});
  }
  if (height <= 0) return null;
  return (
    <div style={{position: 'absolute', left: g.left, width: g.right - g.left, top, height,
      borderRadius: 14, backgroundColor: D.panel, border: `1.5px solid ${D.panelBorder}`, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: -1.5, borderRadius: 14, border: `1.5px solid ${TEXT_TONES.green}`,
        opacity: green * 0.6}} />
      {blocks.map((b, bi) => {
        const o = t >= b.from - EPS && t < b.to - EPS ? 1 : bi === blocks.length - 1 && t >= b.to - EPS ? 1 : 0;
        if (o <= 0) return null;
        return (
          <div key={`b${bi}`} style={{position: 'absolute', inset: 0, opacity: o}}>
            {b.lines.map((line, li) => {
              const n = li + 1;
              // a line blinks each time a request runs it: fully lit on the frame its dot lands, which is when its
              // sound plays (the same event), then fading; run again before it's out, it drops for the frame before,
              // so it visibly blinks
              let lit = 0;
              let lost = false;
              for (const [ln, a, z, kind] of b.hl) {
                if (ln !== n || t < a - EPS || t >= z) continue;
                const d = Math.max(0, t - a);
                const cut = z < a + g.hold + g.blink - EPS && t >= z - g.gap - EPS;
                const v = cut ? g.dip : d < g.hold ? 1 : Math.max(0, 1 - (d - g.hold) / g.blink);
                if (v >= lit) lost = kind === 'lost';
                lit = Math.max(lit, v);
              }
              const flash = lit;
              const dimFrom = b.dims.find(([ln]) => ln === n)?.[1];
              const faded = dimFrom === undefined ? 0 : interpolate(t, [dimFrom, dimFrom + 0.3], [0, 1], clamp);
              const y = g.code_pad + li * g.code_line;
              return (
                <div key={li} style={{position: 'absolute', left: 0, right: 0, top: y, height: g.code_line}}>
                  {lit > 0 ? (
                    <>
                      <div style={{position: 'absolute', inset: 0, backgroundColor: lost ? D.lostBand : D.band,
                        opacity: lit}} />
                      {lost ? null : <div style={{position: 'absolute', inset: 0, backgroundColor: D.flash,
                        opacity: flash}} />}
                      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 5,
                        backgroundColor: lost ? D.lostBar : D.flashBar, opacity: flash}} />
                    </>
                  ) : null}
                  <div style={{position: 'absolute', left: 28, top: 0, height: g.code_line, display: 'flex',
                    alignItems: 'center', fontFamily: MONO, fontWeight: 500, fontSize: g.code_size, whiteSpace: 'pre',
                    opacity: 1 - 0.78 * faded}}>
                    {line.map(([text, kind], k) => (
                      <span key={k} style={{color: CODE_TONES[kind] ?? CODE_TONES.text}}>{text}</span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

export const DiagramShort: React.FC<DiagramShortProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  // the last moments crossfade into the first frame, so when the platform loops the short there's no seam
  const back = interpolate(t, [p.loop.from, p.loop.to - 1 / fps], [0, 1], clamp);
  return (
    <AbsoluteFill style={{backgroundColor: D.bg}}>
      <Scene p={p} t={t} />
      {back > 0 ? (
        <AbsoluteFill style={{opacity: ease(back)}}>
          <Scene p={p} t={0} />
        </AbsoluteFill>
      ) : null}
      {p.audio ? <Audio src={staticFile(p.audio)} /> : null}
    </AbsoluteFill>
  );
};

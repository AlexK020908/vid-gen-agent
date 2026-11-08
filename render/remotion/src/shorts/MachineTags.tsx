import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT} from './fonts';
import {MTag, Track} from './machine';
import {TagMark} from './Overlays';
import {SHORT_H, SHORT_W, TONES} from './types';

const OUTLINE = 'rgba(30, 16, 4, 0.9)';

const fadeIn = (frame: number, a: number, b: number, len = 4): number => {
  const l = Math.max(0.5, Math.min(len, (b - a) / 2 - 0.01));
  return interpolate(frame, [a, a + l, b - l, b], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
};

const heavy = (color: string, size: number): React.CSSProperties => ({
  fontFamily: FONT, fontWeight: 900, fontSize: size, color, textTransform: 'uppercase', letterSpacing: 0.5,
  WebkitTextStroke: `3px ${OUTLINE}`, paintOrder: 'stroke fill', textShadow: '0 3px 10px rgba(0,0,0,0.4)',
  whiteSpace: 'pre-line', textAlign: 'center', lineHeight: 1.05,
});

const pointAt = (track: Track | undefined, frame: number): [number, number, boolean] | null => {
  if (!track || !track.points.length) return null;
  const i = Math.max(0, Math.min(track.points.length - 1, frame - track.first));
  return track.points[i];
};

const Arrow: React.FC<{dir: 'up' | 'down' | 'updown'; color: string; size: number}> = ({dir, color, size}) => (
  <svg width={size * 0.55} height={size} viewBox="0 0 12 24" style={{marginRight: 10}}>
    {dir !== 'up' ? <path d="M6 2 L6 22 M1.5 17 L6 22 L10.5 17" stroke={color} strokeWidth={2} fill="none" /> : null}
    {dir !== 'down' ? <path d="M6 22 L6 2 M1.5 7 L6 2 L10.5 7" stroke={color} strokeWidth={2} fill="none" /> : null}
  </svg>
);

const Thermometer: React.FC<{size: number}> = ({size}) => (
  <svg width={size * 0.6} height={size} viewBox="0 0 14 24" style={{marginRight: 10}}>
    <rect x="5" y="1.5" width="4" height="15" rx="2" stroke="white" strokeWidth="1.6" fill="none" />
    <circle cx="7" cy="19" r="3.6" stroke="white" strokeWidth="1.6" fill="#FF8A3D" />
    <rect x="6" y="8" width="2" height="9" fill="#FF8A3D" />
  </svg>
);

// The tags of a whole machine short: TagMark's fail, warn and mode, and the rest of reference A's overlays
export const MachineTag: React.FC<{t: MTag; tracks: Record<string, Track>}> = ({t, tracks}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const a = Math.round(t.from * fps);
  const b = Math.round(t.to * fps);
  if (frame < a || frame >= b) return null;
  const opacity = fadeIn(frame, a, b);
  const [ax, ay] = t.at ?? [0.5, 0.3];
  const color = TONES[t.tone ?? 'white'];
  if (t.kind === 'fail' || t.kind === 'mode' || t.kind === 'ok') {
    return <TagMark t={{kind: t.kind, text: t.text, icon: t.kind === 'ok' ? 'check' : t.icon === 'clock' ? 'clock' : 'x', from: a, to: b,
      at: t.at, size: t.size}} />;
  }
  if (t.kind === 'warn') {
    const size = t.size ?? 40;
    return (
      <div style={{position: 'absolute', left: ax * SHORT_W, top: ay * SHORT_H, transform: 'translate(-50%,-50%)',
        display: 'flex', alignItems: 'center', opacity, ...heavy(TONES.red, size)}}>
        <svg width={size * 1.1} height={size} viewBox="0 0 24 22" style={{marginRight: size * 0.25}}>
          <path d="M12 1.5 L23 20.5 L1 20.5 Z" fill={TONES.yellow} stroke={OUTLINE} strokeWidth={1.4} />
          <path d="M12 8 L12 14 M12 16.5 L12 17.6" stroke={OUTLINE} strokeWidth={2.2} strokeLinecap="round" />
        </svg>
        {t.text}
      </div>
    );
  }
  if (t.kind === 'question') {
    const bob = Math.sin((frame - a) / fps * Math.PI * 2 * 0.8) * 10;
    const s = spring({frame: frame - a, fps, config: {damping: 12, stiffness: 160}});
    return (
      <div style={{position: 'absolute', left: ax * SHORT_W, top: ay * SHORT_H + bob,
        transform: `translate(-50%,-50%) scale(${s})`, opacity, ...heavy('white', 88)}}>?</div>
    );
  }
  if (t.kind === 'multiplier') {
    const steps = t.steps ?? [[t.from, 1]];
    const now = frame / fps;
    const cur = steps.filter(([s]) => s <= now + 1e-6).pop() ?? steps[0];
    return (
      <div style={{position: 'absolute', left: ax * SHORT_W, top: ay * SHORT_H, transform: 'translate(0,-50%)',
        opacity, ...heavy('white', 76), textTransform: 'none'}}>×{cur[1]}</div>
    );
  }
  if (t.kind === 'section') {
    return (
      <div style={{position: 'absolute', left: ax * SHORT_W, top: ay * SHORT_H, transform: 'translate(-50%,-50%)',
        opacity, fontFamily: FONT, fontWeight: 600, fontSize: 24, letterSpacing: 3, color: 'white',
        textTransform: 'uppercase', WebkitTextStroke: `1px ${OUTLINE}`, paintOrder: 'stroke fill',
        whiteSpace: 'nowrap'}}>
        {t.text}
      </div>
    );
  }
  if (t.kind === 'stat') {
    const icon = t.icon;
    return (
      <div style={{position: 'absolute', left: ax * SHORT_W, top: ay * SHORT_H, transform: 'translate(-50%,-50%)',
        opacity, display: 'flex', alignItems: 'center'}}>
        {icon === 'up' || icon === 'down' || icon === 'updown' ? <Arrow dir={icon} color={color} size={44} /> : null}
        {icon === 'thermo' ? <Thermometer size={46} /> : null}
        <div>
          <div style={icon ? {...heavy(color, 36), textAlign: 'left'} : {fontFamily: FONT, fontWeight: 500,
            fontSize: 26, color, whiteSpace: 'pre-line', textShadow: '0 1px 6px rgba(0,0,0,0.6)',
            textAlign: 'center'}}>{t.text}</div>
          {t.sub ? <div style={{fontFamily: FONT, fontWeight: 500, fontSize: 22, color: '#FFE9C2',
            textShadow: '0 1px 6px rgba(0,0,0,0.6)'}}>{t.sub}</div> : null}
        </div>
      </div>
    );
  }
  if (t.kind === 'count') {
    // a big number running up and settling, white-hot with a colored halo, and what it counts under it
    const halo = (size: number): string => [0.12, 0.3, 0.7].map((k) => `0 0 ${Math.round(size * k)}px ${color}`).join(', ');
    const share = interpolate(frame, [a, a + (b - a) * 0.7], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    const value = (t.start ?? 0) + ((t.end ?? 0) - (t.start ?? 0)) * (1 - (1 - share) * (1 - share));
    // to about three figures as it runs, so 40,000 ticks by hundreds and 20 by ones, and exactly what it says at the end
    const step = Math.max(1, 10 ** (Math.floor(Math.log10(Math.max(1, Math.abs(t.end ?? 0)))) - 2));
    const shown = share >= 1 ? (t.end ?? 0) : Math.round(value / step) * step;
    const s = interpolate(frame, [a, a + 5], [0.86, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    return (
      <div style={{position: 'absolute', left: ax * SHORT_W, top: ay * SHORT_H, transform: `translate(-50%,-50%) scale(${s})`,
        opacity, textAlign: 'center', fontFamily: FONT, color: '#FFF3DC', whiteSpace: 'nowrap'}}>
        <div style={{fontWeight: 900, fontSize: 236, lineHeight: 1, letterSpacing: 2, fontVariantNumeric: 'tabular-nums',
          textShadow: halo(170)}}>{shown.toLocaleString('en-US')}</div>
        <div style={{fontWeight: 800, fontSize: 70, letterSpacing: 4, marginTop: 10, textShadow: halo(70)}}>{t.text}</div>
      </div>
    );
  }
  if (t.kind === 'title') {
    const s = interpolate(frame, [a, a + 8], [0.92, 1], {extrapolateRight: 'clamp'});
    return (
      <AbsoluteFill style={{alignItems: 'center', opacity}}>
        <div style={{position: 'absolute', top: SHORT_H * 0.17, transform: `scale(${s})`, ...heavy('white', 104)}}>
          {t.text}
        </div>
      </AbsoluteFill>
    );
  }
  if (t.kind === 'footage') {
    return (
      <div style={{position: 'absolute', left: SHORT_W * 0.06, top: SHORT_H * 0.11, opacity, fontFamily: FONT,
        textShadow: '0 1px 6px rgba(0,0,0,0.7)'}}>
        <div style={{fontSize: 22, fontWeight: 700, letterSpacing: 2, color: 'white'}}>
          <span style={{color: '#FF3B30', marginRight: 8}}>●</span>{t.text}
        </div>
        {t.sub ? <div style={{fontSize: 26, fontWeight: 500, color: 'white', marginTop: 4}}>{t.sub}</div> : null}
      </div>
    );
  }
  if (t.kind === 'credit') {
    return (
      <AbsoluteFill style={{alignItems: 'center', opacity}}>
        <div style={{position: 'absolute', top: SHORT_H * (t.at?.[1] ?? 0.785), fontFamily: FONT, fontSize: 20,
          fontWeight: 500, color: 'rgba(255,255,255,0.9)', textShadow: '0 1px 5px rgba(0,0,0,0.8)',
          whiteSpace: 'pre-line', textAlign: 'center'}}>{t.text}</div>
      </AbsoluteFill>
    );
  }
  // dimension: a white line with arrowheads between two tracked points, its label at the middle on the right;
  // deeper: a white dashed line at the old depth and a yellow arrow down to the new tip, with DEEPER
  const p = pointAt(tracks[t.anchor ?? ''], frame);
  const q = pointAt(tracks[t.anchor2 ?? ''], frame);
  if (!p || !q) return null;
  const [x1, y1] = [p[0] * SHORT_W, p[1] * SHORT_H];
  const y2 = q[1] * SHORT_H;   // the line is vertical, at the first point's x
  if (t.kind === 'dimension') {
    const x = x1 + 70;
    return (
      <AbsoluteFill style={{opacity}}>
        <svg width={SHORT_W} height={SHORT_H} style={{position: 'absolute'}}>
          <line x1={x} y1={y1} x2={x} y2={y2} stroke="white" strokeWidth={3} />
          <path d={`M${x - 10} ${y1 + 16} L${x} ${y1} L${x + 10} ${y1 + 16}`} stroke="white" strokeWidth={3} fill="none" />
          <path d={`M${x - 10} ${y2 - 16} L${x} ${y2} L${x + 10} ${y2 - 16}`} stroke="white" strokeWidth={3} fill="none" />
        </svg>
        <div style={{position: 'absolute', left: x + 18, top: (y1 + y2) / 2 - 24, ...heavy('white', 40),
          textAlign: 'left'}}>{t.text}</div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{opacity}}>
      <svg width={SHORT_W} height={SHORT_H} style={{position: 'absolute'}}>
        <line x1={x1 - 90} y1={y1} x2={x1 + 90} y2={y1} stroke="white" strokeWidth={3} strokeDasharray="10 8" />
        <line x1={x1 + 60} y1={y1} x2={x1 + 60} y2={y2} stroke={TONES.yellow} strokeWidth={4} />
        <path d={`M${x1 + 50} ${y2 - 14} L${x1 + 60} ${y2} L${x1 + 70} ${y2 - 14}`} stroke={TONES.yellow}
          strokeWidth={4} fill="none" />
      </svg>
      <div style={{position: 'absolute', left: x1 + 80, top: (y1 + y2) / 2 - 22, ...heavy(TONES.yellow, 40),
        textAlign: 'left'}}>{t.text}</div>
    </AbsoluteFill>
  );
};

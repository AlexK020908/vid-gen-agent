import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT} from './fonts';
import {Callout, Caption, Point, SAFE, SHORT_H, SHORT_W, Tag, TONES} from './types';

const OUTLINE = 'rgba(30, 16, 4, 0.9)';
const LABEL_SIZE = 32; // A's labels are about this big on a 1080-wide picture
const LEADER = 95; // how far out a label sits from its dot

const pop = (frame: number, from: number, fps: number): number =>
  spring({frame: frame - from, fps, config: {damping: 13, stiffness: 190}});

// in over `len` frames, out over `len`; shorter for something on screen less than twice that
const fade = (frame: number, from: number, to: number, len = 4): number => {
  const l = Math.max(0.5, Math.min(len, (to - from) / 2 - 0.01));
  return interpolate(frame, [from, from + l, to - l, to], [0, 1, 1, 0], {extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp'});
};

// Reference A's caption: the line in sentence case, white in a dark rounded box, just above the platform's caption
// Large bare words low in the picture, each line appearing with no fade, for fast cuts
export const CaptionBig: React.FC<{captions: Caption[]}> = ({captions}) => {
  const frame = useCurrentFrame();
  const cur = captions.find((c) => c.from <= frame && frame < c.to);
  if (!cur) return null;
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{position: 'absolute', top: SHORT_H * (cur.at ?? 0.72), width: SHORT_W * 0.8, textAlign: 'center', fontFamily: FONT,
        fontWeight: 800, fontSize: 68, lineHeight: 1.1, color: 'white', whiteSpace: 'pre-line', textWrap: 'balance',
        // a thin dark outline under the white, so it reads on a white plate as well as in a dark kitchen (the microwave short's
        // sixth cut, Nov 16, 2026: white on white, washed out)
        WebkitTextStroke: '8px rgba(0,0,0,0.85)', paintOrder: 'stroke fill',
        textShadow: '0 2px 3px rgba(0,0,0,0.9), 0 0 14px rgba(0,0,0,0.75), 0 4px 22px rgba(0,0,0,0.5)'}}>
        {cur.text}
      </div>
    </AbsoluteFill>
  );
};

export const CaptionBox: React.FC<{captions: Caption[]}> = ({captions}) => {
  const frame = useCurrentFrame();
  const cur = captions.find((c) => c.from <= frame && frame < c.to);
  if (!cur) return null;
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div
        style={{
          position: 'absolute',
          top: SHORT_H * 0.715,
          maxWidth: SHORT_W * 0.72,
          whiteSpace: 'pre-line', // a line break in the text is where the line breaks, as A breaks by phrase
          textWrap: 'balance', // otherwise the lines are evened out, so no word is left alone on the last one
          padding: '10px 22px',
          borderRadius: 12,
          backgroundColor: 'rgba(16, 16, 18, 0.72)',
          color: 'white',
          fontFamily: FONT,
          fontWeight: 600,
          fontSize: 42,
          lineHeight: 1.22,
          textAlign: 'center',
          opacity: fade(frame, cur.from, cur.to),
        }}
      >
        {cur.text}
      </div>
    </AbsoluteFill>
  );
};

const at = (track: Point[] | undefined, frame: number): Point | null => {
  if (!track || !track.length) return null;
  return track[Math.max(0, Math.min(track.length - 1, frame))];
};

const labelStyle = (color: string, size: number): React.CSSProperties => ({
  fontFamily: FONT,
  fontWeight: 800,
  fontSize: size,
  letterSpacing: 0.5,
  textTransform: 'uppercase',
  color,
  WebkitTextStroke: `2.5px ${OUTLINE}`,
  paintOrder: 'stroke fill',
  textShadow: '0 2px 8px rgba(0, 0, 0, 0.35)',
  whiteSpace: 'nowrap',
});

// A hide shorter than this (frames) is ridden through, so a part passing in front doesn't make the label blink;
// render/shot_checks.py counts hides the same way
export const BLINK = 18;

// Whether the label shows at track index i: its anchor is seen, or hidden only for a moment while in the picture
const showing = (track: Point[], i: number): boolean => {
  if (track[i][2]) return true;
  const [x, y] = track[i];
  if (x < 0 || x > 1 || y < 0 || y > 1) return false;
  let a = i;
  let b = i;
  while (a > 0 && !track[a - 1][2] && i - a < BLINK) a--;
  while (b < track.length - 1 && !track[b + 1][2] && b - i < BLINK) b++;
  return b - a + 1 < BLINK && a > 0 && b < track.length - 1;
};

// A part's label: a dot on the part, a thin line out to the side, the name at its end. It follows the part, and
// hides while something stands in front of the dot for longer than a moment.
export const CalloutLabel: React.FC<{c: Callout; track: Point[] | undefined; first?: number}> = ({c, track,
  first = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = at(track, frame - first);
  if (!p || !track || frame < c.from || frame >= c.to) return null;
  const [fx, fy] = p;
  const seen = showing(track, Math.max(0, Math.min(track.length - 1, frame - first)));
  const x = fx * SHORT_W;
  const y = fy * SHORT_H;
  const s = pop(frame, c.from, fps);
  const asked = c.size ?? LABEL_SIZE;
  const k = asked / LABEL_SIZE;       // the dot, line and leader grow with the letters
  const lo = SAFE.left * SHORT_W + 10;
  const hi = (1 - SAFE.right) * SHORT_W - 10;
  // Inter ExtraBold capitals run about 0.68 em wide; a label that wouldn't fit on its side goes on the other
  const wide = (letters: number): number => c.label.length * letters * 0.68 + 16;
  let dir = c.side === 'right' ? 1 : -1;
  const roomOn = (d: number): number => (d > 0 ? hi - (x + LEADER * k + 8) : x - LEADER * k - 8 - lo);
  // a label that wouldn't fit on its side goes on the other, if there's more room there
  if (!c.stay && wide(asked) > roomOn(dir) && roomOn(-dir) > roomOn(dir)) dir = -dir;
  // and if it fits on neither, its letters shrink until it fits on the side it's on, rather than running off the picture
  const room = roomOn(dir);
  const size = c.stay ? asked : Math.max(asked * 0.45, Math.min(asked, ((room - 16) / (c.label.length * 0.68))));
  const end = Math.max(lo + 40, Math.min(hi - 40, x + dir * LEADER * k * s));
  const ly = y - 34 * k * s;
  const color = TONES[c.tone];
  return (
    <AbsoluteFill style={{opacity: (seen ? 1 : 0) * fade(frame, c.from, c.to, 3)}}>
      <svg width={SHORT_W} height={SHORT_H} style={{position: 'absolute'}}>
        <line x1={x} y1={y} x2={end} y2={ly} stroke="rgba(255,255,255,0.92)" strokeWidth={3 * k} />
        <circle cx={x} cy={y} r={8 * k * s} fill={color} stroke={OUTLINE} strokeWidth={2.5 * k} />
      </svg>
      <div
        style={{
          position: 'absolute',
          top: ly - size * 0.65,
          ...(dir > 0 ? {left: end + 8} : {right: SHORT_W - end + 8}),
          transform: `scale(${s})`,
          transformOrigin: dir > 0 ? 'left center' : 'right center',
          ...labelStyle(color, size),
        }}
      >
        {c.label}
      </div>
    </AbsoluteFill>
  );
};

const Icon: React.FC<{icon: Tag['icon']; color: string; size?: number}> = ({icon, color, size = 38}) => {
  const common = {width: size, height: size, viewBox: '0 0 24 24', style: {marginRight: size * 0.21, flexShrink: 0}};
  const stroke = {stroke: color, strokeWidth: 3.2, strokeLinecap: 'round' as const, fill: 'none'};
  if (icon === 'clock') {
    return (
      <svg {...common}>
        <circle cx="12" cy="13.5" r="8" {...stroke} stroke={OUTLINE} strokeWidth={5.5} />
        <circle cx="12" cy="13.5" r="8" {...stroke} />
        <path d="M12 13.5 L12 9 M9.5 3 L14.5 3" {...stroke} />
      </svg>
    );
  }
  if (icon === 'check') {
    return (
      <svg {...common}>
        <path d="M4 12.5 L10 18 L20 6" {...stroke} stroke={OUTLINE} strokeWidth={6} />
        <path d="M4 12.5 L10 18 L20 6" {...stroke} />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M5 5 L19 19 M19 5 L5 19" {...stroke} stroke={OUTLINE} strokeWidth={6} />
      <path d="M5 5 L19 19 M19 5 L5 19" {...stroke} />
    </svg>
  );
};

const TAG_COLOR: Partial<Record<Tag['kind'], string>> = {fail: TONES.red, ok: TONES.green, warn: TONES.yellow};

// fail / ok / warn: a red ✗ (or a stopwatch), a green ✓, a yellow ⚠ before a short verdict. mode: "// SLOW MOTION"
// in the top left.
export const TagMark: React.FC<{t: Tag}> = ({t}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < t.from || frame >= t.to) return null;
  const s = pop(frame, t.from, fps);
  const opacity = fade(frame, t.from, t.to, 3);
  if (t.kind === 'mode') {
    return (
      <div style={{position: 'absolute', left: SHORT_W * 0.06, top: SHORT_H * (t.at?.[1] ?? 0.095), opacity,
        fontFamily: FONT, fontWeight: 600, fontSize: 32, letterSpacing: 1.5, color: 'white',
        textTransform: 'uppercase', textShadow: '0 1px 6px rgba(0,0,0,0.45)'}}>
        <span style={{color: TONES.yellow, fontWeight: 800, marginRight: 10}}>//</span>
        {t.text}
      </div>
    );
  }
  const color = TAG_COLOR[t.kind] ?? TONES.white;
  const [ax, ay] = t.at ?? [0.5, 0.3];
  return (
    <div
      style={{
        position: 'absolute',
        left: ax * SHORT_W,
        top: ay * SHORT_H,
        transform: `translate(-50%, -50%) scale(${s})`,
        display: 'flex',
        alignItems: 'center',
        opacity,
        ...labelStyle(color, t.size ?? 38),
        // a dark halo round the words and the icon, so a red verdict still reads over skin or a red glove (three reviewers
        // running called NO TOUCH, ONE TOUCH and NOTHING hard to read there, Nov 12, 2026). Over a dark picture it doesn't show.
        filter: 'drop-shadow(0 0 9px rgba(0,0,0,0.8)) drop-shadow(0 0 22px rgba(0,0,0,0.6))',
      }}
    >
      {t.kind === 'fail' || t.kind === 'ok' ? <Icon icon={t.icon ?? (t.kind === 'ok' ? 'check' : 'x')} color={color} size={t.size ?? 38} /> : null}
      {t.text}
    </div>
  );
};

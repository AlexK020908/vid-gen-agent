import {Audio, Video} from '@remotion/media';
import {AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFonts} from './fonts';
import {MachineShortProps, Screen} from './machine';
import {MachineTag} from './MachineTags';
import {CalloutLabel, CaptionBig, CaptionBox} from './Overlays';
import {SHORT_H, SHORT_W} from './types';

loadFonts();

const ramp = (frame: number, a: number, b: number, peak: number): number => {
  if (b <= a) return 0;
  const mid = (a + b) / 2;
  return interpolate(frame, [a, mid, b], [0, peak, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
};

// up in a frame, held, down in a frame; a flash only two or three frames long peaks at its middle instead
const hold = (frame: number, a: number, b: number, peak: number): number =>
  b - a < 3 ? ramp(frame, a, b, peak) : interpolate(frame, [a, a + 1, b - 1, b], [0, peak, peak, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

// A grey smoke cloud that rolls across and clears: a few big soft blobs, growing and drifting
const Smoke: React.FC<{a: number; b: number}> = ({a, b}) => {
  const frame = useCurrentFrame();
  if (frame < a || frame > b) return null;
  const t = (frame - a) / Math.max(1, b - a);
  const cover = t < 0.6 ? interpolate(t, [0, 0.6], [0, 1]) : interpolate(t, [0.6, 1], [1, 0]);
  const blobs = [[0.2, 0.7, 0.9], [0.65, 0.55, 1.0], [0.4, 0.3, 1.1], [0.8, 0.85, 0.8], [0.1, 0.25, 0.9]];
  return (
    <AbsoluteFill>
      {blobs.map(([x, y, s], i) => (
        <div key={i} style={{position: 'absolute', left: (x + t * 0.1) * SHORT_W, top: (y - t * 0.15) * SHORT_H,
          width: SHORT_W * s * (0.6 + t), height: SHORT_W * s * (0.6 + t), borderRadius: '50%',
          transform: 'translate(-50%,-50%)', background: 'radial-gradient(circle, rgba(92,92,96,0.97) 0%, ' +
          'rgba(80,80,84,0.85) 45%, rgba(70,70,74,0) 70%)', opacity: cover}} />
      ))}
      <AbsoluteFill style={{backgroundColor: 'rgb(84,84,88)', opacity: Math.max(0, cover * 1.4 - 0.4)}} />
    </AbsoluteFill>
  );
};

const ScreenFx: React.FC<{s: Screen}> = ({s}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const a = Math.round(s.from * fps);
  const b = Math.round(s.to * fps);
  if (s.kind === 'smoke') return <Smoke a={a} b={b} />;
  if (s.kind === 'darken') {
    if (frame < a) return null;
    return <AbsoluteFill style={{backgroundColor: '#05080f', opacity: s.amount ?? 0.65}} />;
  }
  if (s.kind === 'crossfade' || frame < a || frame > b) return null;
  const color = s.kind === 'black' || s.kind === 'dim' ? 'black' : s.kind === 'white' ? 'white' : s.color ?? '#ff4a1f';
  const held = s.kind === 'black' || s.kind === 'white';
  const opacity = held ? hold(frame, a, b, s.amount ?? 1) : ramp(frame, a, b, s.amount ?? 0.5);
  return <AbsoluteFill style={{backgroundColor: color, opacity, mixBlendMode: s.kind === 'tint' ? 'multiply' : 'normal'}} />;
};

// A whole machine short: the segments Blender rendered, crossfaded where they overlap, the screen effects, the
// labels on their tracks, the tags and captions, the narration and sound, and real footage at the end
export const MachineShort: React.FC<MachineShortProps> = ({segments, screens, captions, labels, tags, tracks,
  sounds, footage, captionStyle}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const f = (t: number): number => Math.round(t * fps);
  const fades = screens.filter((s) => s.kind === 'crossfade');
  const segOpacity = (i: number): number => {
    const seg = segments[i];
    let o = 1;
    for (const c of fades) {   // a segment fades in over a crossfade that starts inside it
      if (c.from >= seg.from - 1e-3 && c.from < seg.to && i > 0 && segments[i - 1].to > c.from) {
        o = Math.min(o, interpolate(frame, [f(c.from), f(c.to)], [0, 1], {extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp'}));
      }
    }
    return o;
  };
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      {segments.map((s, i) => (
        <Sequence key={`s${i}`} from={f(s.from)} durationInFrames={Math.max(1, f(s.to) - f(s.from))}>
          <AbsoluteFill style={{opacity: segOpacity(i)}}>
            <Video src={staticFile(s.clip)} muted />
          </AbsoluteFill>
        </Sequence>
      ))}
      {footage ? (
        <Sequence from={f(footage.from)} durationInFrames={Math.max(1, f(footage.to) - f(footage.from))}>
          <Video src={staticFile(footage.src)} muted trimBefore={f(footage.offset ?? 0)}
            style={{width: SHORT_W, height: SHORT_H, objectFit: 'cover'}} />
        </Sequence>
      ) : null}
      {screens.map((s, i) => <ScreenFx key={`x${i}`} s={s} />)}
      {labels.map((l, i) => {
        const track = tracks[l.anchor];
        return track ? <CalloutLabel key={`l${i}`} c={{...l, from: f(l.from), to: f(l.to)}} track={track.points}
          first={track.first} /> : null;
      })}
      {tags.map((t, i) => <MachineTag key={`t${i}`} t={t} tracks={tracks} />)}
      {captionStyle === 'big'
        ? <CaptionBig captions={captions.map((c) => ({...c, from: f(c.from), to: f(c.to)}))} />
        : <CaptionBox captions={captions.map((c) => ({...c, from: f(c.from), to: f(c.to)}))} />}
      {sounds.map((s, i) => (
        <Sequence key={`a${i}`} from={f(s.from)}>
          <Audio src={staticFile(s.src)} volume={s.volume ?? 1} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

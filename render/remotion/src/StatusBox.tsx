import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Status} from './types';

const SHOW_S = 6;
const ACCENT = '#FFD23F';
const DOWN = '#FF6B6B';
const UP = '#7CE38B';

// The day and the tracked amounts in the top left for the first seconds of a scene that starts a day or moves an
// amount: it slides in, holds, and fades, so the picture has the screen back for the rest of the line.
export const StatusBox: React.FC<{status: Status | null}> = ({status}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!status) return null;
  const end = SHOW_S * fps;
  const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
  const opacity = interpolate(frame, [0, 10, end - 15, end], [0, 1, 1, 0], clamp);
  if (opacity <= 0) return null;
  const x = interpolate(frame, [0, 12], [-36, 0], clamp);
  return (
    <AbsoluteFill style={{padding: 56}}>
      <div
        style={{
          alignSelf: 'flex-start',
          opacity,
          transform: `translateX(${x}px)`,
          fontFamily: "'Arial Black', 'Segoe UI', Arial, sans-serif",
          color: 'white',
          backgroundColor: 'rgba(0, 0, 0, 0.72)',
          borderRadius: 18,
          padding: '16px 28px 18px',
          minWidth: 300,
        }}
      >
        <div style={{fontSize: 58, fontWeight: 900, color: ACCENT, letterSpacing: 2, lineHeight: 1.1}}>
          {status.day.toUpperCase()}
        </div>
        {status.rows.map((row) => (
          <div key={row.item} style={{display: 'flex', alignItems: 'baseline', gap: 18, marginTop: 6}}>
            <span style={{flex: 1, fontSize: 30, fontWeight: 800, opacity: 0.8, textTransform: 'uppercase'}}>
              {row.item}
            </span>
            <span style={{fontSize: 40, fontWeight: 900}}>
              {row.amount} {row.unit}
            </span>
            {row.change ? (
              <span style={{fontSize: 30, fontWeight: 900, color: row.down ? DOWN : UP}}>{row.change}</span>
            ) : null}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

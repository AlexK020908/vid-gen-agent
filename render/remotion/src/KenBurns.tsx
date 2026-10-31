import {AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

const ZOOM = 1.08;
// Pan directions; scene idx picks one, so a re-render moves the same way.
const PANS: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1], [-1, 1]];

export const KenBurns: React.FC<{src: string; idx: number}> = ({src, idx}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, width, height} = useVideoConfig();
  const t = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const scale = 1 + (ZOOM - 1) * t;
  const [dx, dy] = PANS[idx % PANS.length];
  // Stay inside the zoomed overflow so no white edge ever shows.
  const x = dx * t * ((scale - 1) * width) / 2 * 0.9;
  const y = dy * t * ((scale - 1) * height) / 2 * 0.9;
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <Img
        src={src}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `translate(${x}px, ${y}px) scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

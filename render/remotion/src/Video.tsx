import {Audio, Video as Clip} from '@remotion/media';
import {AbsoluteFill, Sequence, staticFile} from 'remotion';
import {Captions} from './Captions';
import {KenBurns} from './KenBurns';
import {StatusBox} from './StatusBox';
import {FPS, Scene, toFrames, VideoProps} from './types';

// A clip plays once, then its last frame holds with a slow push, so the picture never jumps back to the start.
const ClipThenHold: React.FC<{scene: Scene; frames: number}> = ({scene, frames}) => {
  const clipFrames = Math.min(frames, Math.floor(((scene.clip_ms ?? 0) * FPS) / 1000));
  return (
    <>
      <Sequence durationInFrames={Math.max(1, clipFrames)} name="Clip">
        <Clip src={staticFile(scene.clip!)} muted objectFit="cover" style={{width: '100%', height: '100%'}} />
      </Sequence>
      {frames > clipFrames && scene.hold ? (
        <Sequence from={clipFrames} durationInFrames={frames - clipFrames} name="Hold">
          <KenBurns src={staticFile(scene.hold)} idx={scene.idx} />
        </Sequence>
      ) : null}
    </>
  );
};

const SceneView: React.FC<{scene: Scene; frames: number}> = ({scene, frames}) => (
  <AbsoluteFill style={{backgroundColor: 'white'}}>
    {scene.clip ? <ClipThenHold scene={scene} frames={frames} /> : <KenBurns src={staticFile(scene.still)} idx={scene.idx} />}
    <Audio src={staticFile(scene.audio)} />
    <StatusBox status={scene.status} />
    <Captions words={scene.words} />
  </AbsoluteFill>
);

export const Video: React.FC<VideoProps> = ({scenes}) => (
  <AbsoluteFill style={{backgroundColor: 'white'}}>
    {scenes.map((scene) => {
      // Round each scene's start on its own so frame rounding never adds up over 120 scenes.
      const from = toFrames(scene.start_ms);
      const frames = toFrames(scene.start_ms + scene.duration_ms) - from;
      return frames > 0 ? (
        <Sequence key={scene.idx} from={from} durationInFrames={frames} name={`Scene ${scene.idx}`}>
          <SceneView scene={scene} frames={frames} />
        </Sequence>
      ) : null;
    })}
  </AbsoluteFill>
);

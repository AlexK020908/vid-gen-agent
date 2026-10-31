import {CalculateMetadataFunction, Composition} from 'remotion';
import {FPS, toFrames, VideoProps} from './types';
import {Video} from './Video';

// The audio is the timeline: the video lasts exactly as long as the scenes' narration.
const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({props}) => {
  const last = props.scenes[props.scenes.length - 1];
  return {durationInFrames: last ? Math.max(1, toFrames(last.start_ms + last.duration_ms)) : 1};
};

export const Root: React.FC = () => (
  <Composition
    id="Video"
    component={Video}
    width={1920}
    height={1080}
    fps={FPS}
    durationInFrames={1}
    defaultProps={{scenes: []} satisfies VideoProps}
    calculateMetadata={calculateMetadata}
  />
);

import {CalculateMetadataFunction, Composition} from 'remotion';
import {ShortClip} from './shorts/ShortClip';
import {MachineShort} from './shorts/MachineShort';
import {MachineShortProps} from './shorts/machine';
import {SHORT_FPS, SHORT_H, SHORT_W, ShortClipProps} from './shorts/types';
import {FPS, toFrames, VideoProps} from './types';
import {Video} from './Video';

// The audio is the timeline: the video lasts exactly as long as the scenes' narration.
const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({props}) => {
  const last = props.scenes[props.scenes.length - 1];
  return {durationInFrames: last ? Math.max(1, toFrames(last.start_ms + last.duration_ms)) : 1};
};

// A machine shot lasts as long as Blender rendered it.
const shortMetadata: CalculateMetadataFunction<ShortClipProps> = ({props}) => ({
  durationInFrames: Math.max(1, props.frames),
});

// A whole machine short lasts its `duration` seconds.
const machineMetadata: CalculateMetadataFunction<MachineShortProps> = ({props}) => ({
  durationInFrames: Math.max(1, Math.round(props.duration * SHORT_FPS)),
});

const emptyMachine: MachineShortProps = {duration: 1, segments: [], screens: [], captions: [], labels: [], tags: [],
  tracks: {}, sounds: [], footage: null};

const emptyShort: ShortClipProps = {clip: '', frames: 1, captions: [], captionStyle: 'box', callouts: [], tags: [],
  anchors: {}};

export const Root: React.FC = () => (
  <>
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
    <Composition
      id="ShortClip"
      component={ShortClip}
      width={SHORT_W}
      height={SHORT_H}
      fps={SHORT_FPS}
      durationInFrames={1}
      defaultProps={emptyShort}
      calculateMetadata={shortMetadata}
    />
    <Composition
      id="MachineShort"
      component={MachineShort}
      width={SHORT_W}
      height={SHORT_H}
      fps={SHORT_FPS}
      durationInFrames={1}
      defaultProps={emptyMachine}
      calculateMetadata={machineMetadata}
    />
  </>
);

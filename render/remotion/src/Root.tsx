import {CalculateMetadataFunction, Composition} from 'remotion';
import {ShortClip} from './shorts/ShortClip';
import {MachineShort} from './shorts/MachineShort';
import {MachineShortProps} from './shorts/machine';
import {DiagramShort} from './shorts/DiagramShort';
import {DiagramShortProps} from './shorts/diagram';
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

// A systems short lasts its timeline's `duration` seconds (diagram/sim.py)
const diagramMetadata: CalculateMetadataFunction<DiagramShortProps> = ({props}) => ({
  durationInFrames: Math.max(1, Math.round(props.duration * SHORT_FPS)),
});

const emptyDiagram = {duration: 1, beat: 120, title: '', subtitles: [], captions: [], stats: [], nodes: [], edges: [],
  dots: [], flashes: [], badges: [], code: null, end: null, loop: {from: 1, to: 1}, audio: null,
  geometry: {icon: 96, ring: 79, label: 30, counter: 44, trim: 60, queue_dot: 6, queue_step: 14, queue_dots: 4, queue_more: 30, badge: 26, badge_pad: 14, badge_h: 43, left: 43,
    right: 929, head_left: 43, head_right: 1037, code_size: 33, code_line: 50, code_pad: 22, code_bottom: 1478,
    end_big: 92, end_claim: 46, end_note: 28, pill_h: 64, pill_text: 22, pill_value: 36, pill_pad: 26, pill_gap: 18,
    move: 0.5, blink: 0.35, hold: 0.0667, gap: 0.0333, dip: 0.15, title_size: 60, title_top: 172, subtitle_top: 255, pills_top: 314,
    box: [43, 418, 929, 1013], caption_top: 1037, caption_h: 119, code_top: null, code_lines: 0}} satisfies DiagramShortProps;

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
    <Composition
      id="DiagramShort"
      component={DiagramShort}
      width={SHORT_W}
      height={SHORT_H}
      fps={SHORT_FPS}
      durationInFrames={1}
      defaultProps={emptyDiagram}
      calculateMetadata={diagramMetadata}
    />
  </>
);

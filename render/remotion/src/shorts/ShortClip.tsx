import {Video} from '@remotion/media';
import {AbsoluteFill, staticFile} from 'remotion';
import {loadFonts} from './fonts';
import {CalloutLabel, CaptionBig, CaptionBox, TagMark} from './Overlays';
import {ShortClipProps} from './types';

loadFonts();

// One machine shot: the clip Blender rendered, with its caption, the parts' labels on their tracks, and its tags.
export const ShortClip: React.FC<ShortClipProps> = ({clip, captions, captionStyle, callouts, tags, anchors}) => (
  <AbsoluteFill style={{backgroundColor: 'black'}}>
    <Video src={staticFile(clip)} muted />
    {callouts.map((c, i) => (
      <CalloutLabel key={`c${i}`} c={c} track={anchors[c.anchor]} />
    ))}
    {tags.map((t, i) => (
      <TagMark key={`t${i}`} t={t} />
    ))}
    {captionStyle === 'big' ? <CaptionBig captions={captions} /> : <CaptionBox captions={captions} />}
  </AbsoluteFill>
);

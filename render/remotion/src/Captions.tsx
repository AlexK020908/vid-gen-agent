import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Word} from './types';

const MAX_WORDS = 3;
const ACCENT = '#FFD23F';

// 2-4 words at a time: break after MAX_WORDS, or at punctuation once a chunk has 2.
const chunk = (words: Word[]): Word[][] => {
  const out: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    cur.push(w);
    if (cur.length >= MAX_WORDS || (cur.length >= 2 && /[.,!?;:]$/.test(w.word))) {
      out.push(cur);
      cur = [];
    }
  }
  if (cur.length) {
    const prev = out[out.length - 1];
    if (cur.length === 1 && prev && prev.length < 4) prev.push(cur[0]);
    else out.push(cur);
  }
  return out;
};

export const Captions: React.FC<{words: Word[]}> = ({words}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!words.length) return null;
  const ms = (frame / fps) * 1000;
  const chunks = chunk(words);
  const current = chunks.findLast((c) => c[0].start_ms <= ms) ?? chunks[0];
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 80}}>
      <div
        style={{
          fontFamily: "'Arial Black', 'Segoe UI', Arial, sans-serif",
          fontWeight: 900,
          fontSize: 64,
          lineHeight: 1.15,
          color: 'white',
          backgroundColor: 'rgba(0, 0, 0, 0.78)',
          borderRadius: 18,
          padding: '14px 30px',
          maxWidth: 1500,
          textAlign: 'center',
        }}
      >
        {current.map((w, i) => (
          <span key={i} style={{color: w.start_ms <= ms && ms < w.end_ms ? ACCENT : 'white'}}>
            {i ? ' ' : ''}
            {w.word}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

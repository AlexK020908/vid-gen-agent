// Mirrors the props render/remotion_render.py render_short() writes for one shot. Frames count from 0, the shot's
// first frame (Blender's frame 1).

// x, y as fractions of the picture (from the left, from the top), and whether nothing hides it
export type Point = [number, number, boolean];

export type Tone = 'yellow' | 'white' | 'blue' | 'red' | 'green';

// a "\n" in the text breaks the line there
export type Caption = {text: string; from: number; to: number};

// A part's label: a dot on the anchor, a leader line, the label beside it on `side`
// `stay` keeps a label on its side past the safe area, where the other side would put it on something it can't be
// read against
export type Callout = {label: string; anchor: string; tone: Tone; from: number; to: number; side: 'left' | 'right';
  stay?: boolean};

export type TagKind = 'fail' | 'ok' | 'warn' | 'question' | 'multiplier' | 'section' | 'mode' | 'stat';

// `at` places it (fractions of the picture); without it each kind has its own place
export type Tag = {kind: TagKind; text: string; icon?: 'x' | 'clock' | 'check' | 'warn'; from: number; to: number;
  at?: [number, number]};

export type ShortClipProps = {
  clip: string;
  frames: number;
  captions: Caption[];
  captionStyle: 'box' | 'big'; // box is reference A's; big is the character shorts', large and bare in mid-picture
  callouts: Callout[];
  tags: Tag[];
  anchors: Record<string, Point[]>;
};

export const SHORT_FPS = 30;
export const SHORT_W = 1080;
export const SHORT_H = 1920;

// What Shorts' and Reels' own buttons and caption cover: keep text out of these edges (fractions of the picture)
export const SAFE = {top: 0.08, right: 0.14, bottom: 0.22, left: 0.04};

export const TONES: Record<Tone, string> = {
  yellow: '#F7B733',
  white: '#FFFFFF',
  blue: '#8FD3FF',
  red: '#FF4B3E',
  green: '#5BE37D',
};

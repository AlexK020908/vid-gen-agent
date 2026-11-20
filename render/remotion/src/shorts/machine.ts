// Mirrors the props a whole machine short renders from (render/short.py). Times are seconds of the short; tracks
// are an anchor's screen positions frame by frame from `first`.

import {Caption, Point, Tone} from './types';

export type Segment = {clip: string; from: number; to: number};

// crossfade: from the segment that ends to the one that starts, over from..to (the clips overlap there)
// black, white, tint: the frame covered by a colour, rising to `amount` and falling back over from..to
// smoke: a grey smoke wipe; darken: the frame dimmed to `amount` from `from` to the end
export type Screen = {kind: 'crossfade' | 'black' | 'white' | 'tint' | 'smoke' | 'darken' | 'dim'; from: number;
  to: number; color?: string; amount?: number};

export type Track = {first: number; points: Point[]};

export type Label = {label: string; anchor: string; tone: Tone; from: number; to: number; side: 'left' | 'right';
  stay?: boolean; size?: number};

export type MTag = {
  kind: 'fail' | 'ok' | 'warn' | 'question' | 'multiplier' | 'section' | 'mode' | 'stat' | 'title' | 'dimension' | 'deeper' |
    'footage' | 'credit' | 'count' | 'stamp';
  text: string;
  from: number;
  to: number;
  at?: [number, number];        // place, as fractions of the picture
  icon?: 'x' | 'clock' | 'warn' | 'up' | 'down' | 'updown' | 'thermo' | 'arrows';
  tone?: Tone;
  sub?: string;                 // a smaller second line
  subSize?: number;             // stamp: the second line's letters' height, when it must read as well as the captions
  steps?: [number, number][];   // a multiplier's values: [second, value]
  start?: number;               // a count's first value...
  end?: number;                 // ...and its last, reached a little before it goes
  step?: number;                // a count's tick as it runs (1 for years); left out, about three figures
  grouping?: boolean;           // a count: false drops the commas, for a year
  box?: boolean;                // a count: in a dark box with a colored rim, like a stamp's, so it reads on a bright picture
  hold?: number;                // a count: seconds it stands on its first value before it runs
  run?: number;                 // a count: seconds the run takes; left out, seven tenths of the time it's up
  anchor?: string;              // dimension and deeper: from this anchor's point...
  anchor2?: string;             // ...to this one's
  size?: number;                // fail, warn and stamp: their letters' height; count: its number's height
};

export type Sound = {src: string; from: number; volume?: number};

export type Footage = {src: string; from: number; to: number; darken_from?: number; offset?: number};

export type MachineShortProps = {
  duration: number;
  segments: Segment[];
  screens: Screen[];
  captions: Caption[];
  labels: Label[];
  tags: MTag[];
  tracks: Record<string, Track>;
  sounds: Sound[];
  footage?: Footage | null;
  captionStyle?: 'box' | 'big'; // box is reference A's; big is the character shorts', large and bare in mid-picture
};

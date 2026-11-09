// Mirrors the timeline diagram/sim.py works out for a systems short. Times are seconds of the short; positions are px
// of the 1080x1920 frame. Remotion only draws this: every number in it comes from the simulation.

export type DKey = [number, number, number, number]; // time, x, y, opacity: a node eases from one key to the next

export type DNode = {
  id: string;
  icon: string;
  label: string;
  tone: string;
  counter: boolean;
  ring: boolean;
  keys: DKey[];
  states: [number, string][];
  counts: [number, number][];
  queue: [number, number][];
};

export type DEdge = {a: string; b: string; keys: [number, number][]; dashed: [number, boolean][]};

// from, to, leaves, arrives, kind (a request going out, or its answer coming back), and 1 for the request being followed
export type DDot = [string, string, number, number, string, number];

// a node, when, what: a request lost there
export type DFlash = [string, number, string];

// a node, from, to, text, tone, and where: HIT, MISS, LOST, or a time, under the node's label or beside its icon
export type DBadge = [string, number, number, string, string, string];

export type DCaption = {text: string; lines: string[]; size: number; tone: string; from: number; to: number};

export type DSubtitle = {text: string; from: number; to: number; size: number};

export type DStat = {name: string; unit: string; steps: [number, number | null, string][]; spans: [number, number][]};

// each line is [text, kind] tokens; dims are [line, from]; hl are [line, from, to, kind], lines counted from 1: a
// request running the line, a blink (kind "run", or "lost" where the request was lost there)
export type DCodeBlock = {from: number; to: number; lines: [string, string][][]; dims: [number, number][];
  hl: [number, number, number, string][]};

export type DEnd = {from: number; to: number; before: {text: string; tone: string}; after: {text: string; tone: string};
  claim: string; claim_lines: string[]; note: string};

export type DGeometry = {
  icon: number; ring: number; label: number; counter: number; trim: number; queue_dot: number; queue_step: number;
  queue_dots: number; queue_more: number; badge: number; badge_pad: number; badge_h: number; left: number; right: number; head_left: number; head_right: number; code_size: number;
  code_line: number; code_pad: number; code_bottom: number; end_big: number; end_claim: number; end_note: number;
  pill_h: number; pill_text: number; pill_value: number; pill_pad: number; pill_gap: number; move: number;
  blink: number; hold: number; gap: number; dip: number; title_size: number; title_top: number; subtitle_top: number; pills_top: number;
  box: [number, number, number, number]; caption_top: number; caption_h: number; code_top: number | null;
  code_lines: number;
};

export type DiagramShortProps = {
  duration: number;
  beat: number;
  geometry: DGeometry;
  title: string;
  subtitles: DSubtitle[];
  captions: DCaption[];
  stats: DStat[];
  nodes: DNode[];
  edges: DEdge[];
  dots: DDot[];
  flashes: DFlash[];
  badges: DBadge[];
  code: {blocks: DCodeBlock[]} | null;
  end: DEnd | null;
  loop: {from: number; to: number};
  audio?: string | null;
};

// The dark look: near-black, line icons in their tone, muted code
export const D = {
  bg: '#030405',
  edge: '#272c34',
  edgeDead: '#3b4048',
  dot: '#4a82f0',
  back: '#2fb866',
  grey: '#5f646c',
  pillName: '#7b818a',
  pillBg: '#0b0d10',
  panel: '#090b0f',
  panelBorder: '#1b1f26',
  band: 'rgba(64, 96, 166, 0.24)',
  bar: '#4a6fc0',
  flash: 'rgba(120, 160, 240, 0.30)',   // over the band as a line runs
  flashBar: '#9dbcff',
  lostBand: 'rgba(214, 72, 72, 0.30)',  // a line run by a request that was lost there
  lostBar: '#ff6b6b',
};

export const NODE_TONES: Record<string, string> = {
  green: '#3db58f',
  blue: '#6098f0',
  orange: '#f09820',
  purple: '#a78bfa',
  teal: '#2fc4b2',
  red: '#f05848',
  grey: '#8b9099',
  yellow: '#f2c94c',
};

export const TEXT_TONES: Record<string, string> = {
  white: '#f2f4f7',
  orange: '#f09820',
  blue: '#6098f0',
  green: '#25b15f',
  red: '#f05848',
  grey: '#6b7078',
};

export const CODE_TONES: Record<string, string> = {
  keyword: '#b392c9',
  name: '#a9c49a',
  func: '#e5c07b',
  string: '#a9c49a',
  number: '#d7a26b',
  comment: '#5c636e',
  punct: '#8c939d',
  text: '#b9c0c9',
};

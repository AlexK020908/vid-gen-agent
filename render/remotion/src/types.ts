// Mirrors the props.json that render/remotion_render.py writes. Paths are relative to --public-dir.

export type Word = {word: string; start_ms: number; end_ms: number};

export type Scene = {
  idx: number;
  still: string;
  audio: string;
  clip: string | null;
  clip_ms: number | null; // the clip's length; it plays once
  hold: string | null; // the clip's last frame, held for the rest of the scene
  start_ms: number;
  duration_ms: number;
  words: Word[];
  status: Status | null; // the corner box: the day and the tracked amounts, when this scene changes them
};

// `change` is "▼ 3" or "▲ 5" on an amount this scene moved; `down` colors it.
export type StatusRow = {item: string; amount: string; unit: string; change: string | null; down: boolean};

export type Status = {day: string; rows: StatusRow[]};

export type VideoProps = {scenes: Scene[]};

export const FPS = 30;

export const toFrames = (ms: number): number => Math.round((ms * FPS) / 1000);

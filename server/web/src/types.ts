// Shapes the server sends. Card payloads mirror the builders in core/cards.py.

export type VideoState =
  | 'new' | 'outlined' | 'outline_approved' | 'scripted' | 'generating' | 'assembled'
  | 'render_approved' | 'publishing' | 'scheduled' | 'live' | 'failed' | 'blocked'

export type CardStatus =
  | 'active' | 'approved' | 'revised' | 'regenerated' | 'flagged' | 'superseded' | 'retried' | 'done' | 'denied'
  | 'kept'

export interface Channel {
  id: string
  name: string
  budget_usd: number
  gates: string[]
  home_thread_id: number
  youtube: YouTubeStatus
}

/** A channel's YouTube sign-in, as /api/channels reports it (the token itself never leaves the keychain). */
export interface YouTubeStatus {
  mode: string
  /** secrets/client_secret.json exists */
  client_secret: boolean
  connected: boolean
  title: string | null
  channel_id: string | null
  error: string | null
  /** Scopes added since this channel was connected; Connect again to grant them. */
  missing_scopes: string[]
  /** The daily sign-in check's complaint, if the last one failed. */
  signin_error: string | null
}

export interface Thread {
  id: number
  channel_id: string
  video_id: number | null
  title: string
  created_at: number
  state: VideoState | null
  cost_usd: number | null
  error: string | null
  waiting: number
  last_message_id: number | null
  /** The chat agent is working on a turn in this thread. */
  running: boolean
}

export interface AgentInfo {
  online: boolean
  model: string | null
  budget_usd_per_session: number
}

export interface Message {
  id: number
  thread_id: number
  video_id: number | null
  role: 'system' | 'card' | 'progress' | 'user' | 'assistant' | 'tool'
  text: string | null
  card: Card | null
  card_status: CardStatus | null
  created_at: number
}

export interface Beat {
  n: number
  label: string
  title: string
  summary: string
  skill: string
  hero: boolean
  /** Cast members in this beat; the last beat that lists someone ends their thread. */
  cast?: string[]
}

export interface CastMember {
  name: string
  look: string
  role: string
  thread: string
}

/** Something the viewer counts with the character; `start` is formatted for display. */
export interface TrackerItem {
  item: string
  unit: string
  start: string
}

export interface OutlineCard {
  kind: 'outline'
  /** A note taken back by Stop, to change and send again. */
  draft_note?: string | null
  video_id: number
  version: number
  topic: string
  hook: string
  /** Older outlines have no backstory, cast or tracker. */
  backstory?: string
  cast?: CastMember[]
  tracker?: TrackerItem[]
  ending: string
  beats: Beat[]
}

export interface ScriptScene {
  idx: number
  narration: string
  visual_prompt: string
  motion: string
  /** The place's name; null for scripts from before places. */
  place?: string | null
  cast?: string[]
  /** The tracked amounts this scene shows, like "Water 9 L · Food 12 days". */
  tracker?: string | null
  /** How this scene changes its place for good. */
  set_change?: string | null
}

export interface ScriptCard {
  kind: 'script'
  /** A note taken back by Stop, to change and send again. */
  draft_note?: string | null
  video_id: number
  version: number
  topic: string
  beats: { n: number; label: string; title: string; scenes: ScriptScene[] }[]
  /** Each is drawn once as the reference picture for every scene there. */
  places?: { name: string; look: string }[]
  scene_count: number
  word_count: number
  est_minutes: number
}

export interface RenderScene {
  idx: number
  beat: number
  label: string
  motion: string
  regen_count: number
  narration: string
  visual_prompt: string
  start_ms: number | null
  still_url: string | null
  preview_url: string | null
}

export interface RenderCard {
  kind: 'render'
  video_id: number
  topic: string
  titles: string[]
  thumbs: string[]
  picked: { title: string | null; thumb_idx: number | null }
  video_url: string | null
  highlight_url: string | null
  duration_ms: number | null
  cost_usd: number
  budget_usd: number
  scenes: RenderScene[]
}

export interface Chapter {
  t_ms: number
  title: string
}

export interface PublishCard {
  kind: 'publish'
  video_id: number
  youtube_mode: string
  /** Live mode only: whether the channel has a YouTube sign-in. */
  youtube_connected: boolean | null
  title: string
  description: string
  tags: string[]
  publish_at: number
  privacy: string
  ai_disclosure: boolean
  made_for_kids: boolean
  category_id: string
  playlist_id: string | null
  thumbnail: string | null
  captions: string | null
  chapters: Chapter[]
}

export interface ErrorCard {
  kind: 'error'
  video_id: number
  state: VideoState
  error: string | null
  resume_state: string | null
}

export interface ProgressCard {
  kind: 'progress'
  video_id: number
  stage: string
  done: number
  total: number
  /** '%' when done is a percentage (Remotion render, upload); 'scenes' while the script is written (total is a ceiling). */
  unit: string | null
  cost_usd: number | null
}

export interface TopicIdea {
  id: number
  title: string
  why: string | null
  status: 'queued' | 'used' | 'dismissed'
  /** Its kind of setting, so the channel's own results can be compared by family. */
  family: string | null
  /** Why it ranks where it does (a held family, or one that has done well or poorly here). */
  note: string | null
  /** The video started from it. */
  video_id: number | null
  /** The competitor hits it builds on; url is null for made-up ones. */
  based_on: { title: string; channel: string; per_day: number; url: string | null }[]
}

/** Topic ideas from competitors' recent hits, in a channel's home thread. */
export interface TopicsCard {
  kind: 'topics'
  channel_id: string
  /** Built on made-up competitor videos (topics.competitors: stub). */
  simulated: boolean
  /** Follow-ups to this channel's own 48-hour winner (the surge), or null for competitor ideas. */
  winner_video_id: number | null
  topics: TopicIdea[]
}

/** A live video's other thumbnails and titles from its render card; Apply changes them on YouTube. */
export interface SwapCard {
  kind: 'swap'
  video_id: number
  reason: string | null
  /** false: youtube.mode is stub (or the video was uploaded in stub mode), so Apply only writes the request. */
  live: boolean
  title: string
  thumb_idx: number
  titles: string[]
  thumbs: string[]
  texts: string[]
}

/** How a video is doing 48 hours or 7 days after going public. Information only: it posts as done. */
export interface MetricsCard {
  kind: 'metrics'
  video_id: number
  after_h: number
  views: number | null
  avd_seconds: number | null
  avd_pct: number | null
  subs_gained: number | null
  /** null until YouTube's daily reach files cover the whole window. */
  impressions: number | null
  ctr: number | null
  simulated: boolean
  captured_at: number
  /** Hours late it was read (the app was off), or 0. */
  late_h: number
  /** Against the channel's medians, once the reading is complete; 'early' until there are min_videos to compare. */
  verdict: 'winner' | 'loser' | 'mixed' | 'early' | null
  min_videos: number
  medians: { avd_pct: number; ctr: number; n: number } | null
  /** The last thumbnail/title swap before this reading, and click-through since (null until its days are in). */
  swap: { applied_at: number; title: string | null; thumb: number | null; ctr_before: number | null;
    ctr_since: number | null } | null
}

/** The agent wants to Edit a file; nothing changes until the person approves. */
export interface ConfirmCard {
  kind: 'confirm'
  tool: string
  title: string
  path: string
  diff: string
  input: Record<string, unknown>
}

/** A muted line in the chat for each tool the agent calls (role 'tool'). */
export interface ToolCard {
  kind: 'tool'
  name: string
  detail: string
  error: string | null
}

export type Card =
  | OutlineCard | ScriptCard | RenderCard | PublishCard | ErrorCard | ProgressCard | ConfirmCard | ToolCard
  | TopicsCard | MetricsCard | SwapCard

export interface VideoInfo {
  video_id: number
  state: VideoState
  cost_usd: number
  budget_usd: number
  error: string | null
  scene_list: {
    idx: number
    label: string
    state: string
    regen_count: number
    narration: string
    visual_prompt: string
    preview_url: string | null
  }[]
}

export type LiveEvent =
  | { type: 'message' | 'message_updated'; message: Message }
  | { type: 'thread'; thread: Thread }
  | { type: 'turn'; thread_id: number; running: boolean }

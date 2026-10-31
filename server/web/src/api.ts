import type { AgentInfo, Channel, Message, Thread, VideoInfo } from './types'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      // not JSON; keep the status line
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  channels: () => request<Channel[]>('GET', '/api/channels'),
  threads: () => request<Thread[]>('GET', '/api/threads'),
  messages: (threadId: number) => request<Message[]>('GET', `/api/threads/${threadId}/messages`),
  video: (videoId: number) => request<VideoInfo>('GET', `/api/videos/${videoId}`),
  newVideo: (channelId: string, idea: string) =>
    request<{ video_id: number; thread_id: number }>('POST', '/api/videos', { channel_id: channelId, idea }),
  agent: () => request<AgentInfo>('GET', '/api/agent'),
  /** Opens Google's consent screen on this machine; resolves once you've signed in (or it times out). */
  connect: (channelId: string) =>
    request<{ youtube_channel_id: string; title: string }>('POST', `/api/channels/${channelId}/connect`),
  chat: (threadId: number, text: string) => request<Message>('POST', `/api/threads/${threadId}/chat`, { text }),
  stop: (threadId: number) => request<{ ok: boolean }>('POST', `/api/threads/${threadId}/stop`),
  /** Approve or deny a confirm card (an Edit the agent wants to make). */
  confirm: (messageId: number, allow: boolean) =>
    request<{ ok: boolean }>('POST', `/api/confirm/${messageId}`, { allow }),
  /** A topic card's Start: creates the video and its thread. */
  startTopic: (topicId: number) =>
    request<{ video_id: number; thread_id: number }>('POST', `/api/topics/${topicId}/start`),
  dismissTopic: (topicId: number) => request<{ ok: boolean }>('POST', `/api/topics/${topicId}/dismiss`),
  /** A card button: approve, revise, edit_outline, flag, edit_scene, pick, publish_fields, publish, retry. */
  act: (videoId: number, verb: string, body: object = {}) =>
    request<{ ok: boolean }>('POST', `/api/videos/${videoId}/${verb}`, body),
}

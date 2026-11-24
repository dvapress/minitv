import type { Locale } from "./i18n";

export type SeriesCard = {
  id: number;
  slug: string;
  title: string;
  title_en: string;
  synopsis: string;
  synopsis_en: string;
  genre: string;
  genre_en: string;
  region: string;
  cover_url: string | null;
  episode_count: number;
  free_count: number;
  play_count: number;
  long_episode_count: number;
  reason: string | null;
};

export type Episode = {
  id: number;
  number: number;
  title: string;
  duration_seconds: number | null;
  duration_flag: "ok" | "long" | "unknown";
  width: number;
  height: number;
  access: "free" | "member" | "locked" | "unavailable";
  browser_playable: boolean;
  playback_block?: string;
  has_subtitle: boolean;
  rendition_count: number;
  play_count: number;
  position_seconds: number;
};

export type User = {
  id: number;
  email: string;
  display_name: string;
  role: string;
  region: string;
  theme: string;
  locale: string;
  member: boolean;
  membership_until: string | null;
};

export type AppConfig = {
  regions: string[];
  free_episodes: number;
  max_episode_seconds: number;
  payments: string;
  selection: { include: string[]; episode_from: number; episode_to: number };
};

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export function viewerKey(): string {
  const existing = localStorage.getItem("leapdrama.viewer");
  if (existing && /^[A-Za-z0-9_-]{8,64}$/.test(existing)) return existing;
  const created = crypto.randomUUID().replace(/-/g, "");
  localStorage.setItem("leapdrama.viewer", created);
  return created;
}

export async function api<T>(path: string, locale: Locale, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept-Language", locale);
  headers.set("X-Viewer", viewerKey());
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  const text = await response.text();
  const data = text ? JSON.parse(text) as { detail?: { code?: string; message?: string } } : null;
  if (!response.ok) {
    const code = data?.detail?.code || "error";
    if (code === "gate_required" && !path.startsWith("/api/gate/")) {
      const next = window.location.pathname + window.location.search;
      window.location.assign(`/gate?next=${encodeURIComponent(next.startsWith("/") ? next : "/")}`);
    }
    throw new ApiError(data?.detail?.message || response.statusText, code, response.status);
  }
  return data as T;
}

export function titleOf(locale: Locale, item: { title: string; title_en: string }): string {
  return locale === "en" && item.title_en ? item.title_en : item.title;
}

export function genreOf(locale: Locale, item: { genre: string; genre_en: string }): string {
  return locale === "en" && item.genre_en ? item.genre_en : item.genre;
}

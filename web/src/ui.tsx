import { useEffect, useState } from "react";
import { usePrefs } from "./prefs";

export function formatPlays(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

export function formatDuration(seconds: number) {
  if (!seconds || seconds < 0) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function PosterImage({ src, alt }: { src: string; alt: string }) {
  const { locale } = usePrefs();
  const [failed, setFailed] = useState(false);
  const resolved = src ? src.replace(/^(\/covers\/\d+)\.jpg$/i, `$1.${locale}.jpg`) : "";

  useEffect(() => {
    setFailed(false);
  }, [resolved]);

  if (!resolved || failed) {
    return (
      <span className="poster-fallback" aria-hidden="true">
        <span className="ld-brand-mark">L</span>
      </span>
    );
  }
  return <img src={resolved} alt={alt} loading="lazy" onError={() => setFailed(true)} />;
}

export function PlayGlyph({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M8 5.5v13l11-6.5z" />
    </svg>
  );
}

export function LockGlyph({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="4.5" y="10.5" width="15" height="9.5" rx="2.5" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
      <path d="M12 14.5v2" />
    </svg>
  );
}

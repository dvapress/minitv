import { FormEvent, SyntheticEvent, useEffect, useRef, useState } from "react";
import { api, genreOf, titleOf, type Episode, type SeriesCard } from "./api";
import { useApp } from "./context";

function Poster({ title, url }: { title: string; url: string | null }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) return <span className="monogram" aria-hidden="true">{title.slice(0, 1)}</span>;
  return <img src={url} alt="" onError={() => setFailed(true)} />;
}

function Card({ item }: { item: SeriesCard }) {
  const { locale, t, go } = useApp();
  return (
    <a className="card" href={`/watch/${encodeURIComponent(item.slug)}`} onClick={(event) => { event.preventDefault(); go(`/watch/${encodeURIComponent(item.slug)}`); }}>
      <div className="poster"><Poster title={titleOf(locale, item)} url={item.cover_url} /></div>
      <p>{titleOf(locale, item)}</p>
      <small>
        {genreOf(locale, item)} · {t("hero.episodes", { count: item.episode_count })}
        {item.play_count > 0 ? ` · ${t("card.plays", { count: item.play_count })}` : ""}
      </small>
      {item.long_episode_count > 0 ? <small className="warn"> {t("home.long")}</small> : null}
    </a>
  );
}

export function HomePage() {
  const { t, locale, region, go } = useApp();
  const [heroIndex, setHeroIndex] = useState(0);
  const [data, setData] = useState<{ catalog_empty: boolean; visible_count: number; hero: SeriesCard[]; genres: { genre: string; genre_en: string; series: SeriesCard[] }[]; popular: SeriesCard[] } | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let alive = true;
    setError(false);
    api<NonNullable<typeof data>>(`/api/home?region=${encodeURIComponent(region)}`, locale)
      .then((payload) => { if (alive) { setData(payload); setHeroIndex(0); } })
      .catch(() => { if (alive) setError(true); });
    return () => { alive = false; };
  }, [locale, region]);
  useEffect(() => {
    if (!data || data.hero.length < 2) return;
    const timer = window.setInterval(() => setHeroIndex((index) => (index + 1) % data.hero.length), 6500);
    return () => window.clearInterval(timer);
  }, [data]);
  if (error) return <p>{t("common.error")} <button className="text-btn" onClick={() => setError(false)}>{t("common.retry")}</button></p>;
  if (!data) return <p>{t("common.loading")}</p>;
  if (data.catalog_empty) {
    return (
      <section className="empty">
        <h1>{t("empty.title")}</h1>
        <p>{t("empty.body")}</p>
        <code>{t("empty.command")}</code>
      </section>
    );
  }
  if (data.visible_count === 0) return <section className="empty"><h1>{t("filter.empty")}</h1></section>;
  const hero = data.hero[heroIndex] || data.hero[0];
  const unclassified = data.genres.length === 1 && data.genres[0].genre === "未分类";
  return (
    <>
      {hero ? (
        <section className="hero">
          <div className="hero-copy">
            <div className="kicker">{genreOf(locale, hero)}</div>
            <h1>{titleOf(locale, hero)}</h1>
            <div className="meta">
              <span className="chip">{t("hero.episodes", { count: hero.episode_count })}</span>
              <span className="chip">{t("hero.free", { count: hero.free_count })}</span>
              {hero.long_episode_count > 0 ? <span className="chip warn">{t("home.long")}</span> : null}
            </div>
            <p><a className="solid" href={`/watch/${encodeURIComponent(hero.slug)}`} onClick={(event) => { event.preventDefault(); go(`/watch/${encodeURIComponent(hero.slug)}`); }}>{t("hero.play")}</a></p>
            <div className="dots">
              {data.hero.map((item, index) => (
                <button key={item.id} className={index === heroIndex ? "on" : ""} aria-label={titleOf(locale, item)} onClick={() => setHeroIndex(index)} />
              ))}
            </div>
          </div>
          <div className="hero-poster poster"><Poster title={titleOf(locale, hero)} url={hero.cover_url} /></div>
        </section>
      ) : null}
      {unclassified ? <p className="meta">{t("home.genreUnknown")}</p> : null}
      {data.popular.length > 0 ? (
        <section className="section">
          <h2>{t("home.popular")}</h2>
          <div className="cards">{data.popular.map((item) => <Card key={item.id} item={item} />)}</div>
        </section>
      ) : null}
      {data.genres.map((group) => (
        <section className="section" key={group.genre}>
          <h2>{locale === "en" && group.genre_en ? group.genre_en : group.genre}</h2>
          <div className="cards">{group.series.map((item) => <Card key={item.id} item={item} />)}</div>
        </section>
      ))}
    </>
  );
}

export function SearchPage({ query }: { query: string }) {
  const { t, locale, region, go } = useApp();
  const [results, setResults] = useState<SeriesCard[] | null>(null);
  useEffect(() => {
    api<{ results: SeriesCard[] }>(`/api/search?q=${encodeURIComponent(query)}&region=${encodeURIComponent(region)}`, locale)
      .then((payload) => setResults(payload.results))
      .catch(() => setResults([]));
  }, [query, locale, region]);
  return (
    <section>
      <h1>{t("search.title")}</h1>
      {!results ? <p>{t("common.loading")}</p> : results.length === 0 ? <p>{t("search.empty")}</p> : (
        <div className="cards">{results.map((item) => <Card key={item.id} item={item} />)}</div>
      )}
      <p><button className="ghost" onClick={() => go("/")}>{t("watch.back")}</button></p>
    </section>
  );
}

type Authorize = {
  episode_id: number;
  number: number;
  title: string;
  width: number;
  height: number;
  duration_flag: string;
  position_seconds: number;
  sources: { id: string; height: number; label_zh: string; label_en: string; url: string }[];
  subtitles: { id: string; lang: string; label_zh: string; label_en: string; url: string }[];
  next_episode_id: number | null;
  next_access: string | null;
};

export function WatchPage({ slug }: { slug: string }) {
  const { t, locale, user, go, refreshUser } = useApp();
  const [detail, setDetail] = useState<{ series: SeriesCard; episodes: Episode[]; liked: boolean; like_count: number; favorited: boolean; recommendations: SeriesCard[] } | null>(null);
  const [auth, setAuth] = useState<Authorize | null>(null);
  const [gate, setGate] = useState<"membership" | "unavailable" | "codec" | null>(null);
  const [blockCode, setBlockCode] = useState("unsupported");
  const [rendition, setRendition] = useState("source");
  const [speed, setSpeed] = useState(1);
  const [subsOn, setSubsOn] = useState(true);
  const [autoplay, setAutoplay] = useState(localStorage.getItem("leapdrama.autoplay") !== "0");
  const [paused, setPaused] = useState(true);
  const [comments, setComments] = useState<{ id: number; body: string; display_name: string }[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const pendingSeek = useRef(0);
  const lastProgress = useRef(0);

  async function loadDetail() {
    const payload = await api<NonNullable<typeof detail>>(`/api/series/${encodeURIComponent(slug)}`, locale);
    setDetail(payload);
    return payload;
  }

  async function openEpisode(id: number, list: Episode[]) {
    setError("");
    const episode = list.find((item) => item.id === id);
    if (episode && (episode.access === "locked" || episode.access === "unavailable")) {
      setAuth(null);
      setBlockCode(episode.playback_block || "unsupported");
      setGate(episode.playback_block ? "codec" : episode.access === "locked" ? "membership" : "unavailable");
      return;
    }
    try {
      const payload = await api<Authorize>("/api/playback/authorize", locale, { method: "POST", body: JSON.stringify({ episode_id: id }) });
      setGate(null);
      setAuth(payload);
      setRendition(payload.sources[0]?.id || "source");
      pendingSeek.current = payload.position_seconds > 1 ? payload.position_seconds : 0;
      await api("/api/playback/start", locale, { method: "POST", body: JSON.stringify({ episode_id: id }) });
      const thread = await api<{ comments: { id: number; body: string; display_name: string }[] }>(`/api/episodes/${id}/comments`, locale);
      setComments(thread.comments);
    } catch (reason) {
      const code = reason instanceof Error && "code" in reason ? String((reason as { code?: string }).code) : "";
      if (code === "membership_required") setGate("membership");
      else if (code === "codec_unsupported" || code === "not_playable") setGate(code === "codec_unsupported" ? "codec" : "unavailable");
      else setError(reason instanceof Error ? reason.message : t("common.error"));
      setAuth(null);
    }
  }

  useEffect(() => {
    let alive = true;
    loadDetail().then((payload) => {
      if (!alive) return;
      const requested = Number(new URLSearchParams(window.location.search).get("ep"));
      const episode = payload.episodes.find((item) => item.number === requested)
        || payload.episodes.find((item) => item.position_seconds > 1)
        || payload.episodes[0];
      if (episode) void openEpisode(episode.id, payload.episodes);
    }).catch(() => { if (alive) setError(t("common.error")); });
    return () => { alive = false; };
    // Reload when membership changes so locks update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, locale, user?.member]);

  const source = auth?.sources.find((item) => item.id === rendition) || auth?.sources[0];
  const wide = Boolean(auth && auth.width > auth.height && auth.height > 0);

  function onLoaded() {
    const video = videoRef.current;
    if (!video) return;
    video.playbackRate = speed;
    if (pendingSeek.current > 0) video.currentTime = pendingSeek.current;
    const track = video.textTracks[0];
    if (track) track.mode = subsOn ? "showing" : "hidden";
  }

  async function onTime(event: SyntheticEvent<HTMLVideoElement>) {
    if (!user || !auth) return;
    const current = event.currentTarget.currentTime;
    if (current - lastProgress.current < 5) return;
    lastProgress.current = current;
    await api("/api/playback/progress", locale, {
      method: "POST",
      body: JSON.stringify({ episode_id: auth.episode_id, position_seconds: current, completed: false }),
    }).catch(() => undefined);
  }

  function onEnded() {
    if (!detail || !auth) return;
    const next = detail.episodes.find((item) => item.number > auth.number);
    if (!autoplay || !next) return;
    void openEpisode(next.id, detail.episodes);
  }

  async function activate() {
    if (!user) {
      go(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
      return;
    }
    await api("/api/me/membership", locale, { method: "POST", body: "{}" });
    await refreshUser();
    const payload = await loadDetail();
    const target = detail?.episodes.find((item) => item.number === (auth?.number || Number(new URLSearchParams(window.location.search).get("ep")))) || payload.episodes.find((item) => item.access === "locked");
    if (target) await openEpisode(target.id, payload.episodes);
  }

  async function toggleLike() {
    if (!user || !detail) return go("/login");
    const result = await api<{ liked: boolean; count: number }>(`/api/series/${encodeURIComponent(slug)}/like`, locale, { method: "POST", body: "{}" });
    setDetail({ ...detail, liked: result.liked, like_count: result.count });
  }

  async function toggleFavorite() {
    if (!user || !detail) return go("/login");
    const method = detail.favorited ? "DELETE" : "PUT";
    await api(`/api/me/favorites/${encodeURIComponent(slug)}`, locale, { method });
    setDetail({ ...detail, favorited: !detail.favorited });
  }

  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: detail ? titleOf(locale, detail.series) : "LeapDrama", url });
      else {
        await navigator.clipboard.writeText(url);
        setNote(t("watch.copied"));
      }
    } catch {
      setNote(t("watch.copied"));
    }
  }

  async function sendComment(event: FormEvent) {
    event.preventDefault();
    if (!auth) return;
    const form = event.currentTarget as HTMLFormElement;
    const body = new FormData(form).get("body");
    try {
      await api(`/api/episodes/${auth.episode_id}/comments`, locale, { method: "POST", body: JSON.stringify({ body }) });
      form.reset();
      const thread = await api<{ comments: { id: number; body: string; display_name: string }[] }>(`/api/episodes/${auth.episode_id}/comments`, locale);
      setComments(thread.comments);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("common.error"));
    }
  }

  if (!detail) return <p>{error || t("common.loading")}</p>;
  const label = (item: { label_zh: string; label_en: string }) => (locale === "en" ? item.label_en : item.label_zh);
  return (
    <div className="watch">
      <div>
        <p><button className="ghost" onClick={() => go("/")}>{t("watch.back")}</button></p>
        <h1>{titleOf(locale, detail.series)}</h1>
        <p className="meta">{genreOf(locale, detail.series)} · {t("hero.free", { count: detail.series.free_count })}</p>
        <div className="stage">
          <div className="video-wrap">
            {source ? (
              <video
                ref={videoRef}
                className={wide ? "wide" : undefined}
                src={source.url}
                controls
                playsInline
                preload="metadata"
                controlsList="nodownload"
                onLoadedMetadata={onLoaded}
                onTimeUpdate={onTime}
                onEnded={onEnded}
                onPlay={() => setPaused(false)}
                onPause={() => setPaused(true)}
              >
                {subsOn && auth?.subtitles[0] ? (
                  <track kind="subtitles" src={auth.subtitles[0].url} srcLang={auth.subtitles[0].lang} label={label(auth.subtitles[0])} default />
                ) : null}
              </video>
            ) : null}
            {source && paused ? <button className="play-overlay" onClick={() => videoRef.current?.play()}>{t("player.play")}</button> : null}
          </div>
          {gate === "membership" ? (
            <div className="gate">
              <h2>{t("gate.title")}</h2>
              <p>{t("gate.body")}</p>
              <p>{t("gate.listPrice")} · {t("gate.charged")}</p>
              <button className="solid" onClick={() => void activate()}>{user ? t("gate.cta") : t("gate.login")}</button>
            </div>
          ) : null}
          {gate === "unavailable" ? <div className="gate"><p>{t("gate.unavailable")}</p></div> : null}
          {gate === "codec" ? <div className="gate"><p>{blockCode === "hevc" ? t("codec.hevc") : blockCode === "high10" ? t("codec.high10") : blockCode === "unknown" ? t("codec.unknown") : t("codec.unsupported")}</p></div> : null}
          <div className="controls">
            <label>{t("watch.speed")}
              <select value={speed} onChange={(event) => { const value = Number(event.target.value); setSpeed(value); if (videoRef.current) videoRef.current.playbackRate = value; }}>
                {[0.75, 1, 1.25, 1.5, 2].map((value) => <option key={value} value={value}>{value}x</option>)}
              </select>
            </label>
            {auth && auth.sources.length > 1 ? (
              <label>{t("watch.quality")}
                <select value={source?.id} onChange={(event) => { pendingSeek.current = videoRef.current?.currentTime || 0; setRendition(event.target.value); }}>
                  {auth.sources.map((item) => <option key={item.id} value={item.id}>{label(item)}</option>)}
                </select>
              </label>
            ) : source ? <span>{label(source)}</span> : null}
            {auth && auth.subtitles.length > 0 ? (
              <button className="ghost" onClick={() => {
                const next = !subsOn;
                setSubsOn(next);
                const track = videoRef.current?.textTracks[0];
                if (track) track.mode = next ? "showing" : "hidden";
              }}>{subsOn ? t("watch.subtitleOff") : t("watch.subtitle")}</button>
            ) : null}
            <label><input type="checkbox" checked={autoplay} onChange={(event) => { setAutoplay(event.target.checked); localStorage.setItem("leapdrama.autoplay", event.target.checked ? "1" : "0"); }} />{t("watch.autoplay")}</label>
          </div>
          {auth?.duration_flag === "long" ? <p className="warn">{t("watch.long")}</p> : null}
          {detail.series.numbering_note ? <p className="meta">{detail.series.numbering_note}</p> : null}
          <div className="actions">
            <button className="ghost" onClick={() => void toggleLike()}>{detail.liked ? t("watch.liked") : t("watch.like")} {detail.like_count}</button>
            <button className="ghost" onClick={() => void toggleFavorite()}>{detail.favorited ? t("watch.favorited") : t("watch.favorite")}</button>
            <button className="ghost" onClick={() => void share()}>{t("watch.share")}</button>
          </div>
          {error ? <p className="warn">{error}</p> : null}
          <section>
            <h2>{t("watch.comments")}</h2>
            {user ? (
              <form className="comment" onSubmit={(event) => void sendComment(event)}>
                <textarea name="body" className="input" required maxLength={400} placeholder={t("watch.commentPlaceholder")} />
                <button className="solid" type="submit">{t("watch.commentSend")}</button>
              </form>
            ) : <p>{t("watch.loginToComment")}</p>}
            {comments.map((comment) => <article className="comment" key={comment.id}><strong>{comment.display_name}</strong><p>{comment.body}</p></article>)}
          </section>
        </div>
      </div>
      <aside className="side">
        <h2>{t("watch.episodes")}</h2>
        <div className="episode-list">
          {detail.episodes.map((episode) => (
            <button key={episode.id} className={episode.id === auth?.episode_id ? "on" : ""} onClick={() => void openEpisode(episode.id, detail.episodes)}>
              <span>{t("common.episode", { number: episode.number })}</span>
              {episode.access === "locked" ? <span className="chip">{t("common.locked")}</span> : episode.access === "free" ? <span className="chip">{t("common.free")}</span> : null}
              {episode.duration_flag === "long" ? <span className="warn"> {t("watch.long")}</span> : null}
              {episode.play_count > 0 ? <small> · {episode.play_count}</small> : null}
            </button>
          ))}
        </div>
        <h2>{t("watch.recommend")}</h2>
        {detail.recommendations.map((item) => (
          <a key={item.id} className="rec" href={`/watch/${encodeURIComponent(item.slug)}`} onClick={(event) => { event.preventDefault(); go(`/watch/${encodeURIComponent(item.slug)}`); }}>
            <div className="poster"><Poster title={titleOf(locale, item)} url={item.cover_url} /></div>
            <span>{titleOf(locale, item)}<br /><small>{item.reason === "same_genre" ? t("watch.sameGenre") : t("watch.more")}</small></span>
          </a>
        ))}
      </aside>
      {note ? <div className="toast" role="status">{note}</div> : null}
    </div>
  );
}

export function MePage() {
  const { t, locale, user, go, setTheme, theme, setRegion, region, refreshUser } = useApp();
  const [history, setHistory] = useState<{ series_slug: string; series_title: string; series_title_en: string; number: number; position_seconds: number; cover_url: string | null }[]>([]);
  const [favorites, setFavorites] = useState<SeriesCard[]>([]);
  const [billing, setBilling] = useState<{ member: boolean; membership_until: string | null; bills: { id: number; kind: string; list_price_cents: number; charged_cents: number; status: string; created_at: string }[] } | null>(null);
  useEffect(() => {
    if (!user) return;
    api<{ items: typeof history }>("/api/me/history", locale).then((payload) => setHistory(payload.items)).catch(() => undefined);
    api<{ items: SeriesCard[] }>("/api/me/favorites", locale).then((payload) => setFavorites(payload.items)).catch(() => undefined);
    api<NonNullable<typeof billing>>("/api/me/billing", locale).then(setBilling).catch(() => undefined);
  }, [user, locale]);
  if (!user) return <section className="auth"><h1>{t("me.title")}</h1><p>{t("me.guest")}</p><button className="solid" onClick={() => go("/login")}>{t("nav.login")}</button></section>;
  const until = billing?.membership_until ? new Date(billing.membership_until).toLocaleString(locale === "en" ? "en" : "zh-CN") : "";
  return (
    <div className="me">
      <section className="panel" id="history">
        <h2>{t("me.history")}</h2>
        {history.length === 0 ? <p>{t("me.historyEmpty")}</p> : history.map((item) => (
          <p key={`${item.series_slug}-${item.number}`}><button className="text-btn" onClick={() => go(`/watch/${encodeURIComponent(item.series_slug)}?ep=${item.number}`)}>{locale === "en" && item.series_title_en ? item.series_title_en : item.series_title} · {t("common.episode", { number: item.number })}</button></p>
        ))}
      </section>
      <section className="panel" id="favorites">
        <h2>{t("me.favorites")}</h2>
        {favorites.length === 0 ? <p>{t("me.favoritesEmpty")}</p> : <div className="cards">{favorites.map((item) => <Card key={item.id} item={item} />)}</div>}
      </section>
      <section className="panel" id="member">
        <h2>{t("me.member")}</h2>
        <p>{billing?.member ? t("member.active", { until }) : t("member.inactive")}</p>
        <p>{t("gate.listPrice")} · {t("gate.charged")}</p>
        <p>{t("member.note")}</p>
        <div className="actions">
          <button className="solid" onClick={() => void api("/api/me/membership", locale, { method: "POST", body: "{}" }).then(() => refreshUser()).then(() => api<NonNullable<typeof billing>>("/api/me/billing", locale).then(setBilling))}>{t("member.activate")}</button>
          <button className="ghost" onClick={() => void api("/api/me/membership/cancel", locale, { method: "POST", body: "{}" }).then(() => refreshUser()).then(() => api<NonNullable<typeof billing>>("/api/me/billing", locale).then(setBilling))}>{t("member.cancel")}</button>
        </div>
      </section>
      <section className="panel" id="billing">
        <h2>{t("me.billing")}</h2>
        {!billing || billing.bills.length === 0 ? <p>{t("me.billingEmpty")}</p> : (
          <table className="table">
            <thead><tr><th>{t("bill.list")}</th><th>{t("bill.charged")}</th><th></th></tr></thead>
            <tbody>
              {billing.bills.map((bill) => (
                <tr key={bill.id}>
                  <td>USD {(bill.list_price_cents / 100).toFixed(2)}</td>
                  <td>USD {(bill.charged_cents / 100).toFixed(2)}</td>
                  <td>{bill.kind === "cancel" ? t("bill.cancel") : t("bill.activate")} · {t("bill.simulated")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section className="panel" id="region">
        <h2>{t("me.region")}</h2>
        <label>{t("region.label")}
          <select className="input" value={region} onChange={(event) => setRegion(event.target.value)}>
            {["ALL", "SG", "MY", "US", "TH", "PH", "ID", "TW", "HK"].map((code) => <option key={code} value={code}>{t(`region.${code}` as "region.ALL")}</option>)}
          </select>
        </label>
        <p><a href="/legal/region" onClick={(event) => { event.preventDefault(); go("/legal/region"); }}>{t("footer.region")}</a></p>
      </section>
      <section className="panel" id="theme">
        <h2>{t("me.theme")}</h2>
        <div className="seg">
          <button aria-pressed={theme === "light"} onClick={() => setTheme("light")}>{t("me.themeLight")}</button>
          <button aria-pressed={theme === "dark"} onClick={() => setTheme("dark")}>{t("me.themeDark")}</button>
        </div>
        <h2>{t("me.privacy")}</h2>
        <p><a href="/legal/privacy" onClick={(event) => { event.preventDefault(); go("/legal/privacy"); }}>{t("footer.privacy")}</a> · <a href="/legal/terms" onClick={(event) => { event.preventDefault(); go("/legal/terms"); }}>{t("footer.terms")}</a></p>
      </section>
    </div>
  );
}

export function AuthPage() {
  const { t, locale, go, refreshUser } = useApp();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
    try {
      await api(path, locale, { method: "POST", body: JSON.stringify({ email: form.get("email"), password: form.get("password"), display_name: form.get("name") || undefined }) });
      await refreshUser();
      const next = new URLSearchParams(window.location.search).get("next");
      go(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("common.error"));
    }
  }
  return (
    <form className="auth stack" onSubmit={(event) => void submit(event)}>
      <h1>{mode === "login" ? t("auth.login") : t("auth.register")}</h1>
      <p>{t("auth.note")}</p>
      <label>{t("auth.email")}<input name="email" type="email" required autoComplete="username" /></label>
      <label>{t("auth.password")}<input name="password" type="password" required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
      {mode === "register" ? <label>{t("auth.name")}<input name="name" maxLength={40} /></label> : null}
      {error ? <p className="warn">{error}</p> : null}
      <button className="solid" type="submit">{mode === "login" ? t("auth.submitLogin") : t("auth.submitRegister")}</button>
      <button className="text-btn" type="button" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? t("auth.switchRegister") : t("auth.switchLogin")}</button>
    </form>
  );
}

export function CreatorPage() {
  const { t, locale, user, go } = useApp();
  const [overview, setOverview] = useState<{ series: { id: number; title: string; play_count: number; episodes: { number: number; duration_flag: string; play_count: number }[] }[] } | null>(null);
  const [seriesId, setSeriesId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  function load() {
    api<NonNullable<typeof overview>>("/api/creator/overview", locale).then(setOverview).catch((reason) => setMessage(reason instanceof Error ? reason.message : t("common.error")));
  }
  useEffect(() => { if (user && (user.role === "admin" || user.role === "creator")) load(); }, [user, locale]);
  if (!user) return <section className="auth"><p>{t("creator.note")}</p><button className="solid" onClick={() => go("/login?next=/creator")}>{t("nav.login")}</button></section>;
  if (user.role !== "admin" && user.role !== "creator") return <section className="auth"><p>{t("creator.forbidden")}</p></section>;
  async function createSeries(event: FormEvent) {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const created = await api<SeriesCard>("/api/creator/series", locale, { method: "POST", body: JSON.stringify({ title: form.get("title"), genre: form.get("genre"), synopsis: form.get("synopsis") }) });
    setSeriesId(created.id);
    load();
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!seriesId) return;
    const form = event.currentTarget as HTMLFormElement;
    const body = new FormData(form);
    const result = await api<{ number: number; duration_flag: string }>(`/api/creator/series/${seriesId}/episodes`, locale, { method: "POST", body });
    setMessage(`${t("common.episode", { number: result.number })} · ${result.duration_flag}`);
    form.reset();
    load();
  }
  return (
    <section>
      <h1>{t("creator.title")}</h1>
      <p>{t("creator.note")}</p>
      <form className="panel stack" onSubmit={(event) => void createSeries(event)}>
        <label>{t("creator.seriesTitle")}<input name="title" required /></label>
        <label>{t("creator.genre")}<input name="genre" placeholder="都市" /></label>
        <label>{t("creator.synopsis")}<textarea name="synopsis" /></label>
        <button className="solid" type="submit">{t("creator.create")}</button>
      </form>
      <form className="panel stack" onSubmit={(event) => void upload(event)}>
        <label>{t("creator.seriesTitle")}
          <select className="input" value={seriesId ?? ""} onChange={(event) => setSeriesId(Number(event.target.value))}>
            <option value="" />
            {overview?.series.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
        </label>
        <label>{t("creator.number")}<input name="number" type="number" min={1} required /></label>
        <input name="file" type="file" accept="video/mp4,video/webm,video/quicktime" required />
        <button className="solid" type="submit">{t("creator.upload")}</button>
      </form>
      {message ? <p>{message}</p> : null}
      {overview?.series.map((item) => (
        <section key={item.id} className="panel">
          <h2>{item.title}</h2>
          <p>{t("creator.plays")}: {item.play_count}</p>
          <table className="table">
            <tbody>
              {item.episodes.map((episode) => (
                <tr key={episode.number}>
                  <td>{t("common.episode", { number: episode.number })}</td>
                  <td>{episode.play_count}</td>
                  <td>{episode.duration_flag === "long" ? t("creator.flagLong") : episode.duration_flag === "unknown" ? t("creator.flagUnknown") : t("creator.flagOk")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </section>
  );
}

export function LegalPage({ slug }: { slug: string }) {
  const { t } = useApp();
  const key = slug === "terms" || slug === "copyright" || slug === "region" || slug === "privacy" ? slug : "privacy";
  const title = t(`legal.${key}Title` as "legal.privacyTitle");
  const body = t(`legal.${key}Body` as "legal.privacyBody");
  return <article className="panel"><p className="kicker">{t("legal.badge")}</p><h1>{title}</h1><p>{body}</p></article>;
}

export function NotFound() {
  const { t, go } = useApp();
  return <section className="empty"><h1>{t("notfound.title")}</h1><p>{t("notfound.body")}</p><button className="solid" onClick={() => go("/")}>{t("nav.home")}</button></section>;
}

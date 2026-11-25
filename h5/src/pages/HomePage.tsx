import { useEffect, useRef, useState } from "react";
import { getJson } from "../api";
import type { Locale } from "../copy";
import { dramaTitle, floorName, t } from "../copy";
import { formatCount } from "../format";
import { IMG, thumb } from "../img";
import {
  IconChevronRight,
  IconCrown,
  IconFire,
  IconPlaySmall,
  IconSparkle,
} from "../icons";
import type { Banner, ChannelTab, ConfigPayload, DramaCard, FeedDrama, HomeGroup, HomePayload } from "../types";

interface Props {
  locale: Locale;
  onOpen: (dramaId: number) => void;
}

/**
 * The ops backend can be empty on a fresh environment (no ChannelTab rows).
 * Discover is the one pinned tab, so render it anyway instead of a blank page.
 */
const DEFAULT_TAB: ChannelTab = {
  code: "discover",
  title_en: "Discover",
  title_zh: "发现",
  position: 0,
  locked: true,
  group_id: null,
};

/** No banner configured: promote up to 4 unique dramas from the floors into a real carousel. */
function heroFromGroups(groups: HomeGroup[], locale: Locale): Banner[] {
  const seen = new Set<number>();
  const out: Banner[] = [];
  for (const group of groups) {
    for (const item of group.dramas) {
      if (!item?.cover_url || seen.has(item.id)) continue;
      seen.add(item.id);
      out.push({
        id: -item.id,
        drama_id: item.id,
        slot: "hero",
        title: item.title,
        cover_url: item.cover_url,
        kicker: floorName(group.name, locale),
        headline: item.title,
      });
      if (out.length >= 4) return out;
    }
  }
  return out;
}

export function HomePage({ locale, onOpen }: Props) {
  const [tabs, setTabs] = useState<ChannelTab[]>([]);
  const [banners, setBanners] = useState<Banner[]>([]);
  const [groups, setGroups] = useState<HomeGroup[]>([]);
  const [feedItems, setFeedItems] = useState<FeedDrama[]>([]);
  const [selectedTag, setSelectedTag] = useState<string>("");
  const [tabIndex, setTabIndex] = useState(0);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [group, setGroup] = useState<HomeGroup | null>(null);
  const [legalModal, setLegalModal] = useState<"terms" | "copyright" | "regional" | null>(null);

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([
      getJson<ConfigPayload>(`/v1/config?locale=${locale}`),
      getJson<HomePayload>("/v1/home/groups"),
      getJson<{ items?: FeedDrama[] }>("/v1/feed").catch(() => ({ items: [] })),
    ])
      .then(([config, home, feed]) => {
        setTabs(config.tabs);
        setBanners(home.banners);
        setGroups(home.groups);
        setFeedItems(feed.items ?? []);
        setTabIndex((i) => (i >= config.tabs.length ? 0 : i));
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [locale]);

  if (group) {
    return (
      <div className="group-page">
        <div className="group-bar">
          <button className="icon-btn" onClick={() => setGroup(null)}>←</button>
          <h1>{floorName(group.name, locale)}</h1>
        </div>
        <PosterGrid dramas={group.dramas} locale={locale} onOpen={onOpen} />
      </div>
    );
  }

  if (loading) return <HomeSkeleton />;
  if (error) return <div className="center"><button className="retry" onClick={load}>{t(locale, "retry")}</button></div>;

  const shown = tabs.length > 0 ? tabs : [DEFAULT_TAB];
  const tab = shown[tabIndex] ?? DEFAULT_TAB;
  const discover = tab.locked || tabIndex === 0;
  const bound = groups.find((item) => item.id === tab.group_id) ?? null;
  const hasContent = banners.length > 0 || groups.some((group) => group.dramas.length > 0);
  const hero = banners.length > 0 ? banners : heroFromGroups(groups, locale);

  const allTags = Array.from(
    new Set(feedItems.flatMap((d) => d.tags || []).filter(Boolean)),
  ).slice(0, 10);

  const filteredDramas: DramaCard[] = selectedTag
    ? feedItems
        .filter((d) => (d.tags || []).includes(selectedTag))
        .map((d) => ({ id: d.id, title: d.title, cover_url: d.cover_url, play_count: d.play_count }))
    : [];

  return (
    <div className="home-page">
      <div className="channel-wrap">
        <div className="channel" role="tablist">
          {shown.map((item, index) => {
            const active = index === tabIndex;
            return (
              <button
                key={item.code}
                role="tab"
                aria-selected={active}
                className={active ? "channel-tab on" : "channel-tab"}
                onClick={() => { setTabIndex(index); setSelectedTag(""); }}
              >
                <span>{locale === "zh" && item.title_zh ? item.title_zh : item.title_en}</span>
                {active && <span className="channel-indicator" />}
              </button>
            );
          })}
        </div>
        {allTags.length > 0 && discover && (
          <div className="cat-chips" role="group" aria-label="Categories">
            <button
              type="button"
              className={selectedTag === "" ? "cat-chip on" : "cat-chip"}
              onClick={() => setSelectedTag("")}
            >
              {t(locale, "cat_all")}
            </button>
            {allTags.map((tag) => (
              <button
                key={tag}
                type="button"
                className={selectedTag === tag ? "cat-chip on" : "cat-chip"}
                onClick={() => setSelectedTag(tag === selectedTag ? "" : tag)}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>
      {!hasContent ? (
        <div className="center" style={{ height: "60vh" }}>{t(locale, "empty")}</div>
      ) : selectedTag ? (
        <div className="cat-results">
          <PosterGrid dramas={filteredDramas} locale={locale} onOpen={onOpen} />
        </div>
      ) : discover ? (
        <Discover banners={hero} groups={groups} locale={locale} onOpen={onOpen} onMore={setGroup} />
      ) : bound ? (
        <PosterGrid dramas={bound.dramas} locale={locale} onOpen={onOpen} />
      ) : (
        <div className="center" style={{ height: "50vh" }}>{t(locale, "empty")}</div>
      )}

      <footer className="site-footer">
        <div className="site-footer-top">
          <div className="site-footer-brand">
            <span className="brand-m">L</span>
            <span className="brand-rest">eapDrama</span>
          </div>
          <p className="site-footer-tag">{t(locale, "footer_tagline")}</p>
        </div>
        <div className="site-footer-links">
          <a href="/site/privacy.html" target="_blank" rel="noopener noreferrer">{t(locale, "footer_privacy")}</a>
          <button type="button" onClick={() => setLegalModal("terms")}>{t(locale, "footer_terms")}</button>
          <button type="button" onClick={() => setLegalModal("copyright")}>{t(locale, "footer_copyright")}</button>
          <button type="button" onClick={() => setLegalModal("regional")}>{t(locale, "footer_regional")}</button>
          <a href="/admin/" target="_blank" rel="noopener noreferrer">{t(locale, "creator_studio")} ↗</a>
        </div>
        <p className="site-footer-copy">© 2026 LeapDrama. All rights reserved.</p>
      </footer>

      {legalModal && (
        <>
          <button className="sheet-mask" onClick={() => setLegalModal(null)} aria-label={t(locale, "close")} />
          <div className="sheet legal-sheet" role="dialog" aria-modal="true">
            <div className="sheet-head">
              <h3>
                {legalModal === "terms"
                  ? t(locale, "footer_terms")
                  : legalModal === "copyright"
                  ? t(locale, "footer_copyright")
                  : t(locale, "footer_regional")}
              </h3>
              <button className="icon-btn" onClick={() => setLegalModal(null)} aria-label={t(locale, "close")}>✕</button>
            </div>
            <div className="legal-body">
              {legalModal === "terms" && (
                <p>
                  {locale === "zh"
                    ? "本平台提供竖屏微短剧及漫剧在线点播服务。每部剧集前 2 集免费试看，单集时长不超过 3 分钟；后续剧集可通过金币或会员权益解锁。"
                    : "This platform provides vertical micro-drama streaming. The first 2 episodes of each series are free (up to 3 minutes per episode); subsequent episodes unlock via coins or membership."}
                </p>
              )}
              {legalModal === "copyright" && (
                <p>
                  {locale === "zh"
                    ? "平台展示的所有短剧、漫剧、封面与字幕内容均受版权保护，未经授权禁止录制、搬运或用于商业再分发。"
                    : "All dramas, covers, and subtitles are protected by copyright. Unauthorized recording, redistribution, or commercial reuse is prohibited."}
                </p>
              )}
              {legalModal === "regional" && (
                <>
                  <p><strong>简体中文：</strong>本服务遵循您所在地区的数字内容分发与隐私保护规范，支持简体中文、繁体中文与英文多语言体验。</p>
                  <p><strong>繁體中文：</strong>本服務遵循您所在地區之數位內容分發與隱私保護規範，繁體中文介面持續完善中。</p>
                  <p><strong>English:</strong> Regional availability, pricing, and content ratings follow local regulations across supported territories.</p>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function HomeSkeleton() {
  return (
    <div className="home-skeleton" aria-hidden>
      <div className="sk-hero" />
      <div className="sk-floor" />
      <div className="grid3">
        {Array.from({ length: 6 }, (_, index) => <div key={index} className="sk-card" />)}
      </div>
    </div>
  );
}

function Discover({
  banners, groups, locale, onOpen, onMore,
}: {
  banners: Banner[];
  groups: HomeGroup[];
  locale: Locale;
  onOpen: (id: number) => void;
  onMore: (group: HomeGroup) => void;
}) {
  const visible = groups.filter((group) => group.dramas.length > 0);
  if (banners.length === 0 && visible.length === 0) return <div className="center">{t(locale, "empty")}</div>;
  return (
    <>
      {banners.length > 0 && <BannerCarousel banners={banners} locale={locale} onOpen={onOpen} />}
      {visible.map((group) => (
        <Floor key={group.id} group={group} locale={locale} onOpen={onOpen} onMore={() => onMore(group)} />
      ))}
    </>
  );
}

function BannerCarousel({ banners, locale, onOpen }: { banners: Banner[]; locale: Locale; onOpen: (id: number) => void }) {
  const [page, setPage] = useState(0);
  const trackRef = useRef<HTMLDivElement>(null);

  const goTo = (next: number) => {
    const count = banners.length;
    if (count <= 1) return;
    const target = ((next % count) + count) % count;
    setPage(target);
    const el = trackRef.current;
    if (el) el.scrollTo({ left: target * el.clientWidth, behavior: "smooth" });
  };

  useEffect(() => {
    if (banners.length <= 1) return;
    const timer = window.setInterval(() => {
      setPage((prev) => {
        const next = (prev + 1) % banners.length;
        const el = trackRef.current;
        if (el) el.scrollTo({ left: next * el.clientWidth, behavior: "smooth" });
        return next;
      });
    }, 6000);
    return () => window.clearInterval(timer);
  }, [banners.length]);

  return (
    <div className="banner">
      <div
        ref={trackRef}
        className="banner-track"
        onScroll={(event) => {
          const el = event.currentTarget;
          if (el.clientWidth > 0) setPage(Math.round(el.scrollLeft / el.clientWidth));
        }}
      >
        {banners.map((banner, index) => (
          <div
            key={banner.id}
            className="banner-slide"
            role="button"
            tabIndex={0}
            onClick={() => banner.drama_id != null && onOpen(banner.drama_id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                if (banner.drama_id != null) onOpen(banner.drama_id);
              }
            }}
          >
            <span className="banner-media">
              {banner.cover_url && (
                <img
                  className="banner-backdrop"
                  src={thumb(banner.cover_url, IMG.banner, 80, locale)}
                  alt=""
                  loading={index === 0 ? "eager" : "lazy"}
                  decoding="async"
                />
              )}
            </span>
            {banner.cover_url && (
              <div className="banner-poster-showcase" aria-hidden="true">
                <img
                  src={thumb(banner.cover_url, IMG.card, 85, locale)}
                  alt=""
                  loading={index === 0 ? "eager" : "lazy"}
                  decoding="async"
                />
              </div>
            )}
            <div className="banner-copy">
              <div className="banner-badge-row">
                <span className="chip">
                  <IconSparkle size={10} />
                  <span>{t(locale, "exclusive")}</span>
                </span>
                <span className="chip chip-free">{t(locale, "free_two_eps")}</span>
                <span className="chip chip-rule">{t(locale, "short_ep_rule")}</span>
              </div>
              {banner.kicker && <p className="kicker">{floorName(banner.kicker, locale)}</p>}
              <div className="banner-title-row">
                <h2 className="headline">{dramaTitle(banner.headline || banner.title || "", locale)}</h2>
                <span className="banner-play-btn" aria-hidden="true">
                  <IconPlaySmall size={14} />
                  <span>{locale === "zh" ? "立即观看" : "Watch"}</span>
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
      {banners.length > 1 && (
        <>
          <button type="button" className="banner-arrow prev" onClick={(e) => { e.stopPropagation(); goTo(page - 1); }} aria-label="Previous">‹</button>
          <button type="button" className="banner-arrow next" onClick={(e) => { e.stopPropagation(); goTo(page + 1); }} aria-label="Next">›</button>
          <div className="dots">
            {banners.map((banner, index) => (
              <button
                key={banner.id}
                type="button"
                className={index === page ? "dot-btn on" : "dot-btn"}
                onClick={() => goTo(index)}
                aria-label={`Slide ${index + 1}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Floor({
  group, locale, onOpen, onMore,
}: {
  group: HomeGroup;
  locale: Locale;
  onOpen: (id: number) => void;
  onMore: () => void;
}) {
  const style = group.style || "poster3";
  const limit = style === "rank" ? 3 : style === "grid2" ? 4 : 10;
  const isHot = group.name.toLowerCase().includes("hot") || group.name.includes("热");
  return (
    <section className="floor-section">
      <div className="floor-head">
        <span className="floor-bar" />
        <h3 className="floor-title">
          <span>{floorName(group.name, locale)}</span>
          {isHot && (
            <span className="floor-fire-badge">
              <IconFire size={12} />
              <span>HOT</span>
            </span>
          )}
        </h3>
        {group.dramas.length > limit && (
          <button className="floor-more-btn" onClick={onMore} aria-label={t(locale, "more")}>
            <span>{t(locale, "more")}</span>
            <IconChevronRight size={12} />
          </button>
        )}
      </div>
      {style === "rank" ? (
        <RankList dramas={group.dramas.slice(0, limit)} onOpen={onOpen} locale={locale} />
      ) : style === "grid2" ? (
        <LandscapeGrid dramas={group.dramas.slice(0, limit)} badge={group.badge} locale={locale} onOpen={onOpen} />
      ) : (
        <PosterGrid dramas={group.dramas.slice(0, limit)} badge={group.badge} locale={locale} onOpen={onOpen} />
      )}
    </section>
  );
}

function PosterGrid({
  dramas, onOpen, badge, locale,
}: {
  dramas: DramaCard[];
  onOpen: (id: number) => void;
  badge?: string;
  locale: Locale;
}) {
  if (dramas.length === 0) return null;
  return (
    <div className="grid3">
      {dramas.map((drama, index) => (
        <button key={drama.id} className="card" onClick={() => onOpen(drama.id)} type="button">
          <div className="poster">
            <span className="poster-media">
              {drama.cover_url && (
                <img
                  className="cover"
                  src={thumb(drama.cover_url, IMG.card, 75, locale)}
                  alt=""
                  loading="lazy"
                  decoding="async"
                />
              )}
            </span>
            {badge === "rank" && (
              <span className={`poster-rank-badge rank-${index + 1}`}>
                {index === 0 && <IconCrown size={10} />}
                <span>{index + 1}</span>
              </span>
            )}
            <div className="poster-gradient" />
          </div>
          <p className="card-title">{dramaTitle(drama.title, locale)}</p>
        </button>
      ))}
    </div>
  );
}

function LandscapeGrid({
  dramas, badge, locale, onOpen,
}: {
  dramas: DramaCard[];
  badge: string;
  locale: Locale;
  onOpen: (id: number) => void;
}) {
  return (
    <div className="new-release-grid">
      {dramas.map((drama) => (
        <button key={drama.id} className="new-release-card" onClick={() => onOpen(drama.id)} type="button">
          <div className="nr-poster">
            {drama.cover_url && (
              <img
                src={thumb(drama.cover_url, IMG.card, 80, locale)}
                alt=""
                loading="lazy"
                decoding="async"
              />
            )}
          </div>
          <div className="nr-info">
            {badge === "label" && (
              <span className="nr-hot-badge">
                <IconFire size={10} />
                <span>{t(locale, "hot")}</span>
              </span>
            )}
            <strong className="nr-title">{dramaTitle(drama.title, locale)}</strong>
            <span className="nr-meta">
              {t(locale, "free_two_eps")}
              {drama.play_count ? ` · ${formatCount(drama.play_count, locale)}` : ""}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

function RankList({
  dramas, onOpen, locale,
}: {
  dramas: DramaCard[];
  onOpen: (id: number) => void;
  locale: Locale;
}) {
  return (
    <div className="rank-list">
      {dramas.map((drama, index) => {
        const isTop1 = index === 0;
        const isTop2 = index === 1;
        const isTop3 = index === 2;
        const rankClass = isTop1 ? "rank-item rank-1" : isTop2 ? "rank-item rank-2" : isTop3 ? "rank-item rank-3" : "rank-item";

        return (
          <button
            key={drama.id}
            className={rankClass}
            onClick={() => onOpen(drama.id)}
            type="button"
          >
            <div className="rank-num-box">
              {isTop1 && <span className="rank-crown"><IconCrown size={14} /></span>}
              <span className="rank-num">{index + 1}</span>
            </div>

            <div className="rank-thumb-box">
              {drama.cover_url && (
                <img
                  className="cover"
                  src={thumb(drama.cover_url, IMG.rank, 75, locale)}
                  alt=""
                  loading="lazy"
                  decoding="async"
                />
              )}
            </div>

            <div className="rank-info-col">
              <strong className="rank-title">{dramaTitle(drama.title, locale)}</strong>
              <div className="rank-meta-row">
                <span className="rank-tag">
                  {isTop1 ? "TOP 1" : isTop2 ? "TOP 2" : isTop3 ? "TOP 3" : `NO.${index + 1}`}
                </span>
                <span className="rank-trend">
                  <IconFire size={11} />
                  <span>{formatCount(drama.play_count ?? 0, locale)}</span>
                </span>
              </div>
            </div>

            <span className="rank-play-btn" aria-hidden="true">
              <IconPlaySmall size={14} />
            </span>
          </button>
        );
      })}
    </div>
  );
}

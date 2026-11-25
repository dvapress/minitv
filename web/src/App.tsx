import { useEffect, useRef, useState } from "react";

import { fetchMarketing, fetchPreviewCatalog, Marketing, Plan, PreviewDrama } from "./api";
import { ANDROID_APK, ANDROID_MIN } from "./downloads";
import { SiteFooter, SiteHeader, WEB_APP_URL } from "./layout";
import { PrefsProvider, localizeDramaTitle, usePrefs } from "./prefs";
import PreviewPage from "./preview";
import { parseRoute, Route, scrollToRoute } from "./routes";
import { PosterImage, formatPlays } from "./ui";
import WatchPage from "./watch";

type FeatureIcon = "swipe" | "coins" | "diamond";

const features: { icon: FeatureIcon; titleEn: string; titleZh: string; bodyEn: string; bodyZh: string }[] = [
  {
    icon: "swipe",
    titleEn: "Vertical swipe",
    titleZh: "竖屏畅看",
    bodyEn: "Every episode is up to 3 minutes, crafted for mobile and PC. Swipe up or click next — zero waiting.",
    bodyZh: "每集最长 3 分钟，专为移动端与 PC 网页打造，随滑随看、即刻进入高能剧情。",
  },
  {
    icon: "coins",
    titleEn: "First 2 eps free + Coins",
    titleZh: "前 2 集免费 + 金币解锁",
    bodyEn: "Watch the first 2 episodes of every series free, then spend coins to unlock the episodes you love.",
    bodyZh: "全站剧集前 2 集免费试看，后续分集可使用金币灵活解锁，签到任务还能领金币。",
  },
  {
    icon: "diamond",
    titleEn: "Membership",
    titleZh: "会员全站通看",
    bodyEn: "Skip the coins. Members unlock the whole library, ad-free, in up to 1080p.",
    bodyZh: "无需逐集花金币，会员畅享全站剧集无广告 1080p 高清播放。",
  },
];

function FeatureGlyph({ name }: { name: FeatureIcon }) {
  if (name === "swipe") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="7" y="3" width="10" height="18" rx="3" />
        <path d="M12 16.5h.01" />
        <path d="M12 7.2v4.6" />
        <path d="M10.2 8.8 12 7l1.8 1.8" />
      </svg>
    );
  }
  if (name === "coins") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <ellipse cx="12" cy="6.5" rx="7" ry="3" />
        <path d="M5 6.5v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5" />
        <path d="M5 11.5v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3.5 4 9l8 11.5L20 9z" />
      <path d="M4 9h16" />
      <path d="M9.5 9 12 3.7 14.5 9" />
      <path d="M9.5 9 12 20.2 14.5 9" />
    </svg>
  );
}

const faqs = [
  {
    qEn: "Is LeapDrama free?",
    qZh: "LeapDrama 可以免费看吗？",
    aEn: "Yes. The first 2 episodes of every drama are free to watch. Locked episodes unlock with coins or a membership.",
    aZh: "可以。每部剧集前 2 集免费试看，单集不超过 3 分钟；后续分集可用金币或会员解锁。",
  },
  {
    qEn: "Can I watch on the website?",
    qZh: "可以直接在网页上看吗？",
    aEn: "Yes — both PC web and mobile H5 stream right in your browser, no native app install required.",
    aZh: "可以，完整支持 PC 网页与移动端 H5，无需下载原生 App，打开浏览器即可畅看。",
  },
  {
    qEn: "How do coins work?",
    qZh: "金币怎么获取和使用？",
    aEn: "Earn coins from daily check-ins and rewards, then spend them to unlock locked episodes. Members skip coins entirely.",
    aZh: "每日签到和任务均可领取金币，用于按集解锁；开通会员后全站免金币观看。",
  },
  {
    qEn: "Can I cancel anytime?",
    qZh: "会员可以随时取消吗？",
    aEn: "Yes. Cancel from Me → Subscription. Your benefits stay active until the end of the billing period.",
    aZh: "可以。在「我的 → 会员中心」随时取消续费，当期权益持续有效至周期结束。",
  },
];

const planUnit: Record<string, { en: string; zh: string }> = {
  weekly: { en: "week", zh: "周" },
  monthly: { en: "month", zh: "月" },
  yearly: { en: "year", zh: "年" },
};

function HomePage() {
  const { locale, t } = usePrefs();
  const [data, setData] = useState<Marketing | null>(null);
  const [error, setError] = useState("");
  const [teaser, setTeaser] = useState<PreviewDrama[]>([]);
  const [storeNotice, setStoreNotice] = useState("");
  const noticeTimer = useRef<number | null>(null);

  const showStoreNotice = (message: string) => {
    setStoreNotice(message);
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setStoreNotice(""), 6000);
  };

  useEffect(
    () => () => {
      if (noticeTimer.current) window.clearTimeout(noticeTimer.current);
    },
    [],
  );

  const load = () => {
    setError("");
    fetchMarketing()
      .then(setData)
      .catch(() => setError(t("Could not load LeapDrama. Check the API and retry.", "加载 LeapDrama 失败，请稍后重试。")));
  };

  useEffect(() => {
    load();
    fetchPreviewCatalog()
      .then((catalog) => setTeaser(catalog.categories.find((category) => category.id === 0)?.dramas.slice(0, 6) ?? []))
      .catch(() => setTeaser([]));
  }, []);

  // Async sections (stats, plans, teaser row) change the page height, which
  // can strand a #download / #premium anchor; re-anchor once content settles.
  useEffect(() => {
    if (data) scrollToRoute(parseRoute(), { instant: true });
  }, [data, teaser]);

  const stats = data?.stats ?? [];
  const rating = stats.find((stat) => stat.label.toLowerCase().includes("rating"));
  const downloads = stats.find((stat) => stat.label.toLowerCase().includes("download"));
  const trending = data?.trending ?? [];
  const plans: Plan[] = data?.plans ?? [];
  const testimonials = data?.testimonials ?? [];
  const loading = !data && !error;

  return (
    <main>
      <section id="home" className="hero">
        <div className="shell hero-inner">
          <div className="hero-copy">
            <span className="eyebrow">{t("Vertical drama · New episodes daily", "竖屏短剧漫剧 · 每日上新")}</span>
            <h1>
              {t("One Swipe.", "指尖一滑，")}
              <br />
              <em>{t("Leap Into Drama.", "跃入高能好戏。")}</em>
            </h1>
            <p className="lede">
              {t(
                "Watch the first 2 episodes free right in your browser (PC & Mobile H5). Unlock the full library on LeapDrama.",
                "PC 网页与移动端 H5 全适配，每部剧集前 2 集免费试看，在 LeapDrama 随时解锁全集。",
              )}
            </p>
            <div className="hero-actions">
              <a className="btn btn-primary" href={WEB_APP_URL}>
                {t("Watch Online", "立即在线观看")}
              </a>
              <a className="btn btn-ghost" href="#preview">
                {t("Free Preview", "免费试看")}
              </a>
              <a className="btn btn-ghost" href="#premium">
                {t("See plans", "查看会员")}
              </a>
            </div>
            <p className="hero-web-link">
              {t("Prefer the full player?", "直接进入完整播放大厅？")}{" "}
              <a href={WEB_APP_URL} target="_blank" rel="noopener noreferrer">
                {t("Open LeapDrama Web App ↗", "打开 LeapDrama 播放端 ↗")}
              </a>
            </p>
            {stats.length > 0 && (
              <ul className="hero-meta">
                {rating && (
                  <li>
                    <strong>★★★★★</strong>
                    {rating.value} {t("average rating", "综合评分")}
                  </li>
                )}
                {downloads && <li>{downloads.value} {t("viewers worldwide", "全球观众")}</li>}
              </ul>
            )}
          </div>
          <div className="hero-art">
            <div className="phone">
              <img src="/ph_feed.png" alt="LeapDrama vertical player preview" />
            </div>
            {rating && <div className="chip chip-top">★ {rating.value} {t("rating", "评分")}</div>}
            {downloads && <div className="chip chip-bottom">{downloads.value} {t("plays", "次观看")}</div>}
          </div>
        </div>
      </section>

      <section className="stats">
        <div className="shell">
          <div className="stats-grid">
            {loading
              ? Array.from({ length: 4 }, (_, index) => (
                  <div className="stat" key={index}>
                    <span className="skeleton stat-value-skeleton" />
                    <span className="skeleton stat-label-skeleton" />
                  </div>
                ))
              : stats.map((stat) => (
                  <div className="stat" key={stat.label}>
                    <div className="stat-value">{stat.value}</div>
                    <div className="stat-label">{stat.label}</div>
                  </div>
                ))}
          </div>
          {error && (
            <div className="error-banner">
              <span>{error}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={load}>
                Retry
              </button>
            </div>
          )}
        </div>
      </section>

      <section id="about" className="section">
        <div className="shell">
          <div className="section-head">
            <div>
              <span className="eyebrow">{t("Why LeapDrama", "为什么选择 LeapDrama")}</span>
              <h2>{t("Built for the way you watch", "为你的观剧习惯而生")}</h2>
              <p className="section-sub">
                {t("Short, vertical, and always one swipe from the next episode.", "短小精悍、高能竖屏，随时滑向下一集。")}
              </p>
            </div>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <article className="feature" key={feature.titleEn}>
                <span className="feature-icon">
                  <FeatureGlyph name={feature.icon} />
                </span>
                <h3>{t(feature.titleEn, feature.titleZh)}</h3>
                <p>{t(feature.bodyEn, feature.bodyZh)}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="shows" className="section">
        <div className="shell">
          <div className="section-head">
            <div>
              <span className="eyebrow">{t("Shows", "热播剧集")}</span>
              <h2>{t("Trending now", "全站热播")}</h2>
              <p className="section-sub">{t("The dramas our viewers keep coming back to.", "观众追不停的精选爆款短剧。")}</p>
            </div>
            <a className="text-link" href={WEB_APP_URL}>
              {t("Watch Online →", "前往播放大厅 →")}
            </a>
          </div>
          <div className="poster-grid">
            {loading
              ? Array.from({ length: 6 }, (_, index) => (
                  <div className="poster" key={index}>
                    <span className="skeleton poster-skeleton" />
                    <span className="skeleton poster-title-skeleton" />
                  </div>
                ))
              : trending.map((drama) => (
                  <a className="poster" key={drama.id} href={`#watch/${drama.id}`}>
                    <span className="poster-frame">
                      <PosterImage src={drama.cover_url} alt={`${drama.title} cover`} />
                      <span className="poster-overlay">{t("Watch now", "立即观看")}</span>
                    </span>
                    <span className="poster-title">{localizeDramaTitle(drama.title, locale)}</span>
                    {drama.play_count > 0 && (
                      <span className="poster-meta">{formatPlays(drama.play_count)} {t("plays", "次播放")}</span>
                    )}
                  </a>
                ))}
          </div>
          {!loading && !error && trending.length === 0 && (
            <p className="empty-state">{t("No published dramas yet. Check back after the next release.", "暂无上架剧集，敬请期待。")}</p>
          )}
        </div>
      </section>

      {teaser.length > 0 && (
        <section className="section">
          <div className="shell">
            <div className="section-head">
              <div>
                <span className="eyebrow">{t("Free Preview", "免费试看")}</span>
                <h2>{t("Watch free episodes online", "在线免费试看前 2 集")}</h2>
                <p className="section-sub">
                  {t(
                    "The first 2 episodes of our shows stream free in your browser — no app needed. Unlock full series on LeapDrama.",
                    "每部剧集前 2 集浏览器免费直看，无需下载客户端，完整剧集可在 LeapDrama 解锁。",
                  )}
                </p>
              </div>
              <a className="text-link" href="#preview">
                {t("Open the free preview →", "进入免费试看专区 →")}
              </a>
            </div>
            <div className="poster-grid">
              {teaser.map((drama) => (
                <a className="poster" key={drama.id} href={`#watch/${drama.id}`}>
                  <span className="poster-frame">
                    <PosterImage src={drama.cover_url} alt={`${drama.title} cover`} />
                    <span className="preview-badge preview-badge-compact">
                      {drama.free_playable_count} {t("free", "集免费")}
                    </span>
                    <span className="poster-overlay">{t("Watch free", "免费观看")}</span>
                  </span>
                  <span className="poster-title">{localizeDramaTitle(drama.title, locale)}</span>
                  <span className="poster-meta">{t("Free episodes on the web", "网页免费试看")}</span>
                </a>
              ))}
            </div>
          </div>
        </section>
      )}

      {testimonials.length > 0 && (
        <section className="section">
          <div className="shell">
            <div className="section-head">
              <div>
                <span className="eyebrow">Loved by viewers</span>
                <h2>What people say</h2>
              </div>
            </div>
            <div className="quote-grid">
              {testimonials.map((item) => (
                <blockquote className="quote" key={item.author}>
                  <span className="quote-stars" aria-label="5 out of 5 stars">
                    ★★★★★
                  </span>
                  <p>{item.body}</p>
                  <footer>{item.author}</footer>
                </blockquote>
              ))}
            </div>
          </div>
        </section>
      )}

      <section id="premium" className="section">
        <div className="shell">
          <div className="section-head">
            <div>
              <span className="eyebrow">{t("Premium", "会员方案")}</span>
              <h2>{t("Pick how you unlock", "选择你的解锁方式")}</h2>
              <p className="section-sub">
                {t(
                  "Subscribe directly on the web with secure Stripe checkout — works seamlessly across PC and mobile H5.",
                  "支持海外信用卡安全支付（Stripe Checkout），一次开通即可在 PC 网页与移动端 H5 同步畅看。",
                )}
              </p>
            </div>
          </div>
          <div className="plan-grid">
            {loading
              ? Array.from({ length: 3 }, (_, index) => (
                  <div className="plan" key={index}>
                    <span className="skeleton stat-label-skeleton" />
                    <span className="skeleton stat-value-skeleton" />
                    <span className="skeleton stat-label-skeleton" />
                  </div>
                ))
              : plans.map((plan) => (
                  <article
                    className={plan.benefits?.best ? "plan best" : "plan"}
                    key={plan.code}
                  >
                    {plan.benefits?.best && <span className="plan-badge">{t("Most popular", "最受欢迎")}</span>}
                    <h3 className="plan-name">{plan.name_en}</h3>
                    <p className="plan-price">
                      <strong>${(plan.price_cents / 100).toFixed(2)}</strong>
                      <span>
                        / {planUnit[plan.code] ? (locale === "zh" ? planUnit[plan.code].zh : planUnit[plan.code].en) : t("period", "期")}
                      </span>
                    </p>
                    <ul className="plan-benefits">
                      {(plan.benefits?.items ?? []).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    <a
                      className={
                        plan.benefits?.best
                          ? "btn btn-primary btn-block plan-cta"
                          : "btn btn-ghost btn-block plan-cta"
                      }
                      href={WEB_APP_URL}
                    >
                      {t("Subscribe on the web", "前往网页开通")}
                    </a>
                  </article>
                ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="shell">
          <div className="section-head">
            <div>
              <span className="eyebrow">{t("FAQ", "常见问题")}</span>
              <h2>{t("Good to know", "观影指南")}</h2>
            </div>
          </div>
          <div className="faq-list">
            {faqs.map((faq) => (
              <details className="faq-item" key={faq.qEn}>
                <summary>{t(faq.qEn, faq.qZh)}</summary>
                <p>{t(faq.aEn, faq.aZh)}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section id="download" className="section">
        <div className="shell">
          <div className="download-card">
            <div className="download-copy">
              <span className="eyebrow">{t("Watch Anywhere", "随时随地畅看")}</span>
              <h2>{t("Get LeapDrama on your phone", "手机与电脑同步追剧")}</h2>
              <p>
                {t(
                  "Stream every drama directly in your mobile or desktop browser — no installation required. Or grab the Android APK below.",
                  "无需下载原生客户端，PC 网页与移动端 H5 打开即看；也可选择下方 Android 安装包。",
                )}
              </p>
              <div className="store-buttons">
                <a
                  className="store-btn store-btn-apk"
                  href={ANDROID_APK.url}
                  download={`LeapDrama-${ANDROID_APK.version}.apk`}
                >
                  <svg className="icon-stroke" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 3.6v10.4" />
                    <path d="m7.4 9.9 4.6 4.6 4.6-4.6" />
                    <path d="M4.6 17.3v1.3a1.8 1.8 0 0 0 1.8 1.8h11.2a1.8 1.8 0 0 0 1.8-1.8v-1.3" />
                  </svg>
                  <span>
                    <small>
                      Android {ANDROID_MIN}+ · {ANDROID_APK.size}
                    </small>
                    <strong>{t("Download APK", "下载 LeapDrama APK")}</strong>
                  </span>
                </a>
                <a
                  className="store-btn store-btn-web"
                  href={WEB_APP_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <svg className="icon-stroke" viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="12" cy="12" r="8.4" />
                    <path d="M3.6 12h16.8" />
                    <path d="M12 3.6c2.4 2.5 2.4 14.4 0 16.8M12 3.6c-2.4 2.5-2.4 14.4 0 16.8" />
                  </svg>
                  <span>
                    <small>{t("No download needed", "免安装直接看")}</small>
                    <strong>{t("Watch Online", "在线观看")}</strong>
                  </span>
                </a>
              </div>
              <p className="apk-hint">
                {t(
                  `v${ANDROID_APK.version} · The first install asks you to allow installs from this browser — tap Settings, allow, then Install.`,
                  `v${ANDROID_APK.version} · 首次安装如提示权限，请在设置中允许当前浏览器安装应用。`,
                )}
              </p>
              <div className="store-buttons store-buttons-soon">
                <button
                  type="button"
                  className="store-btn"
                  onClick={() =>
                    showStoreNotice(
                      "The iOS app is coming soon — watch online in your browser for now.",
                    )
                  }
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.53 4.08zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
                  </svg>
                  <span>
                    <small>Coming soon</small>
                    <strong>App Store</strong>
                  </span>
                </button>
                <button
                  type="button"
                  className="store-btn"
                  onClick={() =>
                    showStoreNotice(
                      "Google Play is coming soon — download the APK above to install the Android app now.",
                    )
                  }
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3.61 1.81 13.79 12 3.61 22.19a1 1 0 0 1-.61-.92V2.73a1 1 0 0 1 .61-.92zM14.5 12.7l2.3 2.3-10.94 6.34 8.64-8.64zm3.2-3.2 2.8 1.63a1 1 0 0 1 0 1.73l-2.8 1.63-2.5-2.49 2.5-2.5zM5.95 3.06l10.94 6.33-2.3 2.3-8.64-8.63z" />
                  </svg>
                  <span>
                    <small>Coming soon</small>
                    <strong>Google Play</strong>
                  </span>
                </button>
              </div>
              {storeNotice && (
                <p className="store-note" role="status" aria-live="polite">
                  {storeNotice}
                </p>
              )}
            </div>
            <div className="qr-block">
              <div className="qr-tile">
                <img src="/qr-web.png" alt="QR code to watch LeapDrama in your browser" />
              </div>
              <p className="qr-caption">{t("Scan to watch on the web", "扫码在手机浏览器观看")}</p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute());
  const previousKind = useRef<Route["kind"] | null>(null);

  useEffect(() => {
    const onHashChange = () => setRoute(parseRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    const instant = previousKind.current !== null && previousKind.current !== route.kind;
    previousKind.current = route.kind;
    scrollToRoute(route, { instant });
  }, [route]);

  return (
    <PrefsProvider>
      <div className="page">
        <SiteHeader />
        {route.kind === "home" && <HomePage />}
        {route.kind === "preview" && <PreviewPage />}
        {route.kind === "watch" && <WatchPage dramaId={route.dramaId} />}
        <SiteFooter />
      </div>
    </PrefsProvider>
  );
}

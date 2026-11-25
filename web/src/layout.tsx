import { useState } from "react";
import { usePrefs } from "./prefs";
import { FooterModal, type FooterModalKind } from "./SiteModals";

/** Full web app (H5 build). Defaults to same-origin "/" and can be overridden via VITE_WEB_APP_URL. */
export const WEB_APP_URL = import.meta.env.VITE_WEB_APP_URL ?? "/";

/** Operator console. Defaults to same-origin "/admin/" and can be overridden via VITE_ADMIN_URL. */
export const ADMIN_URL = import.meta.env.VITE_ADMIN_URL ?? "/admin/";

type NavItem = { en: string; zh: string; href: string; external?: boolean };

const nav: NavItem[] = [
  { en: "Home", zh: "首页", href: "#home" },
  { en: "Shows", zh: "热播剧集", href: "#shows" },
  { en: "Free Preview", zh: "免费试看", href: "#preview" },
  { en: "Watch Online", zh: "在线观看", href: WEB_APP_URL, external: true },
  { en: "Premium", zh: "会员方案", href: "#premium" },
  { en: "About", zh: "关于我们", href: "#about" },
  { en: "Download", zh: "下载", href: "#download" },
];

export function BrandLogo() {
  return (
    <span className="ld-brand">
      <span className="ld-brand-mark" aria-hidden="true">L</span>
      <span className="ld-brand-text">LeapDrama</span>
    </span>
  );
}

export function SiteHeader() {
  const { locale, toggleLocale, theme, toggleTheme, t } = usePrefs();
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <a className="brand" href="#home">
          <BrandLogo />
        </a>
        <nav className="site-nav" aria-label="Main">
          {nav.map((item) => (
            <a
              key={item.en}
              href={item.href}
              className={item.external ? "site-nav-external" : undefined}
              {...(item.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            >
              {t(item.en, item.zh)}
              {item.external && (
                <span className="nav-ext" aria-hidden="true">
                  ↗
                </span>
              )}
            </a>
          ))}
        </nav>
        <div className="header-actions">
          <button
            type="button"
            className="pref-btn"
            onClick={toggleTheme}
            title={theme === "dark" ? t("Light mode", "切换浅色模式") : t("Dark mode", "切换深色模式")}
            aria-label={theme === "dark" ? "Light mode" : "Dark mode"}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          <button
            type="button"
            className="pref-btn"
            onClick={toggleLocale}
            title={t("Switch to Chinese", "切换为英文")}
          >
            {locale === "zh" ? "EN" : "中"}
          </button>
          <a className="btn btn-primary btn-sm" href={WEB_APP_URL}>
            {t("Watch Now", "立即观看")}
          </a>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  const { t } = usePrefs();
  const [modal, setModal] = useState<FooterModalKind | null>(null);
  return (
    <footer className="site-footer">
      <div className="shell">
        <div className="footer-grid">
          <div className="footer-brand">
            <a className="brand" href="#home">
              <BrandLogo />
            </a>
            <p>
              {t(
                "Vertical micro-dramas, built for PC Web & Mobile H5. Watch the first 2 episodes free, unlock the full series anytime.",
                "竖屏短剧漫剧发行平台，全面适配 PC 网页与移动端 H5。每部剧集前 2 集免费试看，随时解锁全集。",
              )}
            </p>
          </div>
          <div className="footer-col">
            <h4>{t("Product", "产品")}</h4>
            <a href="#shows">{t("Shows", "热播剧集")}</a>
            <a href="#preview">{t("Free Preview", "免费试看")}</a>
            <a href={WEB_APP_URL} target="_blank" rel="noopener noreferrer">
              {t("Watch Online ↗", "在线观看 ↗")}
            </a>
            <a href="#premium">{t("Premium", "会员方案")}</a>
            <a href="#download">{t("Download", "下载")}</a>
          </div>
          <div className="footer-col">
            <h4>{t("Company", "关于")}</h4>
            <button type="button" className="footer-link-btn" onClick={() => setModal("about")}>
              {t("About", "关于我们")}
            </button>
            <button type="button" className="footer-link-btn" onClick={() => setModal("contact")}>
              {t("Contact", "联系我们")}
            </button>
          </div>
          <div className="footer-col">
            <h4>{t("Legal", "条款与隐私")}</h4>
            <button type="button" className="footer-link-btn" onClick={() => setModal("terms")}>
              {t("Terms", "用户协议")}
            </button>
            <a href="/site/privacy.html">{t("Privacy", "隐私政策")}</a>
            <button type="button" className="footer-link-btn" onClick={() => setModal("cookies")}>
              {t("Cookie Settings", "Cookie 设置")}
            </button>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} LeapDrama. {t("All rights reserved.", "保留所有权利。")}</span>
          <div className="footer-bottom-meta">
            <span>{t("Prices shown in USD. First 2 episodes free.", "价格以美元计价，前 2 集免费试看。")}</span>
            <a
              className="footer-admin"
              href={ADMIN_URL}
              target="_blank"
              rel="noopener noreferrer"
              title={t("LeapDrama Creator & Admin Console", "LeapDrama 创作者与管理后台")}
            >
              {t("Creator Studio", "创作者后台")}
              <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
      </div>
      {modal && <FooterModal kind={modal} onClose={() => setModal(null)} />}
    </footer>
  );
}

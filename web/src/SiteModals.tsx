import { useState } from "react";
import { usePrefs } from "./prefs";

export type FooterModalKind = "about" | "contact" | "terms" | "cookies";

export function FooterModal({ kind, onClose }: { kind: FooterModalKind; onClose: () => void }) {
  const { locale, theme, t } = usePrefs();
  const [copied, setCopied] = useState("");
  const [cleared, setCleared] = useState(false);

  const copyEmail = (email: string) => {
    navigator.clipboard?.writeText(email).catch(() => {});
    setCopied(email);
    window.setTimeout(() => setCopied(""), 2200);
  };

  const resetPrefs = () => {
    try {
      localStorage.removeItem("leapdrama_region");
      setCleared(true);
      window.setTimeout(() => setCleared(false), 3000);
    } catch {
      /* ignore */
    }
  };

  const title =
    kind === "about"
      ? t("About LeapDrama", "关于 LeapDrama")
      : kind === "contact"
      ? t("Contact Us", "联系我们")
      : kind === "terms"
      ? t("Terms of Service", "用户协议")
      : t("Cookie & Storage Settings", "Cookie 与本地存储设置");

  return (
    <div className="site-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="site-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="site-modal-head">
          <h3>{title}</h3>
          <button type="button" className="site-modal-close" onClick={onClose} aria-label={t("Close", "关闭")}>
            ✕
          </button>
        </div>
        <div className="site-modal-body">
          {kind === "about" &&
            (locale === "zh" ? (
              <>
                <p className="site-modal-meta">LeapDrama · 全球竖屏微短剧与漫剧发行平台</p>
                <h4>我们的定位</h4>
                <p>
                  LeapDrama 专注于打造面向移动互联网与桌面浏览器的新一代竖屏短剧、漫剧内容发行平台。每集严格控制在 3 分钟以内，节奏紧凑、高能不断，让观众在碎片时间里随时入戏。
                </p>
                <h4>全端无缝观影体验</h4>
                <ul>
                  <li><strong>PC 网页 &amp; 移动端 H5：</strong>打开浏览器即点即看，支持横屏分栏选集与竖屏沉浸滑屏两种交互形态。</li>
                  <li><strong>Android 客户端：</strong>提供官方直装 APK，支持账号跨端同步收藏、观影进度、金币与会员权益。</li>
                  <li><strong>透明试看机制：</strong>全站剧集默认开放前 2 集免费试看，满意后再按集解锁或开通会员。</li>
                </ul>
                <h4>创作者生态</h4>
                <p>
                  我们通过 LeapDrama 创作者后台面向全球短剧制作方与漫剧工作室开放内容分发、多语言字幕适配与数据结算支持。
                </p>
              </>
            ) : (
              <>
                <p className="site-modal-meta">LeapDrama · Global Vertical Micro-Drama &amp; Comic-Drama Platform</p>
                <h4>Our Mission</h4>
                <p>
                  LeapDrama delivers bite-sized, high-emotion vertical dramas and comic-dramas crafted for modern viewers. Every episode runs up to 3 minutes with cinema-grade pacing designed for effortless viewing anywhere.
                </p>
                <h4>Seamless Multi-Device Streaming</h4>
                <ul>
                  <li><strong>PC Web &amp; Mobile H5:</strong> Stream instantly in any browser with split-screen episode navigation on desktop and swipe-first playback on mobile.</li>
                  <li><strong>Android App:</strong> Official Android APK with cross-device sync for watch history, favorites, Coins, and VIP membership.</li>
                  <li><strong>Try Before Unlocking:</strong> The first 2 episodes of every series are free so you always know you love a show before spending Coins.</li>
                </ul>
                <h4>Creator Ecosystem</h4>
                <p>
                  Through LeapDrama Creator Studio, independent studios and rights holders publish localized micro-dramas to global audiences with transparent analytics and monetization.
                </p>
              </>
            ))}

          {kind === "contact" && (
            <>
              <p className="site-modal-meta">
                {t(
                  "We respond within 24–48 business hours in English, Simplified Chinese & Traditional Chinese.",
                  "我们支持简体中文、繁體中文与英文工单，通常在 24–48 个工作小时内回复。",
                )}
              </p>
              <div className="contact-cards">
                {[
                  {
                    label: t("Customer Support & Billing", "用户支持与账单问题"),
                    desc: t("Account login, coin top-ups, membership cancellations & playback help.", "账号登录、金币充值、会员续费取消及播放异常处理。"),
                    email: "support@leapdrama.app",
                  },
                  {
                    label: t("Creator & Content Partnerships", "剧集发行与创作者合作"),
                    desc: t("Studio onboarding, licensed drama submissions & localization.", "短剧/漫剧制作方入驻、版权采购及多语种联合发行。"),
                    email: "partners@leapdrama.app",
                  },
                  {
                    label: t("Copyright & Legal (DMCA)", "版权声明与侵权投诉"),
                    desc: t("Intellectual property notices, takedown requests & compliance.", "知识产权核验、侵权下架通知及地区合规事务。"),
                    email: "legal@leapdrama.app",
                  },
                  {
                    label: t("Privacy & Data Requests", "隐私与个人数据请求"),
                    desc: t("Data export, correction or account deletion requests.", "个人数据查阅、导出、更正或账号注销申请。"),
                    email: "privacy@leapdrama.app",
                  },
                ].map((item) => (
                  <div className="contact-card" key={item.email}>
                    <div>
                      <strong>{item.label}</strong>
                      <p>{item.desc}</p>
                    </div>
                    <div className="contact-actions">
                      <a href={`mailto:${item.email}`} className="contact-email">
                        {item.email}
                      </a>
                      <button type="button" className="contact-copy" onClick={() => copyEmail(item.email)}>
                        {copied === item.email ? t("Copied ✓", "已复制 ✓") : t("Copy", "复制")}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {kind === "terms" &&
            (locale === "zh" ? (
              <>
                <p className="site-modal-meta">生效日期：2026 年 11 月 · 适用范围：LeapDrama 官网、PC 网页端、移动端 H5 及 Android 客户端</p>
                <h4>一、服务说明</h4>
                <p>
                  LeapDrama 提供竖屏微短剧与漫剧在线点播服务。每部剧集默认提供<strong>前 2 集免费试看</strong>（单集通常 ≤ 3 分钟），后续剧集可通过平台金币按集解锁或开通会员全站畅看。
                </p>
                <h4>二、账号与安全</h4>
                <p>
                  您可通过邮箱验证码等方式注册账号，跨设备同步收藏、播放进度、金币余额与会员状态。请妥善保管登录凭证，不得出租、转售或使用自动化脚本抓取平台内容。
                </p>
                <h4>三、金币、会员与支付</h4>
                <ul>
                  <li>金币为本平台虚拟数字道具，仅用于解锁付费剧集或互动支持，不可提现或跨账号转让。</li>
                  <li>付费剧集解锁后即视为数字内容已交付；如发生重复扣款或技术故障无法播放，请联系 <code>support@leapdrama.app</code> 核实处理。</li>
                  <li>支付流程由持牌支付机构（如 Stripe）安全处理，本平台不保存您的银行卡明文信息。</li>
                </ul>
                <h4>四、知识产权与合规</h4>
                <p>
                  本平台展示的全部剧集、海报、字幕与品牌标识均受版权保护，严禁未经授权录屏、盗链、搬运或商业使用。
                </p>
              </>
            ) : (
              <>
                <p className="site-modal-meta">Effective: November 2026 · Applies to LeapDrama Site, PC Web, Mobile H5 &amp; Android App</p>
                <h4>1. Service Overview</h4>
                <p>
                  LeapDrama provides vertical micro-drama and comic-drama streaming. Every series includes the <strong>first 2 episodes free</strong> (typically ≤ 3 minutes/ep); subsequent episodes unlock via Coins or an active VIP membership.
                </p>
                <h4>2. Accounts &amp; Security</h4>
                <p>
                  Register with your email to sync watch history, favorites, Coins, and VIP status across devices. You are responsible for keeping your credentials secure and must not share, resell, or automate account access.
                </p>
                <h4>3. Coins, VIP &amp; Payments</h4>
                <ul>
                  <li>Coins are virtual items redeemable solely on LeapDrama for episode unlocks; they have no cash value and are non-transferable.</li>
                  <li>Unlocked episodes are immediately delivered digital content. Verified duplicate charges or technical playback failures are handled promptly via <code>support@leapdrama.app</code>.</li>
                  <li>Payments are processed securely by licensed payment providers (such as Stripe); LeapDrama never stores raw card numbers.</li>
                </ul>
                <h4>4. Copyright &amp; Acceptable Use</h4>
                <p>
                  All series, posters, subtitles, and brand assets are protected by copyright. Recording, ripping, bypassing signed playback links, or commercial redistribution is prohibited.
                </p>
              </>
            ))}

          {kind === "cookies" && (
            <>
              <p className="site-modal-meta">
                {t(
                  "Manage how LeapDrama uses essential cookies and browser local storage.",
                  "查看并管理 LeapDrama 使用的必要 Cookie 与浏览器本地存储偏好。",
                )}
              </p>
              <div className="cookie-row">
                <div>
                  <strong>{t("Essential & Security Cookies", "必要与安全 Cookie")}</strong>
                  <p>
                    {t(
                      "Required for site access, login sessions, and CSRF protection. Cannot be disabled.",
                      "用于维持站点访问凭证、登录会话与防跨站攻击校验，保障基础安全，不可关闭。",
                    )}
                  </p>
                </div>
                <span className="cookie-pill on">{t("Always On", "始终开启")}</span>
              </div>
              <div className="cookie-row">
                <div>
                  <strong>{t("Interface Preferences (Local Storage)", "界面偏好（本地存储）")}</strong>
                  <p>
                    {t(
                      `Stores your language (${locale.toUpperCase()}), theme (${theme}), and region selection locally on this device.`,
                      `仅在本地设备保存您的界面语言（${locale === "zh" ? "中文" : "EN"}）、主题模式（${theme === "dark" ? "深色" : "浅色"}）与地区偏好。`,
                    )}
                  </p>
                </div>
                <span className="cookie-pill">{t("Active", "已启用")}</span>
              </div>
              <div className="cookie-footer">
                <button type="button" className="btn btn-ghost btn-sm" onClick={resetPrefs}>
                  {cleared ? t("Region cache cleared ✓", "已重置地区缓存 ✓") : t("Reset Region Preference", "重置地区偏好")}
                </button>
                <a className="btn btn-primary btn-sm" href="/site/privacy.html">
                  {t("Read Full Privacy Policy →", "查看完整隐私政策 →")}
                </a>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

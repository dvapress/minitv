import { useState } from "react";
import type { Locale } from "../copy";

export type LegalKind = "terms" | "copyright" | "regional";

export function LegalContent({ kind, locale }: { kind: LegalKind; locale: Locale }) {
  const [regionTab, setRegionTab] = useState<"zh-cn" | "zh-tw" | "en">(locale === "zh" ? "zh-cn" : "en");

  if (kind === "terms") {
    return locale === "zh" ? (
      <div className="legal-doc">
        <p className="legal-meta">生效日期：2026 年 11 月 · 适用范围：LeapDrama PC 网页端、移动端 H5 及 Android 客户端</p>

        <h4>一、服务说明</h4>
        <p>
          LeapDrama（以下简称“本平台”）为用户提供竖屏微短剧与漫剧在线点播服务。每部上线剧集默认开放<strong>前 2 集免费试看</strong>（单集时长通常不超过 3 分钟），后续剧集可通过平台金币单集解锁或开通会员权益畅享全集。
        </p>

        <h4>二、账号注册与安全</h4>
        <ul>
          <li>您可通过邮箱验证码或受支持的第三方登录方式注册并使用本平台账号，用于跨设备同步收藏列表、观影进度、金币余额与会员状态。</li>
          <li>您应妥善保管账号登录凭证，不得将账号出租、出借、转让或用于自动化脚本批量访问。因保管不善导致的损失由用户自行承担。</li>
        </ul>

        <h4>三、金币、会员与支付规则</h4>
        <ul>
          <li>平台金币属于数字化虚拟道具，仅限在本平台内用于解锁付费剧集或参与创作者互动，不可兑换现金、不可跨账号转移。</li>
          <li>付费剧集一经解锁即视为数字化内容已交付，除法律法规另有强制性规定或因平台技术故障导致无法播放外，不支持无理由退费。</li>
          <li>会员权益在有效期内自动生效；若涉及第三方支付渠道（如 Stripe 等），交易安全与账单记录由对应持牌支付机构提供保障。</li>
        </ul>

        <h4>四、用户行为规范</h4>
        <ul>
          <li>禁止通过录屏、抓包、解析签名播放地址或反编译手段下载、搬运、二次分发本平台视频与字幕资源。</li>
          <li>评论与互动内容应遵守所在地法律法规，严禁发布违法违规、人身攻击、广告引流或剧透恶意刷屏信息。</li>
        </ul>

        <h4>五、服务变更与免责声明</h4>
        <p>
          因版权周期调整、系统维护或不可抗力，本平台可能对部分剧集上线状态或功能进行调整，并尽可能提前通过站内公告提示。如对本协议有任何疑问，请联系 <code>support@leapdrama.app</code>。
        </p>
      </div>
    ) : (
      <div className="legal-doc">
        <p className="legal-meta">Effective: November 2026 · Applies to LeapDrama PC Web, Mobile H5, and Android App</p>

        <h4>1. Service Description</h4>
        <p>
          LeapDrama (“the Platform”) provides vertical micro-drama and comic-drama streaming. Every series includes the <strong>first 2 episodes free</strong> (typically ≤ 3 minutes per episode). Subsequent episodes can be unlocked per episode using virtual Coins or streamed with an active VIP membership.
        </p>

        <h4>2. Account Registration &amp; Security</h4>
        <ul>
          <li>You may register via email verification code or supported sign-in methods to sync your favorites, watch progress, Coin balance, and VIP status across devices.</li>
          <li>You are responsible for safeguarding your login credentials and agree not to rent, resell, share, or access accounts via automated bots or scraping tools.</li>
        </ul>

        <h4>3. Coins, VIP Membership &amp; Billing</h4>
        <ul>
          <li>Coins are virtual digital items redeemable solely on LeapDrama for episode unlocks or creator support; they carry no cash value and are non-transferable.</li>
          <li>Unlocked episodes constitute immediately delivered digital content. Except where required by mandatory local consumer law or in cases of verified technical failure, completed unlocks are non-refundable.</li>
          <li>Payments are processed securely through licensed payment providers (such as Stripe); LeapDrama does not store raw payment card numbers.</li>
        </ul>

        <h4>4. Acceptable Use</h4>
        <ul>
          <li>You must not record, rip, scrape, bypass signed playback URLs, or redistribute any video, audio, artwork, or subtitle assets from LeapDrama.</li>
          <li>User comments and community interactions must remain lawful and respectful; spam, harassment, hate speech, and unauthorized promotions are prohibited.</li>
        </ul>

        <h4>5. Service Updates &amp; Contact</h4>
        <p>
          Catalog availability may change due to licensing windows or maintenance. For questions regarding these Terms, contact <code>support@leapdrama.app</code>.
        </p>
      </div>
    );
  }

  if (kind === "copyright") {
    return locale === "zh" ? (
      <div className="legal-doc">
        <p className="legal-meta">最后更新：2026 年 11 月 · LeapDrama 知识产权与版权保护声明</p>

        <h4>一、平台知识产权归属</h4>
        <p>
          LeapDrama 平台上展示的全部微短剧、漫剧正片、预告片、定制海报、中英文剧名与多语字幕、背景音乐，以及 LeapDrama 商标、界面设计与源代码，均受国际版权公约及适用法律保护，其知识产权归 LeapDrama 或合法授权合作方所有。
        </p>

        <h4>二、个人非商业授权范围</h4>
        <ul>
          <li>用户在遵守《用户协议》的前提下，仅获得有限的、非独占的、不可转让的个人在线观影许可。</li>
          <li>未经书面授权，任何个人或机构不得对平台内容进行录制、去水印、剪辑搬运、公开商业放映、镜像聚合或用于模型训练抓取。</li>
        </ul>

        <h4>三、创作者与合作方权利保证</h4>
        <p>
          通过 LeapDrama 创作者后台上传剧集、封面或字幕的合作方，均须保证其对提交内容拥有完整合法的著作权或转授权，且不侵犯任何第三方的肖像权、名誉权、商标权及音乐版权。
        </p>

        <h4>四、侵权投诉与下架指引（DMCA / 版权通知）</h4>
        <p>
          如您认为本平台存在侵犯您合法版权的内容，请将以下材料发送至 <code>legal@leapdrama.app</code>，我们将在核实后尽快依法采取下架或断开链接措施：
        </p>
        <ul>
          <li>权利人身份证明及有效联系方式；</li>
          <li>涉嫌侵权剧集名称、集数及具体页面链接（URL）；</li>
          <li>权属证明文件（著作权登记证、授权链或首发证明）与真实性声明。</li>
        </ul>
      </div>
    ) : (
      <div className="legal-doc">
        <p className="legal-meta">Last Updated: November 2026 · LeapDrama Intellectual Property &amp; Copyright Notice</p>

        <h4>1. Ownership of Content &amp; Trademarks</h4>
        <p>
          All micro-dramas, comic-dramas, trailers, studio posters, bilingual titles, subtitle tracks, audio scores, and the LeapDrama name, brand marks, UI design, and software are protected by international copyright and trademark laws and belong to LeapDrama or its licensed content partners.
        </p>

        <h4>2. Limited Personal Streaming License</h4>
        <ul>
          <li>Subject to the Terms of Service, LeapDrama grants you a limited, non-exclusive, non-transferable license to stream content solely for personal, non-commercial entertainment.</li>
          <li>Screen recording, watermarking removal, unauthorized re-uploading, public commercial exhibition, automated scraping, or dataset harvesting is strictly prohibited.</li>
        </ul>

        <h4>3. Creator &amp; Partner Warranties</h4>
        <p>
          Studios and creators publishing via LeapDrama Creator Studio warrant that they hold all necessary copyrights, music clearances, and talent releases for every submitted episode, poster, and subtitle file.
        </p>

        <h4>4. Copyright Infringement / DMCA Takedown</h4>
        <p>
          If you believe content on LeapDrama infringes your copyright, please submit a written notice to <code>legal@leapdrama.app</code> containing:
        </p>
        <ul>
          <li>Your full name, organization, and verifiable contact details;</li>
          <li>The exact series title, episode number, and URL of the allegedly infringing material;</li>
          <li>Proof of copyright ownership or authorization, plus a good-faith statement of accuracy.</li>
        </ul>
      </div>
    );
  }

  return (
    <div className="legal-doc">
      <div className="legal-tabs" role="tablist" aria-label="Regional language selector">
        <button
          type="button"
          role="tab"
          aria-selected={regionTab === "zh-cn"}
          className={regionTab === "zh-cn" ? "legal-tab on" : "legal-tab"}
          onClick={() => setRegionTab("zh-cn")}
        >
          简体中文
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={regionTab === "zh-tw"}
          className={regionTab === "zh-tw" ? "legal-tab on" : "legal-tab"}
          onClick={() => setRegionTab("zh-tw")}
        >
          繁體中文
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={regionTab === "en"}
          className={regionTab === "en" ? "legal-tab on" : "legal-tab"}
          onClick={() => setRegionTab("en")}
        >
          English
        </button>
      </div>

      {regionTab === "zh-cn" && (
        <>
          <p className="legal-meta">适用地区：简体中文用户及亚太相关服务区域 · 2026 年 11 月更新</p>
          <h4>一、合规与内容分级</h4>
          <p>
            本平台严格遵循服务所在地区关于网络视听内容与未成年人保护的法律法规。如您未满 18 周岁，请在法定监护人同意与指导下使用本服务并进行任何付费操作。
          </p>
          <h4>二、定价、货币与消费者权益</h4>
          <p>
            金币充值包与会员方案将依据您所选择的区域展示对应币种与含税价格。如因网络异常导致重复扣款或未及时到账，您可在 7 个工作日内凭订单号联系 <code>support@leapdrama.app</code> 核实补发或退款。
          </p>
          <h4>三、数据本地偏好与跨端同步</h4>
          <p>
            您的界面语言、深浅色主题与地区设置将通过浏览器本地存储保存，并可在登录同一账号后于 PC 网页、移动端 H5 与 Android 客户端间自动同步观看进度与收藏记录。
          </p>
        </>
      )}

      {regionTab === "zh-tw" && (
        <>
          <p className="legal-meta">適用地區：香港、澳門、台灣及海外繁體中文用戶 · 2026 年 11 月更新</p>
          <h4>一、地區法規與個人資料保護</h4>
          <p>
            本服務遵循您所在地區之數位內容分發與個人資料保護規範（包含個人資料保護法及跨境傳輸安全準則）。您得隨時查閱、匯出、更正或請求刪除您的帳號與個人資料。
          </p>
          <h4>二、數位內容消費與退費說明</h4>
          <p>
            本平台每部微短劇均提供前 2 集免費試看。付費解鎖之數位影音內容一經交付並開始串流播放，依各該地區通訊交易合理例外情事規定，除系統異常無法播放外，不適用七日無條件退貨；惟重複扣款或技術故障情形將全額協助處理。
          </p>
          <h4>三、多語介面與字幕支援</h4>
          <p>
            我們持續擴充繁體中文劇名、介面與字幕在地化體驗。若對地區條款或帳單有任何疑問，歡迎來信 <code>support@leapdrama.app</code>。
          </p>
        </>
      )}

      {regionTab === "en" && (
        <>
          <p className="legal-meta">Applicable Territories: Global, Africa, Europe &amp; Americas · Updated November 2026</p>
          <h4>1. Regional Availability &amp; Pricing</h4>
          <p>
            Series availability, episode pricing, tax calculations, and payment methods vary by territory based on local licensing and regulations. Switching your region selector updates regional recommendations and displayed pricing rules.
          </p>
          <h4>2. Data Protection Rights (GDPR / Local Privacy Laws)</h4>
          <p>
            Where applicable under GDPR, UK GDPR, POPIA, NDPR, or CCPA, you have the right to access, rectify, port, restrict, or erase your personal data and withdraw consent at any time by contacting <code>privacy@leapdrama.app</code>.
          </p>
          <h4>3. Age Guidance &amp; Dispute Resolution</h4>
          <p>
            Users must meet the minimum digital consent age in their jurisdiction (typically 13–16 years old, or with parental consent). Nothing in these terms limits statutory consumer rights granted by mandatory local law.
          </p>
        </>
      )}
    </div>
  );
}

import { useEffect, useState, type ReactNode } from "react";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { LoginSheet } from "./auth/LoginSheet";
import { loadLocale, saveLocale, t, type Locale } from "./copy";
import { IconForYou, IconHome, IconMe, IconRewards, IconSearch } from "./icons";
import { ForYouPage } from "./pages/ForYouPage";
import { HomePage } from "./pages/HomePage";
import { MePage } from "./pages/MePage";
import { PlayPage } from "./pages/PlayPage";
import { RewardsPage } from "./pages/RewardsPage";
import { SearchPage } from "./pages/SearchPage";
import { toast, ToastHost } from "./ui/toast";

type Tab = "home" | "foryou" | "rewards" | "me";

interface TabItem {
  id: Tab;
  key: string;
  renderIcon: (active: boolean) => ReactNode;
}

const TABS: TabItem[] = [
  { id: "home", key: "nav.home", renderIcon: (active) => <IconHome active={active} /> },
  { id: "foryou", key: "nav.foryou", renderIcon: (active) => <IconForYou active={active} /> },
  { id: "rewards", key: "nav.rewards", renderIcon: (active) => <IconRewards active={active} /> },
  { id: "me", key: "nav.me", renderIcon: (active) => <IconMe active={active} /> },
];

export function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}

type Theme = "dark" | "light";
const THEME_KEY = "leapdrama_theme";

function AppShell() {
  const { loginOpen, refresh, user, openLogin } = useAuth();
  const [locale, setLocale] = useState<Locale>(loadLocale);
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark",
  );
  const [tab, setTab] = useState<Tab>("home");
  const [dramaId, setDramaId] = useState<number | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "leapdrama_locale" && (e.newValue === "en" || e.newValue === "zh")) {
        setLocale(e.newValue);
      }
      if (e.key === THEME_KEY && (e.newValue === "light" || e.newValue === "dark")) {
        setTheme(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggleTheme = () => setTheme((prev) => (prev === "dark" ? "light" : "dark"));

  // Stripe sends the browser back here after Checkout. Clean the flag out of the
  // URL and re-read /v1/me so the "Premium active" strip appears immediately.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("checkout");
    if (!result) return;
    params.delete("checkout");
    const query = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    if (result === "success") {
      setTab("me");
      void refresh();
      toast(t(locale, "premium_paid"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const changeLocale = (next: Locale) => {
    saveLocale(next);
    setLocale(next);
  };

  const switchLocale = () => changeLocale(locale === "zh" ? "en" : "zh");

  const playing = dramaId != null;

  const goTab = (next: Tab) => {
    setDramaId(null);
    setSearching(false);
    setTab(next);
  };

  return (
    <div className={playing ? "app is-playing" : "app"} id="app">
      <header className={!playing && tab !== "me" ? "topbar" : "topbar desktop-only-bar"}>
        <div className="topbar-inner">
          {searching ? null : tab === "home" || playing || tab === "me" ? (
            <button type="button" className="brand" onClick={() => goTab("home")}>
              <span className="brand-m">L</span>
              <span className="brand-rest">eapDrama</span>
            </button>
          ) : (
            <>
              <button type="button" className="brand desktop-brand" onClick={() => goTab("home")}>
                <span className="brand-m">L</span>
                <span className="brand-rest">eapDrama</span>
              </button>
              <h1 className="mobile-title">{t(locale, TABS.find((item) => item.id === tab)!.key)}</h1>
            </>
          )}

          <nav className="desktop-nav" aria-label="Primary">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={!playing && !searching && tab === item.id ? "desktop-nav-link on" : "desktop-nav-link"}
                onClick={() => goTab(item.id)}
              >
                {t(locale, item.key)}
              </button>
            ))}
            <a className="desktop-nav-link creator-link" href="/site/">
              {t(locale, "official_site")} ↗
            </a>
            <a className="desktop-nav-link creator-link" href="/admin/" target="_blank" rel="noopener noreferrer">
              {t(locale, "creator_studio")} ↗
            </a>
          </nav>

          <span style={{ flex: 1 }} />

          {!searching && (
            <button
              type="button"
              className="desktop-search-pill"
              onClick={() => { setDramaId(null); setSearching(true); }}
              aria-label={t(locale, "search")}
            >
              <IconSearch />
              <span>{t(locale, "search")}</span>
            </button>
          )}

          <button
            type="button"
            className="icon-btn theme-btn"
            onClick={toggleTheme}
            title={theme === "dark" ? t(locale, "theme_light") : t(locale, "theme_dark")}
            aria-label={theme === "dark" ? t(locale, "theme_light") : t(locale, "theme_dark")}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>

          <button type="button" className="icon-btn" onClick={switchLocale} title="Language">
            {locale === "zh" ? "EN" : "中"}
          </button>

          {!searching && (
            <button
              type="button"
              className="icon-btn search-btn mobile-search-btn"
              onClick={() => { setDramaId(null); setSearching(true); }}
              aria-label={t(locale, "search")}
            >
              <IconSearch />
            </button>
          )}

          {user ? (
            <button type="button" className="desktop-user-pill" onClick={() => goTab("me")}>
              <span className="desktop-user-coins">{user.coins}</span>
              <span>{user.display_name || user.email?.split("@")[0] || t(locale, "nav.me")}</span>
            </button>
          ) : (
            <button type="button" className="desktop-signin-btn" onClick={openLogin}>
              {t(locale, "sign_in")} / {t(locale, "sign_up")}
            </button>
          )}
        </div>
      </header>
      <main className={playing || tab === "foryou" ? "stage bleed" : "stage"}>
        {playing ? (
          <PlayPage
            dramaId={dramaId}
            locale={locale}
            onBack={() => setDramaId(null)}
            onOpenDrama={setDramaId}
            onOpenRewards={() => { setDramaId(null); setTab("rewards"); }}
          />
        ) : searching ? (
          <SearchPage locale={locale} onBack={() => setSearching(false)} onOpen={(id) => { setSearching(false); setDramaId(id); }} />
        ) : tab === "home" ? (
          <HomePage locale={locale} onOpen={setDramaId} />
        ) : tab === "foryou" ? (
          <ForYouPage locale={locale} onOpenDrama={setDramaId} />
        ) : tab === "me" ? (
          <MePage locale={locale} onLocale={changeLocale} onOpen={setDramaId} />
        ) : (
          <RewardsPage locale={locale} onExplore={(target) => setTab(target)} />
        )}
      </main>
      {!playing && !searching && !loginOpen && (
        <nav className="tabs" role="tablist">
          {TABS.map((item) => {
            const active = item.id === tab;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                data-tab={item.id}
                aria-selected={active}
                className={active ? "tab-item on" : "tab-item"}
                onClick={() => setTab(item.id)}
              >
                <span className="tab-icon">{item.renderIcon(active)}</span>
                <span className="tab-label">{t(locale, item.key)}</span>
              </button>
            );
          })}
        </nav>
      )}
      <LoginSheet locale={locale} />
      <ToastHost />
    </div>
  );
}

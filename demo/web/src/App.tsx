import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, type User } from "./api";
import { AppContext } from "./context";
import { translate, type Locale } from "./i18n";
import { AuthPage, CreatorPage, HomePage, LegalPage, MePage, NotFound, SearchPage, WatchPage } from "./pages";

function Logo() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#1a140f" />
      <path d="M8 9h3v14H8zM21 9h3v14h-3z" fill="#e0b15a" />
      <path d="M12 16c2-5 6-7 10-4" fill="none" stroke="#f6f0e6" strokeWidth="1.7" strokeLinecap="round" />
      <circle cx="22" cy="12" r="1.4" fill="#d15a48" />
    </svg>
  );
}

function routeOf(path: string) {
  const url = new URL(path, "http://local");
  const name = url.pathname;
  if (name === "/") return { page: "home" as const, slug: "", query: url.searchParams };
  if (name === "/search") return { page: "search" as const, slug: "", query: url.searchParams };
  if (name === "/me") return { page: "me" as const, slug: "", query: url.searchParams };
  if (name === "/login") return { page: "login" as const, slug: "", query: url.searchParams };
  if (name === "/creator") return { page: "creator" as const, slug: "", query: url.searchParams };
  const watch = name.match(/^\/watch\/([^/]+)$/);
  if (watch) return { page: "watch" as const, slug: decodeURIComponent(watch[1]), query: url.searchParams };
  const legal = name.match(/^\/legal\/(privacy|terms|copyright|region)$/);
  if (legal) return { page: "legal" as const, slug: legal[1], query: url.searchParams };
  return { page: "missing" as const, slug: "", query: url.searchParams };
}

export function App() {
  const [path, setPath] = useState(window.location.pathname + window.location.search);
  const [locale, setLocaleState] = useState<Locale>(localStorage.getItem("leapdrama.locale") === "en" ? "en" : "zh");
  const [theme, setThemeState] = useState<"light" | "dark">(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  const [region, setRegionState] = useState(localStorage.getItem("leapdrama.region") || "ALL");
  const [user, setUser] = useState<User | null>(null);
  const route = routeOf(path);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname + window.location.search);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale === "en" ? "en" : "zh-Hans";
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("leapdrama.locale", locale);
    localStorage.setItem("leapdrama.theme", theme);
    localStorage.setItem("leapdrama.region", region);
  }, [locale, theme, region]);

  async function refreshUser() {
    try {
      setUser(await api<User | null>("/api/me", locale));
    } catch {
      setUser(null);
    }
  }

  useEffect(() => { void refreshUser(); }, [locale]);

  function go(next: string) {
    window.history.pushState({}, "", next);
    setPath(next);
  }

  function setLocale(next: Locale) {
    setLocaleState(next);
    if (user) void api<User>("/api/me", next, { method: "PATCH", body: JSON.stringify({ locale: next }) }).then(setUser).catch(() => undefined);
  }
  function setTheme(next: "light" | "dark") {
    setThemeState(next);
    if (user) void api<User>("/api/me", locale, { method: "PATCH", body: JSON.stringify({ theme: next }) }).then(setUser).catch(() => undefined);
  }
  function setRegion(next: string) {
    setRegionState(next);
    if (user) void api<User>("/api/me", locale, { method: "PATCH", body: JSON.stringify({ region: next }) }).then(setUser).catch(() => undefined);
  }

  const value = useMemo(() => ({
    t: (key: Parameters<typeof translate>[1], vars?: Record<string, string | number>) => translate(locale, key, vars),
    locale, setLocale, theme, setTheme, region, setRegion, user, refreshUser, go, path,
  }), [locale, theme, region, user, path]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const query = new FormData(event.currentTarget as HTMLFormElement).get("q");
    go(`/search?q=${encodeURIComponent(String(query || ""))}`);
  }

  let page = <NotFound />;
  if (route.page === "home") page = <HomePage />;
  if (route.page === "search") page = <SearchPage query={route.query.get("q") || ""} />;
  if (route.page === "watch") page = <WatchPage slug={route.slug} />;
  if (route.page === "me") page = <MePage />;
  if (route.page === "login") page = <AuthPage />;
  if (route.page === "creator") page = <CreatorPage />;
  if (route.page === "legal") page = <LegalPage slug={route.slug} />;

  return (
    <AppContext.Provider value={value}>
      <div className="shell">
        <a className="skip" href="#content">{locale === "en" ? "Skip to content" : "跳到内容"}</a>
        <header className="wrap topbar">
          <a className="brand" href="/" onClick={(event) => { event.preventDefault(); go("/"); }}>
            <Logo />
            <span><strong>LeapDrama</strong><small>{translate(locale, "tagline")}</small></span>
          </a>
          <form className="search" onSubmit={onSearch} role="search">
            <input name="q" placeholder={translate(locale, "search.placeholder")} aria-label={translate(locale, "search.placeholder")} />
            <button className="ghost" type="submit">{translate(locale, "search.submit")}</button>
          </form>
          <div className="tools">
            <div className="seg" aria-label="language">
              <button type="button" aria-pressed={locale === "zh"} onClick={() => setLocale("zh")}>中文</button>
              <button type="button" aria-pressed={locale === "en"} onClick={() => setLocale("en")}>EN</button>
            </div>
            <label>
              <span className="meta">{translate(locale, "region.label")}</span>
              <select className="input" value={region} onChange={(event) => setRegion(event.target.value)} aria-label={translate(locale, "region.label")}>
                {["ALL", "SG", "MY", "US", "TH", "PH", "ID", "TW", "HK"].map((code) => (
                  <option key={code} value={code}>{translate(locale, `region.${code}` as "region.ALL")}</option>
                ))}
              </select>
            </label>
            <button className="ghost" type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? translate(locale, "me.themeLight") : translate(locale, "me.themeDark")}</button>
            {user ? <button className="ghost" type="button" onClick={() => go("/me")}>{user.member ? translate(locale, "nav.member") : user.display_name}</button> : <button className="solid" type="button" onClick={() => go("/login")}>{translate(locale, "nav.login")}</button>}
            <button className="ghost" type="button" onClick={() => go("/creator")}>{translate(locale, "nav.creator")}</button>
          </div>
        </header>
        <div className="wrap"><p className="demo-banner">{translate(locale, "demo.banner")}</p></div>
        <main id="content" className="wrap page">{page}</main>
        <footer className="wrap footer">
          <nav>
            <a href="/legal/privacy" onClick={(event) => { event.preventDefault(); go("/legal/privacy"); }}>{translate(locale, "footer.privacy")}</a>
            <a href="/legal/terms" onClick={(event) => { event.preventDefault(); go("/legal/terms"); }}>{translate(locale, "footer.terms")}</a>
            <a href="/legal/copyright" onClick={(event) => { event.preventDefault(); go("/legal/copyright"); }}>{translate(locale, "footer.copyright")}</a>
            <a href="/legal/region" onClick={(event) => { event.preventDefault(); go("/legal/region"); }}>{translate(locale, "footer.region")}</a>
          </nav>
          <p>{translate(locale, "footer.note")}</p>
          <p>{translate(locale, "footer.credit")}</p>
        </footer>
      </div>
    </AppContext.Provider>
  );
}

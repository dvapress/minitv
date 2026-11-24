import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Locale = "en" | "zh";
export type Theme = "dark" | "light";

const LOCALE_KEY = "leapdrama_locale";
const THEME_KEY = "leapdrama_theme";

interface PrefsContextValue {
  locale: Locale;
  toggleLocale: () => void;
  theme: Theme;
  toggleTheme: () => void;
  t: (en: string, zh: string) => string;
}

const PrefsContext = createContext<PrefsContextValue>({
  locale: "en",
  toggleLocale: () => undefined,
  theme: "dark",
  toggleTheme: () => undefined,
  t: (en) => en,
});

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() =>
    localStorage.getItem(LOCALE_KEY) === "zh" ? "zh" : "en",
  );
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark",
  );

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    localStorage.setItem(LOCALE_KEY, locale);
  }, [locale]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const toggleLocale = () => setLocale((prev) => (prev === "zh" ? "en" : "zh"));
  const toggleTheme = () => setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  const t = (en: string, zh: string) => (locale === "zh" ? zh : en);

  return (
    <PrefsContext.Provider value={{ locale, toggleLocale, theme, toggleTheme, t }}>
      {children}
    </PrefsContext.Provider>
  );
}

export function usePrefs() {
  return useContext(PrefsContext);
}

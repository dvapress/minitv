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
  theme: "light",
  toggleTheme: () => undefined,
  t: (en) => en,
});

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() =>
    localStorage.getItem(LOCALE_KEY) === "zh" ? "zh" : "en",
  );
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light",
  );

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    localStorage.setItem(LOCALE_KEY, locale);
  }, [locale]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === LOCALE_KEY && (e.newValue === "en" || e.newValue === "zh")) {
        setLocale(e.newValue);
      }
      if (e.key === THEME_KEY && (e.newValue === "light" || e.newValue === "dark")) {
        setTheme(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

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

const DRAMA_TITLES_EN: Record<string, string> = {
  "全家听我心声觉醒了，我躺赢": "My Family Hears My Thoughts",
  "孝子贤孙都跪下，我是你们太奶奶": "Bow Down, Great-Grandma's Back",
  "爹爹开门我带剧本来救全家了": "Open Up, Daddy! I Brought the Script",
  "穿成三个反派儿子的锦鲤娘": "Lucky Mother of Three Villains",
  "穿到八零家属院，老公又红温啦": "Blushing Husband in the 1980s",
  "选个纨绔当爹，养成皇帝就好了": "Raising My Playboy Dad Into an Emperor",
  "200斤的她绑定系统后美又飒": "Glow-Up System: Bold & Unstoppable",
  "小姑回娘家，带全村炫肉": "Boss Auntie Returns Home",
  "白月光反击说明书": "First Love's Revenge Playbook",
  "穿书反派成团宠": "The Villainess Became the Favorite",
};

export function localizeDramaTitle(title: string, locale: Locale): string {
  if (locale === "zh") return title;
  return DRAMA_TITLES_EN[title] ?? title;
}

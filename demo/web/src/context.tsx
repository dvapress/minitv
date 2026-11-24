import { createContext, useContext } from "react";
import type { Locale } from "./i18n";
import type { Key } from "./i18n";
import type { User } from "./api";

export type AppContextValue = {
  t: (key: Key, vars?: Record<string, string | number>) => string;
  locale: Locale;
  setLocale: (locale: Locale) => void;
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
  region: string;
  setRegion: (region: string) => void;
  user: User | null;
  refreshUser: () => Promise<void>;
  go: (path: string) => void;
  path: string;
};

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("LeapDrama context missing");
  return value;
}

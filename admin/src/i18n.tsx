import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Button } from "antd";
import { GlobalOutlined } from "@ant-design/icons";
import { translateZhToEn } from "./i18nDict";

export type Locale = "en" | "zh";

/** Shared across Web (/site/), H5 (/), and Admin/Partner (/admin/) on the same origin. */
export const LOCALE_KEY = "leapdrama_locale";

export function getLocale(): Locale {
  if (typeof window === "undefined") return "en";
  return localStorage.getItem(LOCALE_KEY) === "zh" ? "zh" : "en";
}

export function tx(en: string, zh: string, locale: Locale = getLocale()): string {
  return locale === "zh" ? zh : en;
}

interface I18nContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  toggleLocale: () => void;
  t: (en: string, zh: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  locale: "en",
  setLocale: () => undefined,
  toggleLocale: () => undefined,
  t: (en) => en,
});

const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE", "TEXTAREA"]);
const TRANSLATABLE_ATTRS = ["placeholder", "title", "aria-label"] as const;

const originalTextMap = new WeakMap<Text, string>();
const translatedTextMap = new WeakMap<Text, string>();
const originalAttrMap = new WeakMap<Element, Partial<Record<(typeof TRANSLATABLE_ATTRS)[number], string>>>();

function applyTextNode(node: Text, locale: Locale) {
  const parent = node.parentElement;
  if (parent && SKIP_TAGS.has(parent.tagName)) return;

  const current = node.nodeValue ?? "";
  if (locale === "zh") {
    const orig = originalTextMap.get(node);
    if (orig !== undefined && current === translatedTextMap.get(node)) {
      node.nodeValue = orig;
    }
    return;
  }

  // locale === "en"
  const lastTranslated = translatedTextMap.get(node);
  if (lastTranslated !== undefined && current === lastTranslated) return;

  const source = current;
  const translated = translateZhToEn(source);
  if (translated && translated !== source) {
    originalTextMap.set(node, source);
    translatedTextMap.set(node, translated);
    node.nodeValue = translated;
  }
}

function applyElementAttrs(el: Element, locale: Locale) {
  if (SKIP_TAGS.has(el.tagName)) return;
  for (const attr of TRANSLATABLE_ATTRS) {
    const current = el.getAttribute(attr);
    if (current == null) continue;
    let saved = originalAttrMap.get(el);
    if (locale === "zh") {
      if (saved && saved[attr] !== undefined && current !== saved[attr]) {
        el.setAttribute(attr, saved[attr]!);
      }
      continue;
    }
    const translated = translateZhToEn(current);
    if (translated && translated !== current) {
      if (!saved) {
        saved = {};
        originalAttrMap.set(el, saved);
      }
      if (saved[attr] === undefined) saved[attr] = current;
      el.setAttribute(attr, translated);
    }
  }
}

function walkTree(root: Node, locale: Locale) {
  if (root.nodeType === Node.TEXT_NODE) {
    applyTextNode(root as Text, locale);
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const el = root as Element;
  if (SKIP_TAGS.has(el.tagName)) return;
  applyElementAttrs(el, locale);

  const walker = document.createTreeWalker(el, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  let node: Node | null = walker.nextNode();
  while (node) {
    if (node.nodeType === Node.TEXT_NODE) {
      applyTextNode(node as Text, locale);
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      applyElementAttrs(node as Element, locale);
    }
    node = walker.nextNode();
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getLocale);

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    localStorage.setItem(LOCALE_KEY, locale);
  }, [locale]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === LOCALE_KEY && (e.newValue === "en" || e.newValue === "zh")) {
        setLocaleState(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  // Zero-DOM-mutation translation bridge for legacy Chinese pages & AntD portals.
  useEffect(() => {
    if (typeof document === "undefined") return;
    walkTree(document.body, locale);
    if (locale !== "en") return;

    let rafId = 0;
    const pending = new Set<Node>();
    const flush = () => {
      rafId = 0;
      pending.forEach((node) => walkTree(node, "en"));
      pending.clear();
    };

    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.type === "characterData") {
          pending.add(m.target);
        } else if (m.type === "attributes") {
          pending.add(m.target);
        } else if (m.type === "childList") {
          m.addedNodes.forEach((n) => pending.add(n));
        }
      }
      if (!rafId && pending.size > 0) {
        rafId = requestAnimationFrame(flush);
      }
    });

    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: [...TRANSLATABLE_ATTRS],
    });

    return () => {
      observer.disconnect();
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
  }, []);

  const toggleLocale = useCallback(() => {
    setLocaleState((prev) => (prev === "zh" ? "en" : "zh"));
  }, []);

  const t = useCallback((en: string, zh: string) => (locale === "zh" ? zh : en), [locale]);

  return (
    <I18nContext.Provider value={{ locale, setLocale, toggleLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}

export function LocaleSwitchButton({ size = "small" }: { size?: "small" | "middle" | "large" }) {
  const { locale, toggleLocale, t } = useI18n();
  return (
    <Button
      type="default"
      size={size}
      icon={<GlobalOutlined />}
      onClick={toggleLocale}
      title={t("Switch to Chinese", "切换为英文")}
      aria-label={t("Switch to Chinese", "切换为英文")}
    >
      {locale === "zh" ? "EN" : "中文"}
    </Button>
  );
}

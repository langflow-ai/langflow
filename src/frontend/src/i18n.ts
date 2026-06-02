import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';

const localeLoaders: Record<
  string,
  () => Promise<{ default: Record<string, string> }>
> = {
  fr: () => import('./locales/fr.json'),
  es: () => import('./locales/es.json'),
  de: () => import('./locales/de.json'),
  pt: () => import('./locales/pt.json'),
  ja: () => import('./locales/ja.json'),
  'zh-Hans': () => import('./locales/zh-Hans.json'),
};

const supportedLanguages = new Set(['en', ...Object.keys(localeLoaders)]);

export function normalizeLanguageCode(lang: string): string {
  const normalized = lang.toLowerCase();

  if (normalized.startsWith('zh')) {
    return 'zh-Hans';
  }

  return normalized.split('-')[0];
}

export function resolveLanguage(lang?: string | null): string {
  if (!lang) {
    return 'en';
  }

  const normalizedLang = normalizeLanguageCode(lang);

  return supportedLanguages.has(normalizedLang) ? normalizedLang : 'en';
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
  },
  lng: 'en',
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
});

export async function loadLanguage(lang: string): Promise<void> {
  const resolvedLang = resolveLanguage(lang);

  if (resolvedLang === 'en') return;
  if (i18n.hasResourceBundle(resolvedLang, 'translation')) return;

  const localeLoader = localeLoaders[resolvedLang];

  if (!localeLoader) {
    return;
  }

  const messages = await localeLoader();
  i18n.addResourceBundle(resolvedLang, 'translation', messages.default);
}

export default i18n;


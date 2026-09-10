import english from '../locales/en.json';
import hungarian from '../locales/hu.json';

export const locales = {
  en: english,
  hu: hungarian
} as const;

export type Locale = keyof typeof locales;
export type Translation = (typeof locales)[Locale];

export function getTranslations(locale: Locale): Translation {
  return locales[locale];
}

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

// English only for now. `locales/second.json` is the empty file for the
// pilot language, which is not decided yet (D02). When it is: rename the file
// to the language code, register it under `resources`, and add its Noto Sans
// script font. Missing keys fall back to English.
void i18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false }, // React already escapes output
});

export default i18n;

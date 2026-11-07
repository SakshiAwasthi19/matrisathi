/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  /** "development" when unset; the environment banner hides only for "production". */
  readonly VITE_ENV_LABEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

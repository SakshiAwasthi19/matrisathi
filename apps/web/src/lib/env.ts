/** Normalises VITE_ENV_LABEL. Unset means local development. */
export function envLabel(raw: string | undefined): string {
  const value = (raw ?? "").trim().toLowerCase();
  return value === "" ? "development" : value;
}

/** The environment banner shows on every page unless this is production. */
export function shouldShowEnvBanner(label: string): boolean {
  return label !== "production";
}

export const ENV_LABEL = envLabel(import.meta.env.VITE_ENV_LABEL);

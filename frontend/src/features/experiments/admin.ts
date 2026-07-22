const STORAGE_KEY = "experiment_admin_secret";
const GROQ_KEY_STORAGE_KEY = "experiment_admin_groq_api_key";
const EVENT_NAME = "experiment-admin-changed";

export function getExperimentAdminSecret(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(STORAGE_KEY);
}

export function isExperimentAdminUnlocked(): boolean {
  return !!getExperimentAdminSecret();
}

export function getExperimentGroqApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(GROQ_KEY_STORAGE_KEY);
}

export function setExperimentAdminSession(secret: string, groqApiKey?: string | null): void {
  window.sessionStorage.setItem(STORAGE_KEY, secret);
  const normalizedKey = groqApiKey?.trim() ?? "";
  if (normalizedKey) {
    window.sessionStorage.setItem(GROQ_KEY_STORAGE_KEY, normalizedKey);
  } else {
    window.sessionStorage.removeItem(GROQ_KEY_STORAGE_KEY);
  }
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function clearExperimentAdminSecret(): void {
  window.sessionStorage.removeItem(STORAGE_KEY);
  window.sessionStorage.removeItem(GROQ_KEY_STORAGE_KEY);
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function subscribeExperimentAdmin(listener: () => void): () => void {
  window.addEventListener(EVENT_NAME, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(EVENT_NAME, listener);
    window.removeEventListener("storage", listener);
  };
}

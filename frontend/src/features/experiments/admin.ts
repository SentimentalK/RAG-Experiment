const STORAGE_KEY = "experiment_admin_secret";
const EVENT_NAME = "experiment-admin-changed";

export function getExperimentAdminSecret(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(STORAGE_KEY);
}

export function isExperimentAdminUnlocked(): boolean {
  return !!getExperimentAdminSecret();
}

export function setExperimentAdminSecret(secret: string): void {
  window.sessionStorage.setItem(STORAGE_KEY, secret);
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function clearExperimentAdminSecret(): void {
  window.sessionStorage.removeItem(STORAGE_KEY);
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


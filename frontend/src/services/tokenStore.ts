/**
 * In-memory token store.
 * Strictly avoids persisting tokens or credentials to localStorage or sessionStorage
 * to mitigate cross-site scripting (XSS) exfiltration risks.
 */

type TokenListener = (token: string | null) => void;

let inMemoryToken: string | null = null;
let listeners: TokenListener[] = [];

export const tokenStore = {
  getToken(): string | null {
    return inMemoryToken;
  },

  setToken(token: string | null): void {
    inMemoryToken = token ? token.trim() : null;
    listeners.forEach((listener) => {
      try {
        listener(inMemoryToken);
      } catch (err) {
        console.error('Error in token change listener:', err);
      }
    });
  },

  clearToken(): void {
    this.setToken(null);
  },

  subscribe(listener: TokenListener): () => void {
    listeners.push(listener);
    return () => {
      listeners = listeners.filter((l) => l !== listener);
    };
  },
};

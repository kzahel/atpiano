/// <reference types="astro/client" />

interface Window {
  turnstile?: {
    reset: (widgetId?: string | HTMLElement) => void;
  };
}

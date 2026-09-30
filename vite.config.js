import { defineConfig } from 'vite';

// The wall tablet runs Android WebView 106 — keep JS + CSS output within Chromium 106.
export default defineConfig({
  build: {
    target: 'chrome106',
    cssTarget: 'chrome106',
  },
  server: { host: true },
});

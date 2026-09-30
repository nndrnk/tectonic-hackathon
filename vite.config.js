import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/** Injecte la directive CSP de styles adaptée au mode Vite. */
function cspModePlugin() {
  let productionBuild = false;

  return {
    name: "trustlens-csp-mode",
    configResolved(config) {
      productionBuild = config.isProduction;
    },
    transformIndexHtml(html) {
      const stylesDirective = productionBuild ? "" : "'unsafe-inline'";
      const hmrDirective = productionBuild ? "" : "ws://127.0.0.1:5173";
      return html
        .replace("__TRUSTLENS_STYLE_CSP__", stylesDirective)
        .replace("__TRUSTLENS_HMR_CSP__", hmrDirective);
    },
  };
}

export default defineConfig({
  plugins: [react(), cspModePlugin()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/testSetup.js"],
    restoreMocks: true,
    clearMocks: true,
    include: ["src/**/*.test.{js,jsx}"],
  },
});

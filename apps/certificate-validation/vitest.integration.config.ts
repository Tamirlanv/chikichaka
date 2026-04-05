import { defineConfig } from "vitest/config";

/** Same as default vitest config, but integration tests are not excluded. */
export default defineConfig({
  test: {
    globals: true,
    exclude: ["**/node_modules/**", "**/dist/**"],
  },
});

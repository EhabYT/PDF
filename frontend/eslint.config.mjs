import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const config = [
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    ignores: [
      ".next/**",
      "out/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      "coverage/**",
      "next-env.d.ts",
      "tsconfig.tsbuildinfo"
    ]
  },
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": ["warn", { "argsIgnorePattern": "^_", "varsIgnorePattern": "^_" }],
      // Private scan previews are authenticated, user-specific bytes. They are
      // rendered with <img> on purpose; Next's shared image optimizer/cache is
      // not used for private document content.
      "@next/next/no-img-element": "off",
      // The current data-fetching shell intentionally synchronizes server state
      // in effects. Keep this visible as a warning while the app is migrated to
      // a dedicated query/cache layer.
      "react-hooks/set-state-in-effect": "warn"
    }
  },
  {
    files: ["tests/**", "**/*.test.ts", "**/*.test.tsx", "playwright.config.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off"
    }
  }
];

export default config;

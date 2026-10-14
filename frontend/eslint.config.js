import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/shared/api/schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.strict, jsxA11y.flatConfigs.recommended],
    languageOptions: { ecmaVersion: 2023, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "dangerouslySetInnerHTML est interdit (CSP, D-sécurité).",
        },
        {
          selector: "JSXAttribute[name.name='style']",
          message:
            "Attribut style interdit : la CSP (style-src 'self') le bloque. Utiliser une classe CSS.",
        },
      ],
      "no-restricted-globals": [
        "error",
        {
          name: "localStorage",
          message: "Stockage navigateur interdit, sauf src/vote/draft.ts (D039).",
        },
        {
          name: "sessionStorage",
          message: "Stockage navigateur interdit, sauf src/vote/draft.ts (D039).",
        },
      ],
      "no-restricted-properties": [
        "error",
        {
          object: "window",
          property: "localStorage",
          message: "Stockage navigateur interdit, sauf src/vote/draft.ts (D039).",
        },
        {
          object: "window",
          property: "sessionStorage",
          message: "Stockage navigateur interdit (D039).",
        },
      ],
    },
  },
  {
    // D039: the voter's local draft is the ONLY use of browser storage.
    files: ["src/vote/draft.ts", "src/vote/draft.test.ts"],
    rules: { "no-restricted-globals": "off", "no-restricted-properties": "off" },
  },
);

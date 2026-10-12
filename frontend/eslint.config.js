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
      ],
      "no-restricted-globals": [
        "error",
        { name: "localStorage", message: "Aucune donnée d'authentification en stockage local." },
        { name: "sessionStorage", message: "Aucune donnée d'authentification en stockage local." },
      ],
    },
  },
);

import eslint from "@eslint/js";
import globals from "globals";
import vue from "eslint-plugin-vue";
import tseslint from "typescript-eslint";
import vueParser from "vue-eslint-parser";

export default [
  {
    ignores: [
      "**/node_modules/**",
      "**/logs/**",
      "**/*.log",
      "**/npm-debug.log*",
      "**/yarn-debug.log*",
      "**/yarn-error.log*",
      "**/pnpm-debug.log*",
      "**/lerna-debug.log*",
      "**/.DS_Store",
      "**/dist/**",
      "**/dist-ssr/**",
      "**/coverage/**",
      "**/*.local",
      "**/.vscode/**",
      "**/.idea/**",
      "**/*.suo",
      "**/*.ntvs*",
      "**/*.njsproj",
      "**/*.sln",
      "**/*.sw?",
      "**/test-results/**",
      "**/playwright-report/**",
      "**/blob-report/**",
      "**/playwright/.cache/**",
    ],
  },
  eslint.configs.recommended,
  ...vue.configs["flat/recommended"],
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{js,jsx,cjs,mjs,ts,tsx,cts,mts}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
      },
    },
    rules: {
      "vue/multi-word-component-names": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "no-unused-vars": "off",
    },
  },
  {
    files: ["**/*.vue"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parser: vueParser,
      parserOptions: {
        ecmaVersion: "latest",
        parser: tseslint.parser,
        sourceType: "module",
      },
    },
    rules: {
      "vue/multi-word-component-names": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "no-unused-vars": "off",
    },
  },
];

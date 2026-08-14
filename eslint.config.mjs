// Next.js 16 flat config — FlatCompat lazım deyil.
import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescriptConfig from "eslint-config-next/typescript";

const eslintConfig = [
  ...coreWebVitals,
  ...typescriptConfig,
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      "src/generated/**", // Prisma-nın generasiya etdiyi kod
    ],
  },
  {
    // Tip elanlarında namespace istifadəsi qaçılmazdır (JSX augmentation).
    files: ["**/*.d.ts"],
    rules: { "@typescript-eslint/no-namespace": "off" },
  },
];

export default eslintConfig;

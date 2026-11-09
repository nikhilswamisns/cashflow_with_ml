import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'
import prettier from 'eslint-config-prettier'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { globals: globals.browser },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      // features talk to each other through their public files only; shared never imports a feature
      'no-restricted-imports': ['error', { patterns: [{ group: ['../*'], message: 'Use the @/ alias for cross-folder imports.' }] }],
    },
  },
  {
    files: ['src/shared/**/*.{ts,tsx}'],
    rules: { 'no-restricted-imports': ['error', { patterns: [{ group: ['@/features/*', '@/app/*'], message: 'shared/ must not import from features/ or app/.' }, { group: ['../*'], message: 'Use the @/ alias.' }] }] },
  },
  { files: ['**/*.test.{ts,tsx}'], languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  prettier,
)

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,vue}'],
      exclude: ['src/**/*.d.ts', 'src/**/*.{test,spec}.{ts,tsx}'],
      reporter: ['text', 'json-summary', 'lcov', 'html'],
      reportsDirectory: './coverage',
      // Línea base global: statements 56,12; branches 50,14; functions 43,77;
      // lines 57,37. Todos los umbrales se redondean hacia abajo.
      // `autoUpdate` debe permanecer desactivado para que el gate no baje solo.
      thresholds: {
        global: {
          statements: 56,
          branches: 50,
          functions: 43,
          lines: 57
        },
        autoUpdate: false
      }
    }
  },
  server: {
    host: '0.0.0.0',
    port: 8080,
    watch: {
      ignored: ['**/coverage/**', '**/playwright-report/**', '**/test-results/**']
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})

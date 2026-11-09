import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './shared/styles/index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './app/App'
// Chart text is measured on first draw, so load both fonts first (otherwise the "$" on axes gets clipped).
const fonts = Promise.all([
  document.fonts.load('500 12px "Geist Mono Variable"'),
  document.fonts.load('400 12px "Geist Mono Variable"'),
  document.fonts.load('500 14px "Geist Variable"'),
  document.fonts.load('650 14px "Geist Variable"'),
]).catch(() => {})

void fonts.then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})

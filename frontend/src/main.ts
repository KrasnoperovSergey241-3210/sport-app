import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

const url = new URL(location.href)
if (url.searchParams.has('demo')) {
  url.searchParams.delete('demo')
  history.replaceState(history.state, '', url)
}

createApp(App).mount('#app')

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js').catch(console.warn)
  })
}

<script setup lang="ts">
defineProps<{ name: string; size?: number }>()

const paths: Record<string, string> = {
  pulse: 'M2 12h5l3-8 4 16 3-8h5',
  home: 'M3 10l9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z M9 21v-7h6v7',
  clipboard: 'M9 5H5v16h14V5h-4 M9 3h6v4H9z M8 12h8 M8 16h6',
  user: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0z',
  logOut: 'M10 17l5-5-5-5 M15 12H3 M16 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4',
  calendar: 'M8 3v4 M16 3v4 M4 9h16 M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1z M8 13h2 M14 13h2 M8 16h2',
  clock: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z M12 6v6l4 2',
  flag: 'M5 22V3 M5 4c4-4 7 4 14 0v10c-7 4-10-4-14 0',
  trend: 'M3 17l6-6 4 4 7-9 M15 6h5v5',
  shield: 'M12 22s7-3 7-10V5l-7-3-7 3v7c0 7 7 10 7 10z M9 12l2 2 4-4',
  check: 'M5 12l4 4L19 6',
  info: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z M12 11v5 M12 8h.01',
  alert: 'M10.3 4.4 2.5 18a1.5 1.5 0 0 0 1.3 2h16.4a1.5 1.5 0 0 0 1.3-2L13.7 4.4a2 2 0 0 0-3.4 0z M12 9v4 M12 16h.01',
  chevron: 'M9 18l6-6-6-6',
  x: 'M6 6l12 12 M18 6 6 18',
  sync: 'M21 4v6h-6 M3 20v-6h6 M4 10a8 8 0 0 1 14-5l3 5 M3 14l3 5a8 8 0 0 0 14-5',
  wifiOff: 'M2 2l20 20 M2 9a15 15 0 0 1 3-2 M10 5a16 16 0 0 1 12 4 M5 13a11 11 0 0 1 4-2 M15 11a11 11 0 0 1 4 2 M8 17a6 6 0 0 1 7-1 M12 20h.01',
}
</script>

<template>
  <svg v-if="paths[name]" :width="size || 20" :height="size || 20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="paths[name]" />
  </svg>
</template>

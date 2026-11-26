<script setup lang="ts">
import Icon from './Icon.vue'

defineProps<{ question: string; name: string; help?: string; noLabel?: string; yesLabel?: string }>()
const model = defineModel<unknown>()
</script>

<template>
  <fieldset class="question-row">
    <legend class="sr-only">{{ question }}</legend>
    <div class="question-copy"><span aria-hidden="true">{{ question }}</span>
      <details v-if="help" class="help-tip"><summary aria-label="Пояснение"><Icon name="info" :size="18" /></summary><div>{{ help }}</div></details>
    </div>
    <div class="binary">
      <label v-for="item in [{ value: true, label: yesLabel || 'Да' }, { value: false, label: noLabel || 'Нет' }]" :key="String(item.value)" class="option">
        <input v-model="model" type="radio" :name="name" :value="item.value" /><span>{{ item.label }}</span>
      </label>
    </div>
  </fieldset>
</template>

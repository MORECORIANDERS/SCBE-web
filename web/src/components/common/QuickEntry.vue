<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Component } from 'vue'

const props = defineProps<{
  icon: Component
  label: string
  path?: string
  action?: () => void
}>()

const router = useRouter()

const handleClick = () => {
  if (props.path) {
    router.push(props.path)
  } else if (props.action) {
    props.action()
  }
}
</script>

<template>
  <div class="quick-entry" @click="handleClick">
    <component :is="icon" class="entry-icon" />
    <span class="entry-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.quick-entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background-color: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-medium);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex: 1;
  min-width: 0;
}

.quick-entry:hover {
  border-color: var(--color-primary);
  background-color: var(--color-bg-secondary);
}

.entry-icon {
  font-size: 18px;
  line-height: 1;
  color: var(--color-text-secondary);
}

.quick-entry:hover .entry-icon {
  color: var(--color-primary);
}

.entry-label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  white-space: nowrap;
}

@media (max-width: 767px) {
  .quick-entry {
    padding: var(--spacing-sm);
  }

  .entry-icon {
    font-size: 14px;
  }

  .entry-label {
    font-size: 9px;
  }
}
</style>

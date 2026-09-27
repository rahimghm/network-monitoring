<script setup>
import { toasts } from '../toasts.js'
</script>

<template>
  <div class="toast-stack">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.kind">
      {{ t.message }}
    </div>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  top: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 1000;
}
.toast {
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  max-width: 320px;
}
.toast.alert { background: #fbe7e6; color: #a12a22; border: 1px solid #f0d0ce; }
.toast.info { background: var(--brand-green-soft); color: var(--brand-green-dark); border: 1px solid #b9ddc7; }
.toast.success { background: #e5f7e8; color: #218838; border: 1px solid #c7ecc9; }
</style>

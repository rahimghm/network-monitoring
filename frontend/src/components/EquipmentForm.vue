<script setup>
import { ref } from 'vue'

const emit = defineEmits(['created'])

const name = ref('')
const hostname = ref('')
const community = ref('public')
const submitting = ref(false)
const error = ref(null)

async function handleSubmit() {
  error.value = null
  if (!name.value.trim() || !hostname.value.trim()) {
    error.value = 'Le nom et le hostname sont requis.'
    return
  }
  submitting.value = true
  try {
    emit('created', {
      name: name.value.trim(),
      hostname: hostname.value.trim(),
      community: community.value.trim() || 'public'
    })
    name.value = ''
    hostname.value = ''
    community.value = 'public'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="equip-form" @submit.prevent="handleSubmit">
    <h2>Ajouter un équipement</h2>

    <div class="field">
      <label for="name">Nom</label>
      <input id="name" v-model="name" type="text" placeholder="ex: Switch Étage 2" />
    </div>

    <div class="field">
      <label for="hostname">Hostname</label>
      <input id="hostname" v-model="hostname" type="text" placeholder="ex: switch1.local ou 192.168.2.132" />
    </div>

    <div class="field">
      <label for="community">Communauté SNMP</label>
      <input id="community" v-model="community" type="text" placeholder="public" />
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <button type="submit" :disabled="submitting">
      {{ submitting ? 'Ajout...' : 'Ajouter' }}
    </button>
  </form>
</template>

<style scoped>
.equip-form {
  background: #fff;
  border: 1px solid #e2e5ea;
  border-radius: 10px;
  padding: 20px;
  max-width: 360px;
}
.equip-form h2 {
  font-size: 16px;
  margin: 0 0 16px;
  color: #1a1d23;
}
.field {
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
label {
  font-size: 13px;
  color: #555;
  font-weight: 600;
}
input {
  padding: 8px 10px;
  border: 1px solid #d5d9e0;
  border-radius: 6px;
  font-size: 14px;
}
input:focus {
  outline: none;
  border-color: #3b6fed;
}
button {
  width: 100%;
  padding: 9px;
  background: #3b6fed;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error {
  color: #d1453b;
  font-size: 13px;
  margin: 0 0 10px;
}
</style>

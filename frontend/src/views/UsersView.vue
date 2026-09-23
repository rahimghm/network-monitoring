<script setup>
import { ref, onMounted } from 'vue'
import { createUser, deleteUser, listUsers, updateUser } from '../api.js'
import { pushToast } from '../toasts.js'

const users = ref([])
const loading = ref(false)
const newUser = ref({ username: '', password: '', role: 'technician' })
const editingId = ref(null)
const editForm = ref({ role: 'technician', password: '' })

async function refresh() {
  loading.value = true
  try {
    users.value = await listUsers()
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Impossible de charger les comptes.', 'alert')
  } finally {
    loading.value = false
  }
}

async function addUser() {
  try {
    await createUser(newUser.value)
    newUser.value = { username: '', password: '', role: 'technician' }
    await refresh()
    pushToast('Compte créé.', 'success')
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Échec de la création du compte.', 'alert')
  }
}

function startEditing(user) {
  editingId.value = user.id
  editForm.value = { role: user.role, password: '' }
}

function cancelEditing() {
  editingId.value = null
}

async function saveUser(user) {
  const payload = { role: editForm.value.role }
  if (editForm.value.password) payload.password = editForm.value.password

  try {
    await updateUser(user.id, payload)
    editingId.value = null
    await refresh()
    pushToast('Compte modifié.', 'success')
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Échec de la modification.', 'alert')
  }
}

async function removeUser(user) {
  if (!window.confirm(`Supprimer le compte « ${user.username} » ?`)) return
  try {
    await deleteUser(user.id)
    await refresh()
    pushToast('Compte supprimé.', 'success')
  } catch (error) {
    pushToast(error.response?.data?.detail || 'Échec de la suppression.', 'alert')
  }
}

function formatDate(value) {
  return new Date(value).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

onMounted(refresh)
</script>

<template>
  <div class="users-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Administration</p>
        <h2>Gestion des comptes</h2>
      </div>
      <span class="count">{{ users.length }} compte{{ users.length > 1 ? 's' : '' }}</span>
    </div>

    <form class="create-panel" @submit.prevent="addUser">
      <h3>Créer un compte</h3>
      <div class="form-row">
        <label>Nom d'utilisateur <input v-model.trim="newUser.username" type="text" minlength="3" maxlength="50" required /></label>
        <label>Mot de passe <input v-model="newUser.password" type="password" minlength="6" required /></label>
        <label>Rôle
          <select v-model="newUser.role">
            <option value="admin">Administrateur</option>
            <option value="technician">Technicien</option>
            <option value="supervisor">Superviseur</option>
          </select>
        </label>
        <button type="submit">Créer le compte</button>
      </div>
    </form>

    <section class="users-panel">
      <div class="panel-heading">
        <h3>Comptes existants</h3>
        <span v-if="loading" class="muted">Chargement...</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Utilisateur</th><th>Rôle</th><th>Créé le</th><th class="actions-column">Actions</th></tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td class="username">{{ user.username }}</td>
              <td v-if="editingId !== user.id"><span class="role-label" :class="user.role">{{ user.role }}</span></td>
              <td v-else>
                <select v-model="editForm.role">
                  <option value="admin">Administrateur</option>
                  <option value="technician">Technicien</option>
                  <option value="supervisor">Superviseur</option>
                </select>
              </td>
              <td>{{ formatDate(user.created_at) }}</td>
              <td class="actions">
                <template v-if="editingId === user.id">
                  <input v-model="editForm.password" type="password" minlength="6" placeholder="Nouveau mot de passe" />
                  <button class="save-btn" @click="saveUser(user)">Enregistrer</button>
                  <button class="quiet-btn" @click="cancelEditing">Annuler</button>
                </template>
                <template v-else>
                  <button class="quiet-btn" @click="startEditing(user)">Modifier</button>
                  <button class="delete-btn" @click="removeUser(user)">Supprimer</button>
                </template>
              </td>
            </tr>
            <tr v-if="!loading && !users.length"><td colspan="4" class="empty">Aucun compte trouvé.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.users-page { color: #1a1d23; }
.page-heading, .panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-heading { margin-bottom: 20px; }
.eyebrow { margin: 0 0 4px; color: #3b6fed; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
h2 { margin: 0; font-size: 22px; }
h3 { margin: 0 0 14px; font-size: 15px; }
.count, .muted { color: #777f8d; font-size: 13px; }
.create-panel, .users-panel { background: #fff; border: 1px solid #e2e5ea; border-radius: 10px; padding: 18px; margin-bottom: 20px; }
.form-row { display: grid; grid-template-columns: 1.2fr 1.2fr 1fr auto; align-items: end; gap: 12px; }
label { display: grid; gap: 6px; color: #656d79; font-size: 12px; font-weight: 600; }
input, select { width: 100%; padding: 8px 10px; border: 1px solid #d5d9e0; border-radius: 6px; background: #fff; color: #1a1d23; font: inherit; font-size: 13px; }
button { padding: 8px 12px; border-radius: 6px; border: 0; font-size: 12px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.form-row button, .save-btn { background: #3b6fed; color: #fff; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { padding: 9px 8px; border-bottom: 1px solid #e2e5ea; color: #858b95; font-size: 11px; font-weight: 700; text-align: left; text-transform: uppercase; }
td { padding: 11px 8px; border-bottom: 1px solid #f0f1f4; vertical-align: middle; }
.username { font-weight: 600; }
.role-label { display: inline-block; padding: 4px 8px; border-radius: 12px; background: #eef2fe; color: #3b6fed; font-size: 11px; text-transform: capitalize; }
.role-label.admin { background: #fff1df; color: #a76111; }
.role-label.supervisor { background: #e7f6ef; color: #23734b; }
.actions-column { width: 330px; }
.actions { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.actions input { width: 150px; }
.quiet-btn { border: 1px solid #d5d9e0; background: #fff; color: #5f6671; }
.delete-btn { border: 1px solid #f0d0ce; background: #fff; color: #c24138; }
.empty { padding: 24px; color: #858b95; text-align: center; }
@media (max-width: 850px) {
  .form-row { grid-template-columns: 1fr 1fr; }
  .form-row button { width: max-content; }
  .actions-column { width: auto; }
  .actions { justify-content: flex-start; flex-wrap: wrap; }
}
</style>
import { useEffect, useState } from 'react'
import { listUsers, createUser } from '../api'

export default function UserPicker({ userId, onSelectUser }) {
  const [users, setUsers] = useState([])
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    listUsers().then(setUsers).catch(() => {})
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    try {
      const user = await createUser(newName.trim())
      setUsers((prev) => [...prev, user])
      onSelectUser(user.id)
      setNewName('')
    } finally {
      setCreating(false)
    }
  }

  return (
    <section className="card">
      <h2>User</h2>
      <div className="user-picker-row">
        <select
          value={userId ?? ''}
          onChange={(e) => onSelectUser(Number(e.target.value))}
        >
          <option value="" disabled>
            Select a user…
          </option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name}
            </option>
          ))}
        </select>
        <form onSubmit={handleCreate} className="user-picker-new">
          <input
            type="text"
            placeholder="New user name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button type="submit" disabled={creating}>
            Add user
          </button>
        </form>
      </div>
    </section>
  )
}

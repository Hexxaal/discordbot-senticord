export async function fetchSettings(id) {
  const res = await fetch(`/api/guilds/${id}/settings`, { credentials:'include' });
  return res.json();
}

export async function saveSettings(id, data) {
  const res = await fetch(`/api/guilds/${id}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data)
  });
  return res.json();
}

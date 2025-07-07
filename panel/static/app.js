(async function(){
  const form = document.getElementById('settings-form');
  // extract guildId from URL: /guilds/:id
  const match = location.pathname.match(/\/guilds\/(\d+)/);
  if (!match) { document.body.innerHTML = '<p>Invalid path</p>'; return; }
  const guildId = match[1];

  // fetch and populate
  const res = await fetch(`/api/guilds/${guildId}/settings`, { credentials: 'include' });
  if (res.ok) {
    const cfg = await res.json();
    document.getElementById('adminRole').value = cfg.admin_role || '';
    document.getElementById('logChannel').value = cfg.log_channel || '';
  } else {
    alert('Failed to load settings: '+res.status);
  }

  // save handler
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {
      admin_role: document.getElementById('adminRole').value,
      log_channel: document.getElementById('logChannel').value
    };
    const save = await fetch(`/api/guilds/${guildId}/settings`, {
      method: 'POST',
      credentials: 'include',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    if (save.ok) alert('Settings saved!');
    else alert('Save failed: '+save.status);
  });
})();

import React, { useState, useEffect } from 'react';
import { fetchSettings, saveSettings } from '../api/guild';

export default function CaptchaConfigForm({ guildId }) {
  const [cfg, setCfg] = useState({ pendingRole:'', verifiedRole:'', timeout:20 });

  useEffect(() => {
    fetchSettings(guildId).then(data => setCfg(data));
  }, [guildId]);

  function onSubmit(e) {
    e.preventDefault();
    saveSettings(guildId, cfg);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 p-4">
      <div>
        <label>Pending Role ID:</label>
        <input
          className="border p-2 w-full"
          value={cfg.pendingRole}
          onChange={e => setCfg({ ...cfg, pendingRole: e.target.value })}
        />
      </div>
      <div>
        <label>Verified Role ID:</label>
        <input
          className="border p-2 w-full"
          value={cfg.verifiedRole}
          onChange={e => setCfg({ ...cfg, verifiedRole: e.target.value })}
        />
      </div>
      <div>
        <label>Timeout (min):</label>
        <input
          type="number"
          className="border p-2 w-full"
          value={cfg.timeout}
          onChange={e => setCfg({ ...cfg, timeout: +e.target.value })}
        />
      </div>
      <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">
        Save
      </button>
    </form>
  );
}

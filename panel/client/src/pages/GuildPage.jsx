import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import TabPane from '../components/TabPane';
import CaptchaConfigForm from '../components/CaptchaConfigForm';

const tabs = ['Internet','Captcha','Logs','Commands'];

export default function GuildPage() {
  const { id } = useParams();
  const [tab, setTab] = useState(tabs[0]);

  return (
    <div className="p-6">
      <h1 className="text-2xl mb-4">Guild Settings ({id})</h1>
      <TabPane tabs={tabs} active={tab} onChange={setTab} />
      <div className="mt-6">
        {tab==='Captcha' && <CaptchaConfigForm guildId={id} />}
        {tab==='Internet' && <p>🔗 Link whitelist coming soon.</p>}
        {tab==='Logs' && <p>📝 Moderation logs coming soon.</p>}
        {tab==='Commands' && <p>⚙️ Command toggles coming soon.</p>}
      </div>
    </div>
  );
}

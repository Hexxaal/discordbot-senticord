import React from 'react';

export default function TabPane({ tabs, active, onChange }) {
  return (
    <div className="flex border-b">
      {tabs.map(tab => (
        <button
          key={tab}
          className={`px-4 py-2 ${active === tab ? 'border-b-2 font-bold' : ''}`}
          onClick={() => onChange(tab)}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

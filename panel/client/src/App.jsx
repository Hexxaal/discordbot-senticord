import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import GuildPage from './pages/GuildPage';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/guilds/:id" element={<GuildPage />} />
      </Routes>
    </BrowserRouter>
  );
}

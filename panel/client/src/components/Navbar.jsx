import React from 'react';
import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="p-4 bg-gray-800 text-white">
      <Link to="/">Senticord Panel</Link>
    </nav>
  );
}

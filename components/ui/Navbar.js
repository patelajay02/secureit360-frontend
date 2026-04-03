// components/ui/Navbar.js
// SecureIT360 — Shared navigation bar
// Shows on all authenticated pages

"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { logout, getUser } from "../../lib/auth";

export function Navbar() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const user = getUser();

  // Don't show on login/signup pages
  const hideNav = pathname === "/login" || 
                  pathname === "/signup" || 
                  pathname === "/";
  if (hideNav) return null;

  const navLinks = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/settings", label: "Settings" },
  ];

  return (
    <nav className="bg-gray-900 border-b border-gray-800 sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">

          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-2">
            <span className="text-xl font-bold text-white">
              SecureIT<span className="text-indigo-400">360</span>
            </span>
          </Link>

          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-colors ${
                  pathname === link.href
                    ? "text-indigo-400"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* Desktop right side */}
          <div className="hidden md:flex items-center gap-4">
            {user && (
              <span className="text-gray-500 text-sm">{user.email}</span>
            )}
            <button
              onClick={logout}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Log out
            </button>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden text-gray-400 hover:text-white p-2"
          >
            {menuOpen ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                   strokeWidth="2" className="w-6 h-6">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                   strokeWidth="2" className="w-6 h-6">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden border-t border-gray-800 py-4 space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className={`block px-4 py-2 rounded-lg text-sm font-medium ${
                  pathname === link.href
                    ? "bg-indigo-900/40 text-indigo-400"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            ))}
            <div className="px-4 pt-2 border-t border-gray-800">
              {user && (
                <p className="text-gray-500 text-xs mb-2">{user.email}</p>
              )}
              <button
                onClick={logout}
                className="text-sm text-red-400 hover:text-red-300"
              >
                Log out
              </button>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
// components/ui/BottomNav.js
// SecureIT360 — Mobile bottom navigation bar
// Only shows on mobile screens

"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

const navItems = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: (active) => (
      <svg viewBox="0 0 24 24" fill={active ? "currentColor" : "none"}
        stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    label: "Scans",
    href: "/dashboard/scanning",
    icon: (active) => (
      <svg viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
    ),
  },
  {
    label: "Settings",
    href: "/settings",
    icon: (active) => (
      <svg viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
      </svg>
    ),
  },
  {
    label: "Support",
    href: "mailto:support@secureit360.co",
    icon: (active) => (
      <svg viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" className="w-6 h-6">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
];

export function BottomNav() {
  const pathname = usePathname();

  // Only show on dashboard and settings pages
  const showNav = pathname?.startsWith("/dashboard") || 
                  pathname?.startsWith("/settings");

  if (!showNav) return null;

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 
                    flex md:hidden z-40 pb-safe">
      {navItems.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex-1 flex flex-col items-center justify-center py-3 gap-1 
                       transition-colors ${
                         active
                           ? "text-indigo-400"
                           : "text-gray-500 hover:text-gray-300"
                       }`}
          >
            {item.icon(active)}
            <span className="text-xs font-medium">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
// components/ui/SessionTimeout.js
// SecureIT360 — Session timeout warning
// Shows popup 2 minutes before JWT expires

"use client";

import { useState, useEffect } from "react";
import { getToken, decodeToken, clearToken } from "../../lib/auth";

export function SessionTimeout() {
  const [showWarning, setShowWarning] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(120);

  useEffect(() => {
    const interval = setInterval(() => {
      const token = getToken();
      if (!token) return;

      const decoded = decodeToken(token);
      if (!decoded || !decoded.exp) return;

      const secondsUntilExpiry = decoded.exp - Date.now() / 1000;

      if (secondsUntilExpiry <= 120 && secondsUntilExpiry > 0) {
        setShowWarning(true);
        setSecondsLeft(Math.ceil(secondsUntilExpiry));
      } else if (secondsUntilExpiry <= 0) {
        clearToken();
        window.location.href = "/login";
      } else {
        setShowWarning(false);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  async function handleStayLoggedIn() {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/auth/refresh`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${getToken()}`,
            "Content-Type": "application/json",
          },
        }
      );
      const data = await response.json();
      if (data.access_token) {
        localStorage.setItem("secureit360_token", data.access_token);
        setShowWarning(false);
      }
    } catch {
      clearToken();
      window.location.href = "/login";
    }
  }

  function handleLogout() {
    clearToken();
    window.location.href = "/login";
  }

  if (!showWarning) return null;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
      <div className="bg-gray-900 rounded-2xl p-8 w-full max-w-md border border-amber-700">
        <div className="text-center">
          <div className="text-4xl mb-4">⏱️</div>
          <h3 className="text-white font-semibold text-lg mb-2">
            Your session is about to expire
          </h3>
          <p className="text-gray-400 text-sm mb-2">
            You will be logged out in{" "}
            <span className="text-amber-400 font-bold text-lg">
              {secondsLeft}
            </span>{" "}
            seconds
          </p>
          <p className="text-gray-500 text-xs mb-6">
            Any unsaved changes will be lost
          </p>

          <div className="flex gap-3">
            <button
              onClick={handleStayLoggedIn}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-3 rounded-lg"
            >
              Stay logged in
            </button>
            <button
              onClick={handleLogout}
              className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-lg"
            >
              Log out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
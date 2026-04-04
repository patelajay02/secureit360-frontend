// components/ui/PageTitle.js
// SecureIT360 — Page title component
// Sets browser tab title for every page

"use client";

import { useEffect } from "react";

export function PageTitle({ title }) {
  useEffect(() => {
    document.title = title
      ? `${title} — SecureIT360`
      : "SecureIT360 — Complete Cyber Protection";
  }, [title]);

  return null;
}
// components/MfaGuard.tsx
// SecureIT360 — global client route guard for the mandatory-MFA gate. Mounted
// once in the root layout. When a gate ("enroll" | "challenge") is active it
// blocks navigation to protected pages and redirects to the correct MFA step.
// Purely a UX guard — the backend (require_platform_admin) is the hard enforcer.

"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getToken, getMfaGate } from "../lib/auth";
import { gateRedirectTarget } from "../lib/mfaGate";

export default function MfaGuard() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getToken()) return;            // not logged in → nothing to gate
    const gate = getMfaGate();
    if (!gate) return;                  // no active gate → allow
    const target = gateRedirectTarget(gate, pathname || "");
    if (target && target !== pathname) {
      router.replace(target);
    }
  }, [pathname, router]);

  return null;
}

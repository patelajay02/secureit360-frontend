// lib/supabaseClient.js
// SecureIT360 — browser Supabase client used ONLY for native MFA (TOTP) and
// AAL2 step-up. The primary auth flow stays on the FastAPI backend; this client
// is hydrated from the backend-issued Supabase session tokens.
//
// SAFETY:
//  - Uses the ANON (publishable) key only. The service-role key is NEVER shipped
//    to the browser.
//  - Returns null when env vars are absent so every caller degrades gracefully:
//    existing password-only login keeps working with no MFA UI.
//  - persistSession:false — we do not want a second competing session store in
//    localStorage; the backend JWT remains the source of truth for API calls.
//    We hydrate the client on demand via setSession() for MFA operations.

import { createClient } from "@supabase/supabase-js";
import { classifyClientConfig } from "./mfaEnroll";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let _client = null;

export function getSupabase() {
  if (typeof window === "undefined") return null; // client-only
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return null; // graceful no-MFA fallback
  if (_client) return _client;
  _client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
  });
  return _client;
}

export function isMfaConfigured() {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}

// Specific configuration state: "ok" | "no-env" | "ssr". Lets callers report an
// honest reason instead of a generic null (only "no-env" is truly "unavailable").
export function mfaClientStatus() {
  return classifyClientConfig(SUPABASE_URL, SUPABASE_ANON_KEY, typeof window !== "undefined");
}

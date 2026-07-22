"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AuthConfirm() {
  const router = useRouter();

  useEffect(() => {
    async function activate() {
      try {
        const hash = window.location.hash;
        const params = new URLSearchParams(hash.replace("#", "?"));
        const accessToken = params.get("access_token");

        if (!accessToken) {
          router.push("/login");
          return;
        }

        // The backend derives the user from the verified access token (Bearer),
        // never from the request body - so we send the token, not a user_id.
        await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/verify-email`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });

        router.push("/login?verified=true");
      } catch (err) {
        router.push("/login");
      }
    }

    activate();
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-white mb-4">
          SecureIT<span className="text-red-500">360</span>
        </h1>
        <p className="text-gray-400">Activating your account...</p>
      </div>
    </div>
  );
}

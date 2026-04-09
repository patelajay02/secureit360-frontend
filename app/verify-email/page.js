"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function VerifyEmailContent() {
  const params = useSearchParams();
  const email = params.get("email") || "your email address";

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <h1 className="text-3xl font-bold text-white mb-2">
          SecureIT<span className="text-red-500">360</span>
        </h1>
        <p className="text-gray-400 mb-8">by Global Cyber Assurance</p>
        <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
          <div className="text-5xl mb-6">??</div>
          <h2 className="text-xl font-semibold text-white mb-4">Check your email</h2>
          <p className="text-gray-400 mb-4">
            We have sent a verification link to:
          </p>
          <p className="text-white font-semibold mb-6">{email}</p>
          <p className="text-gray-400 text-sm mb-6">
            Please click the link in the email to verify your account and activate your 7-day free trial.
          </p>
          <p className="text-gray-500 text-xs">
            Did not receive it? Check your spam folder or contact us at{" "}
            <a href="mailto:governance@secureit360.co" className="text-red-400 hover:text-red-300">
              governance@secureit360.co
            </a>
          </p>
        </div>
        <p className="text-gray-500 text-sm mt-6">
          Already verified?{" "}
          <a href="/login" className="text-red-400 hover:text-red-300">
            Log in here
          </a>
        </p>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailContent />
    </Suspense>
  );
}

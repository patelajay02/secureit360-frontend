// app/layout.js
// SecureIT360 — Root layout

import "./globals.css";
import { ToastProvider } from "../components/ui/Toast";
import { Navbar } from "../components/ui/Navbar";
import { BottomNav } from "../components/ui/BottomNav";
import { SessionTimeout } from "../components/ui/SessionTimeout";
import { TrialBanner } from "../components/ui/TrialBanner";

export const metadata = {
  title: "SecureIT360 — Complete Cyber Protection",
  description:
    "Complete cyber protection for NZ and AU small businesses. Monitored daily. Fixed automatically. By Global Cyber Assurance.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white min-h-screen">
        <ToastProvider>
          <Navbar />
          <TrialBanner />
          <main className="pb-20 md:pb-0">
            {children}
          </main>
          <BottomNav />
          <SessionTimeout />
        </ToastProvider>
      </body>
    </html>
  );
}
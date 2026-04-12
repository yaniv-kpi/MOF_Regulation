import type { Metadata, Viewport } from "next";
import "./globals.css";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "חיפוש תקנות | מאגר הרגולציה הישראלית",
  description:
    "מנוע חיפוש מלא-טקסט למסמכי תקנות, חוקים ונהלים ישראליים מתוך gov.il",
  keywords: ["תקנות", "חוקים", "ישראל", "רגולציה", "gov.il", "קודקס"],
  openGraph: {
    title: "חיפוש תקנות ישראליות",
    description: "חפש תקנות, חוקים ומסמכי רגולציה ישראליים",
    locale: "he_IL",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0f172a" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 antialiased">
        <Header />
        <main className="min-h-[calc(100vh-64px)]">{children}</main>
        <footer className="border-t border-slate-200 dark:border-slate-800 py-6 mt-12">
          <div className="max-w-6xl mx-auto px-4 text-center text-sm text-slate-400 dark:text-slate-600" dir="rtl">
            מקור נתונים:{" "}
            <a
              href="https://www.gov.il/he/pages/information-entities-codex"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-brand-500 transition-colors underline underline-offset-2"
            >
              פורטל שירותי הממשלה — gov.il
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}

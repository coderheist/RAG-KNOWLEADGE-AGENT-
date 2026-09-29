import type { Metadata } from "next";
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { AppProvider } from "@/lib/context/app-context";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

// "optional": use Geist if it is ready almost immediately (cached, fast network), otherwise keep the
// metric-matched fallback. With "swap" the late repaint became the LCP on slow mobile connections.
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "optional",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "optional",
});

// Answers are reading material, so they are set in a text serif; the interface stays in Geist.
const reading = Source_Serif_4({
  variable: "--font-reading",
  subsets: ["latin"],
  display: "optional",
});

export const metadata: Metadata = {
  title: "RAG Agent",
  description: "Ask questions about your documents and check every answer against its sources",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${reading.variable} font-sans antialiased`}
      >
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <AppProvider>
            {children}
            <Toaster richColors closeButton />
          </AppProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

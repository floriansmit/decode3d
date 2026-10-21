import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DECODE Geothermal Explorer",
  description: "Explore the DECODE regional geological model and first-pass geothermal reservoir maps.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}

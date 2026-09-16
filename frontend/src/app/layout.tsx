import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "DevLens AI — Understand Any Codebase in 15 Minutes",
    template: "%s | DevLens AI",
  },
  description:
    "DevLens AI builds an Engineering Knowledge Graph from your GitHub repository, enabling grounded AI chat, feature tracing, architecture visualization, and health reports. Understand any codebase in 15 minutes.",
  keywords: ["code analysis", "AI", "codebase understanding", "knowledge graph", "developer tools"],
  authors: [{ name: "DevLens AI" }],
  openGraph: {
    title: "DevLens AI",
    description: "Understand any codebase in 15 minutes.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <div className="mesh-bg" />
        {children}
      </body>
    </html>
  );
}

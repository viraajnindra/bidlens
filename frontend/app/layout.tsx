import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "BidLens — Read the requirements. See the consequences.",
  description:
    "Evidence-first government bid qualification and amendment impact analysis.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

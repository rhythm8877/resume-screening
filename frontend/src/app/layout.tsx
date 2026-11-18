import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Shortlist | Resume Review",
  description: "Review candidate applications against a job description and check the project links they provide.",
  icons: {
    icon: "/shortlist-mark.svg",
    shortcut: "/shortlist-mark.svg",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

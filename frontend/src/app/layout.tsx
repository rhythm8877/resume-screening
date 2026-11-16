import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Resume Screening",
  description: "Evidence-led resume review for a job role",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

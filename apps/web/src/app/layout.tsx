import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "CIVITWIN AI | Bajaur Planning Sandbox",
  description: "Audit-ready modeling for synthetic public service accessibility in Bajaur.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <html lang="en"><body><Shell>{children}</Shell></body></html>;
}

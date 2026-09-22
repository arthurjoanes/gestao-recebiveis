import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const productFont = localFont({
  src: [
    { path: "./fonts/plex-sans-regular.woff2", weight: "400", style: "normal" },
    {
      path: "./fonts/plex-sans-semibold.woff2",
      weight: "600",
      style: "normal",
    },
  ],
  variable: "--font-product",
  display: "swap",
  fallback: ["Arial"],
});

export const metadata: Metadata = {
  title: "Gestão de recebíveis · Contas a receber",
  description: "Contas a receber, importação CSV e lembretes simulados.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" className={productFont.variable}>
      <body>{children}</body>
    </html>
  );
}

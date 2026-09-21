import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gestão de recebíveis · Contas a receber",
  description: "Contas a receber, importação CSV e lembretes simulados.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}

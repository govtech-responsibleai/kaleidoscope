import type { Metadata } from "next";
import { Lato } from "next/font/google";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v14-appRouter";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { theme } from "@/lib/theme";
import Navigation from "@/components/Navigation";
import AuthCheck from "@/app/login/AuthCheck";
import "./globals.css";

const lato = Lato({ subsets: ["latin"], variable: "--font-lato", display: "swap", weight: ["400", "700"] });

export const metadata: Metadata = {
  title: "Kaleidoscope - LLM Evaluation Platform",
  description: "Evaluate your LLM applications with ease",
  icons: {
    icon: "/icon.png",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={lato.variable}>
      <body>
        <AppRouterCacheProvider>
          <ThemeProvider theme={theme}>
            <CssBaseline />
            <AuthCheck>
              <Navigation>{children}</Navigation>
            </AuthCheck>
          </ThemeProvider>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}

export const dynamic = "force-dynamic"
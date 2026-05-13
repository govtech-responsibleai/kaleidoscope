import type { Metadata } from "next";
import { Lato, JetBrains_Mono } from "next/font/google";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v14-appRouter";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { theme } from "@/lib/theme";
import Navigation from "@/components/Navigation";
import AuthCheck from "@/app/login/AuthCheck";
import "./globals.css";

const lato = Lato({ subsets: ["latin"], variable: "--font-lato", display: "swap", weight: ["400", "700"] });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains-mono", display: "swap", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "Kaleidoscope - AI evaluation, human aligned",
  description: "A structured workflow for realistic and scalable contextual AI evaluations.",
  icons: {
    icon: "/icon.png",
  },
  openGraph: {
    title: "Kaleidoscope - AI evaluation, human aligned",
    description: "A structured workflow for realistic and scalable contextual AI evaluations.",
    images: [
      {
        url: "/kaleidoscope-preview.png",
        width: 1755,
        height: 242,
        alt: "Project Kaleidoscope powered by GovTech Singapore",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Kaleidoscope - AI evaluation, human aligned",
    description: "A structured workflow for realistic and scalable contextual AI evaluations.",
    images: ["/kaleidoscope-preview.png"],
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${lato.variable} ${jetbrainsMono.variable}`}>
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

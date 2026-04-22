"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Box, CircularProgress } from "@mui/material";
import { authApi } from "@/lib/api";

interface AuthCheckProps {
  children: React.ReactNode;
}

export default function AuthCheck({ children }: AuthCheckProps) {
  const router = useRouter();
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";
  const isLoggedIn = authApi.isLoggedIn();

  useEffect(() => {
    if (!isLoginPage && !isLoggedIn) {
      router.replace("/login");
    }
  }, [isLoggedIn, isLoginPage, router]);

  // Show loading while checking auth (except on login page)
  if (!isLoginPage && !isLoggedIn) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return <>{children}</>;
}

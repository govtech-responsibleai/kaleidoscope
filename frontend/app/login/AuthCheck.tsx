"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Box, CircularProgress } from "@mui/material";
import { authApi } from "@/lib/api";

interface AuthCheckProps {
  children: React.ReactNode;
}

export default function AuthCheck({ children }: AuthCheckProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // Skip auth check on login page
    if (pathname === "/login") {
      setChecking(false);
      return;
    }

    if (!authApi.isLoggedIn()) {
      router.replace("/login");
    } else {
      setChecking(false);
    }
  }, [pathname, router]);

  // Show loading while checking auth (except on login page)
  if (checking && pathname !== "/login") {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return <>{children}</>;
}

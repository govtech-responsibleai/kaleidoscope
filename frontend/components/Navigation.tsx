"use client";

import React, { useState, useEffect } from "react";
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Box,
  Typography,
  IconButton,
  Divider,
} from "@mui/material";
import {
  DashboardCustomizeOutlined as DashboardIcon,
  ChevronLeft as ChevronLeftIcon,
  Logout as LogoutIcon,
} from "@mui/icons-material";
import { useRouter, usePathname } from "next/navigation";
import Image from "next/image";
import { APP_NAME } from "@/lib/constants";
import { authApi } from "@/lib/api";

const DRAWER_WIDTH_OPEN = 240;
const DRAWER_WIDTH_CLOSED = 64;

interface NavigationProps {
  children: React.ReactNode;
}

export default function Navigation({ children }: NavigationProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(true);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    setUsername(authApi.getUsername());
  }, [pathname]);

  const handleSignOut = () => {
    authApi.logout();
    setUsername(null);
    router.push("/login");
  };

  const menuItems = [
    { label: "Targets", icon: <DashboardIcon />, path: "/" },
  ];

  const drawerWidth = open ? DRAWER_WIDTH_OPEN : DRAWER_WIDTH_CLOSED;

  // Don't show navigation on login page
  if (pathname === "/login") {
    return <>{children}</>;
  }

  return (
    <Box sx={{ display: "flex" }}>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          whiteSpace: "nowrap",
          transition: (theme) =>
            theme.transitions.create("width", {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
          "& .MuiDrawer-paper": {
            width: drawerWidth,
            boxSizing: "border-box",
            backgroundColor: "rgb(0, 0, 0, 0.05)",
            overflowX: "hidden",
            overflowY: "hidden",
            border: "none",
            display: "flex",
            flexDirection: "column",
            transition: (theme) =>
              theme.transitions.create("width", {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
          },
        }}
      >
        <Toolbar
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: open ? "space-between" : "center",
            px: open ? 1 : 1,
          }}
        >
          {open ? (
            <>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                <Image src="/icon.png" alt="Kaleidoscope Logo" width={28} height={28} unoptimized />
                <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
                  {APP_NAME}
                </Typography>
              </Box>
              <IconButton disableRipple onClick={() => setOpen(!open)}>
                <ChevronLeftIcon />
              </IconButton>
            </>
          ) : (
            <IconButton onClick={() => setOpen(!open)} size="small">
              <Image src="/icon.png" alt="Kaleidoscope Logo" width={28} height={28} unoptimized />
            </IconButton>
          )}
        </Toolbar>
        <Box sx={{ overflow: "hidden", flexGrow: 1 }}>
          <List>
            {menuItems.map((item) => (
              <ListItem key={item.path} disablePadding sx={{ display: "block" }}>
                <ListItemButton
                  selected={pathname === item.path || pathname.startsWith("/targets")}
                  onClick={() => router.push(item.path)}
                  sx={{
                    minHeight: 48,
                    justifyContent: open ? "initial" : "center",
                    px: 2.5,
                    "&.Mui-selected": {
                      backgroundColor: "white",
                    },
                    "&.Mui-selected:hover": {
                      backgroundColor: "white",
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 0,
                      mr: open ? 1 : "auto",
                      justifyContent: "center",
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={item.label}
                    sx={{ opacity: open ? 1 : 0 }}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>

        {/* User status at bottom */}
        <Box sx={{ mt: "auto" }}>
          <Divider />
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: open ? "space-between" : "center",
              p: 2,
            }}
          >
            {open && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ overflow: "hidden", textOverflow: "ellipsis" }}
              >
                {username}
              </Typography>
            )}
            <IconButton
              onClick={handleSignOut}
              size="small"
              title="Sign out"
            >
              <LogoutIcon />
            </IconButton>
          </Box>
        </Box>
      </Drawer>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: `calc(100% - ${drawerWidth}px)`,
          minHeight: "100vh",
          transition: (theme) =>
            theme.transitions.create(["width", "margin"], {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
        }}
      >
        {children}
      </Box>
    </Box>
  );
}

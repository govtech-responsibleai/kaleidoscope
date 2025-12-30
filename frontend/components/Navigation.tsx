"use client";

import React, { useState } from "react";
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
} from "@mui/material";
import {
  DashboardCustomizeOutlined as DashboardIcon,
  ChevronLeft as ChevronLeftIcon,
} from "@mui/icons-material";
import { useRouter, usePathname } from "next/navigation";
import Image from "next/image";
import { APP_NAME } from "@/lib/constants";

const DRAWER_WIDTH_OPEN = 240;
const DRAWER_WIDTH_CLOSED = 64;

interface NavigationProps {
  children: React.ReactNode;
}

export default function Navigation({ children }: NavigationProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(true);

  const menuItems = [
    { label: "Targets", icon: <DashboardIcon />, path: "/" },
  ];

  const drawerWidth = open ? DRAWER_WIDTH_OPEN : DRAWER_WIDTH_CLOSED;

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
        <Box sx={{ overflow: "hidden" }}>
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

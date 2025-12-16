"use client";

import React from "react";
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
} from "@mui/material";
import {
  Home as HomeIcon,
} from "@mui/icons-material";
import { useRouter, usePathname } from "next/navigation";
import { APP_NAME } from "@/lib/constants";

const DRAWER_WIDTH = 240;

interface NavigationProps {
  children: React.ReactNode;
}

export default function Navigation({ children }: NavigationProps) {
  const router = useRouter();
  const pathname = usePathname();

  const menuItems = [
    { label: "Targets", icon: <HomeIcon />, path: "/" },
  ];

  return (
    <Box sx={{ display: "flex" }}>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
            backgroundColor: "#f5f5f5",
          },
        }}
      >
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
            {APP_NAME}
          </Typography>
        </Toolbar>
        <Box sx={{ overflow: "auto" }}>
          <List>
            {menuItems.map((item) => (
              <ListItem key={item.path} disablePadding>
                <ListItemButton
                  selected={pathname === item.path}
                  onClick={() => router.push(item.path)}
                >
                  <ListItemIcon>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.label} />
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
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          minHeight: "100vh",
        }}
      >
        <Toolbar sx={{minHeight: "4% !important"}}/>
        {children}
      </Box>
    </Box>
  );
}

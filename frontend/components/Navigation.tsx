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
  IconButton,
  Divider,
} from "@mui/material";
import {
  IconChartLine,
  IconChevronLeft,
  IconHome2,
  IconLayoutDashboard,
  IconLogout,
  IconMessageQuestion,
  IconMessageChatbot,
  IconPlugConnected,
  IconRobotFace,
  IconShieldCog,
  IconTool,
} from "@tabler/icons-react";
import { useRouter, usePathname } from "next/navigation";
import Image from "next/image";
import { APP_NAME } from "@/lib/constants";
import { authApi } from "@/lib/api";
import { navIconProps } from "@/lib/styles";

const DRAWER_WIDTH_OPEN = 240;
const DRAWER_WIDTH_CLOSED = 64;

interface NavigationProps {
  children: React.ReactNode;
}

export default function Navigation({ children }: NavigationProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = React.useState(true);
  const username = authApi.getUsername();
  const isAdmin = authApi.isAdmin();

  const handleSignOut = () => {
    authApi.logout();
    router.push("/login");
  };

  const drawerWidth = open ? DRAWER_WIDTH_OPEN : DRAWER_WIDTH_CLOSED;

  // Detect target route
  const targetMatch = pathname.match(/^\/targets\/(\d+)/);
  const targetId = targetMatch ? targetMatch[1] : null;

  // Derive activeTab from pathname (same logic as layout)
  const getActiveTab = () => {
    if (pathname.includes("/annotation")) return "annotation";
    if (pathname.includes("/scoring")) return "scoring";
    if (pathname.includes("/report")) return "report";
    if (pathname.includes("/questions")) return "questions";
    if (pathname.includes("/rubrics")) return "rubrics";
    return "overview";
  };
  const activeTab = getActiveTab();

  const targetNavItems = [
    { label: "Overview", icon: <IconHome2 {...navIconProps} />, tab: "overview", path: `/targets/${targetId}` },
    { label: "Evaluation Set", icon: <IconMessageQuestion {...navIconProps} />, tab: "questions", path: `/targets/${targetId}/questions` },
    { label: "Annotations", icon: <IconMessageChatbot {...navIconProps} />, tab: "annotation", path: `/targets/${targetId}/annotation` },
    { label: "Scoring", icon: <IconRobotFace {...navIconProps} />, tab: "scoring", path: `/targets/${targetId}/scoring` },
    { label: "Report", icon: <IconChartLine {...navIconProps} />, tab: "report", path: `/targets/${targetId}/report` },
  ];

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
            backgroundColor: "#fff",
            borderRight: "1px solid rgba(0,0,0,0.12)",
            overflowX: "hidden",
            overflowY: "hidden",
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
                <IconChevronLeft {...navIconProps} />
              </IconButton>
            </>
          ) : (
            <IconButton onClick={() => setOpen(!open)} size="small">
              <Image src="/icon.png" alt="Kaleidoscope Logo" width={28} height={28} unoptimized />
            </IconButton>
          )}
        </Toolbar>

        <Box sx={{ overflow: "hidden", flexGrow: 1 }}>
          {targetId ? (
            <List>
              {/* Back to all targets */}
              <ListItem disablePadding sx={{ display: "block" }}>
                <ListItemButton
                  onClick={() => router.push("/")}
                  sx={{
                    minHeight: 48,
                    justifyContent: open ? "initial" : "center",
                    px: 2.5,
                  }}
                >
                  <ListItemIcon
                    sx={{ minWidth: 0, mr: open ? 1 : "auto", justifyContent: "center" }}
                  >
                    <IconChevronLeft {...navIconProps} />
                  </ListItemIcon>
                  <ListItemText primary="All Targets" sx={{ opacity: open ? 1 : 0 }} />
                </ListItemButton>
              </ListItem>

              {/* Target Information subheader */}
              {open && (
                <Box sx={{ px: 2.5, pt: 1.5, pb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
                    Target Information
                  </Typography>
                </Box>
              )}

              {/* Overview */}
              <ListItem disablePadding sx={{ display: "block" }}>
                <ListItemButton
                  selected={activeTab === "overview"}
                  onClick={() => router.push(`/targets/${targetId}`)}
                  sx={{
                    minHeight: 48,
                    justifyContent: open ? "initial" : "center",
                    px: 2.5,
                  }}
                >
                  <ListItemIcon
                    sx={{ minWidth: 0, mr: open ? 1 : "auto", justifyContent: "center" }}
                  >
                    <IconHome2 {...navIconProps} />
                  </ListItemIcon>
                  <ListItemText primary="Overview" sx={{ opacity: open ? 1 : 0 }} />
                </ListItemButton>
              </ListItem>

              {/* Rubrics */}
              <ListItem disablePadding sx={{ display: "block" }}>
                <ListItemButton
                  selected={activeTab === "rubrics"}
                  onClick={() => router.push(`/targets/${targetId}/rubrics`)}
                  sx={{
                    minHeight: 48,
                    justifyContent: open ? "initial" : "center",
                    px: 2.5,
                  }}
                >
                  <ListItemIcon
                    sx={{ minWidth: 0, mr: open ? 1 : "auto", justifyContent: "center" }}
                  >
                    <IconTool {...navIconProps} />
                  </ListItemIcon>
                  <ListItemText primary="Rubrics" sx={{ opacity: open ? 1 : 0 }} />
                </ListItemButton>
              </ListItem>

              {/* Run Evaluations subheader */}
              {open && (
                <Box sx={{ px: 2.5, pt: 1.5, pb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
                    Run Evaluations
                  </Typography>
                </Box>
              )}

              {/* Questions, Annotations, Scoring, Report */}
              {targetNavItems.slice(1).map((item) => (
                <ListItem key={item.tab} disablePadding sx={{ display: "block" }}>
                  <ListItemButton
                    selected={activeTab === item.tab}
                    onClick={() => router.push(item.path)}
                    sx={{
                      minHeight: 48,
                      justifyContent: open ? "initial" : "center",
                      px: 2.5,
                    }}
                  >
                    <ListItemIcon
                      sx={{ minWidth: 0, mr: open ? 1 : "auto", justifyContent: "center" }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText primary={item.label} sx={{ opacity: open ? 1 : 0 }} />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          ) : (
            <List>
              <ListItem disablePadding sx={{ display: "block" }}>
                <ListItemButton
                  selected={pathname === "/" || pathname.startsWith("/targets")}
                  onClick={() => router.push("/")}
                  sx={{
                    minHeight: 48,
                    justifyContent: open ? "initial" : "center",
                    px: 2.5,
                  }}
                >
                  <ListItemIcon
                    sx={{ minWidth: 0, mr: open ? 1 : "auto", justifyContent: "center" }}
                  >
                    <IconLayoutDashboard {...navIconProps} />
                  </ListItemIcon>
                  <ListItemText primary="Targets" sx={{ opacity: open ? 1 : 0 }} />
                </ListItemButton>
              </ListItem>
              <ListItem disablePadding sx={{ display: "block" }}>
                <ListItemButton
                  selected={pathname === "/providers"}
                  onClick={() => router.push("/providers")}
                  sx={{
                    minHeight: 48,
                    justifyContent: open ? "initial" : "center",
                    px: 2.5,
                  }}
                >
                  <ListItemIcon
                    sx={{ minWidth: 0, mr: open ? 1 : "auto", justifyContent: "center" }}
                  >
                    <IconPlugConnected {...navIconProps} />
                  </ListItemIcon>
                  <ListItemText primary="Providers" sx={{ opacity: open ? 1 : 0 }} />
                </ListItemButton>
              </ListItem>
              {isAdmin && (
                <>
                  <Divider sx={{ my: 1 }} />
                  {open && (
                    <Box sx={{ px: 2.5, pt: 0.5, pb: 0.5 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
                        Administration
                      </Typography>
                    </Box>
                  )}
                  <ListItem disablePadding sx={{ display: "block" }}>
                    <ListItemButton
                      selected={pathname === "/admin"}
                      onClick={() => router.push("/admin")}
                      sx={{
                        minHeight: 48,
                        justifyContent: open ? "initial" : "center",
                        px: 2.5,
                      }}
                    >
                      <ListItemIcon
                        sx={{ minWidth: 0, mr: open ? 1 : "auto", justifyContent: "center" }}
                      >
                        <IconShieldCog {...navIconProps} />
                      </ListItemIcon>
                      <ListItemText primary="Users" sx={{ opacity: open ? 1 : 0 }} />
                    </ListItemButton>
                  </ListItem>
                </>
              )}
            </List>
          )}
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
            <IconButton onClick={handleSignOut} size="small" title="Sign out">
              <IconLogout {...navIconProps} />
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

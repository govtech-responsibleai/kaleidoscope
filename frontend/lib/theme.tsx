"use client";

import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    primary: {
      main: "#1d2766",
    },
    secondary: {
      main: "#dc004e",
    },
  },
  typography: {
    fontFamily: [
      "-apple-system",
      "BlinkMacSystemFont",
      '"Segoe UI"',
      "Roboto",
      '"Helvetica Neue"',
      "Arial",
      "sans-serif",
    ].join(","),
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          boxShadow: "none",
          "&:hover": { boxShadow: "none" },
        },
      },
    },
    MuiFormControl: {
      styleOverrides: {
        root: {
          display: "flex",
          flexDirection: "column",
          alignItems: "stretch",
          gap: 4, // small spacing between stacked elements
        },
      },
    },
    MuiInputLabel: {
      defaultProps: { shrink: true }, // force the label out of the field
      styleOverrides: {
        root: {
          position: "relative",
          transform: "none",
          left: 0,
          top: 0,
          fontSize: "0.9rem",
          fontWeight: 600,
          marginBottom: 2,
        },
        shrink: { transform: "none" },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          // kill the notch so the top-left corner is solid again
          "& legend": { display: "none" },
          "& .MuiOutlinedInput-notchedOutline legend": { display: "none" },
          "& .MuiOutlinedInput-notchedOutline": { padding: 0 },
        },
        input: {
          paddingTop: "10px" // optional, keeps spacing consistent once the notch is gone
        },
      },
    },
    MuiFormHelperText: {
      styleOverrides: {
        root: {
          order: 1, // sit right after the label
          margin: "0 0 4px",
        },
      },
    },
    MuiInputBase: {
      styleOverrides: {
        root: {
          order: 2,
        },
      },
    },
  },
});

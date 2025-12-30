"use client";

import { createTheme, alpha } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    primary: {
      main: "#1d2766", // rgb(29, 39, 102)
      light: "#4861b6" // rgb(72, 97, 182)
    },
    secondary: {
      main: "#dc004e", // rgb(220, 0, 78)
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
          borderRadius: 5,
          boxShadow: "none",
          "&:hover": { boxShadow: "none" },
          textTransform: "none",
          fontWeight: "bold"
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 5
        },
      },
      variants: [
        {
          props: { variant: "outlined" },
          style: {
            border: "1px solid rgb(180, 180, 180)",
            borderRadius: 5
          },
        },
      ],
    },

    // Form/TextField global styles
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
          borderRadius: 5,
        },
        input: {
          padding: "10px 15px",

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
    // Dropdown/Select global styles
    MuiSelect: {
      styleOverrides: {
        root: {
          borderRadius: 5,
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: "#1d2766",
            borderWidth: 2,
          },
        },
        select: {
          borderRadius: 5,
        },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          borderRadius: 5,
          marginTop: 4,
        },
        list: {
          padding: "8px",
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: 5,
          margin: "2px 0",
          padding: "10px 12px",
          "&:hover": {
            backgroundColor: alpha(theme.palette.primary.light, 0.05),
          },
          "&.Mui-selected": {
            backgroundColor: alpha(theme.palette.primary.light, 0.1),
            "&:hover": {
              backgroundColor: alpha(theme.palette.primary.light, 0.1),
            },
          },
          "&.Mui-focusVisible": {
            backgroundColor: alpha(theme.palette.primary.light, 0.05),
          },
        }),
      },
    },
    MuiAutocomplete: {
      styleOverrides: {
        paper: {
          borderRadius: 5,
          marginTop: 4, 
        },
        listbox: ({ theme }) => ({
          padding: "8px",
          "& .MuiAutocomplete-option": {
            borderRadius: 5,
            margin: "2px 0",
            padding: "10px 12px",
            "&:hover": {
              backgroundColor: alpha(theme.palette.primary.light, 0.05),
            },
            "&[aria-selected='true']": {
              backgroundColor: alpha(theme.palette.primary.light, 0.1),
              "&:hover": {
                backgroundColor: alpha(theme.palette.primary.light, 0.1),
              },
            },
            "&.Mui-focused": {
              backgroundColor: alpha(theme.palette.primary.light, 0.05),
            },
          },
        }),
        inputRoot: {
          borderRadius: 5,
        },
      },
    },
    MuiPopover: {
      styleOverrides: {
        paper: {
          borderRadius: 5,
        },
      },
    },
    MuiCheckbox: {
      styleOverrides: {
        root: {
          padding: "0 9px 0 0",
        },
      },
    },
    MuiListItemText: {
      styleOverrides: {
        primary: {
          fontSize: "0.875rem",
        },
      },
    },
  },
});

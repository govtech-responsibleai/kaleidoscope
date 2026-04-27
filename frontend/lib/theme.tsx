"use client";

import { createTheme, alpha } from "@mui/material/styles";

export const sourceChip = {
  generated: { label: "AI",      bgcolor: "rgba(124, 77, 255, 0.1)", color: "#5C6BC0", borderColor: "rgba(124, 77, 255, 0.3)" },
  general:   { label: "General", bgcolor: "rgba(0, 191, 165, 0.1)", color: "#26A69A", borderColor: "rgba(0, 191, 165, 0.3)" },
};

export const getSourceChip = (source: string) => source === "generated" ? sourceChip.generated : sourceChip.general;

export const groupColors = {
  fixed:  { border: "#5C6BC0", bg: "#F5F5FF" },
  preset: { border: "#26A69A", bg: "#F0FBF9" },
  custom: { border: "#FFA726", bg: "#FFFBF0" },
};

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
    fontFamily: "var(--font-lato), sans-serif",
  },
  components: {
    MuiButtonBase: {
      defaultProps: { disableRipple: true },
    },
    MuiCssBaseline: {
      styleOverrides: {
        html: {
          // fontSize: "90%", // Scale down all rem-based values
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: "none",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 5,
          boxShadow: "none",
          "&:hover": { boxShadow: "none" },
          textTransform: "none",
          fontWeight: "bold",
          transition: "transform 0.1s ease-out",
          "&:active": {
            transform: "scale(0.97)",
            transition:  "transform 0.1s ease-in",
          },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          transition: "transform 0.1s ease-out",
          "&:active": {
            transform: "scale(0.97)",
            transition: "transform 0.1s ease-in",
          },
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          transition: "background-color 0ms",
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
    MuiTextField: {
      styleOverrides: {
        root: {
          // Hide the notch and remove the fieldset top offset (label is positioned outside via MuiInputLabel)
          "& .MuiOutlinedInput-notchedOutline legend": { display: "none" },
          "& .MuiOutlinedInput-notchedOutline": { top: 0 },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 5,
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
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 12,
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
    MuiDialogContent: {
      styleOverrides: {
        root: {
          paddingLeft: 24,
          paddingRight: 24,
          paddingTop: 20,
          paddingBottom: 20,
        },
      },
    },
    MuiDialogActions: {
      styleOverrides: {
        root: {
          paddingLeft: 24,
          paddingRight: 24,
          paddingTop: 16,
          paddingBottom: 16,
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
    MuiAccordion: {
      styleOverrides: {
        root: {
          "&:before": {
            display: "none"
          }
        },
        rounded: {
          borderRadius: 4,
        }
      }
    }
  },
});

import type { SxProps } from "@mui/material";
import { alpha, type Theme } from "@mui/material/styles";

export const navIconProps = {
  size: 19,
  stroke: 1.8,
};

export const sectionIconProps = {
  size: 20,
  stroke: 1.8,
};

export const statIconProps = {
  size: 20,
  stroke: 1.75,
};

export const actionIconProps = {
  size: 18,
  stroke: 1.9,
};

export const compactActionIconProps = {
  size: 16,
  stroke: 2,
};

export const statusIconProps = {
  size: 18,
  stroke: 2,
};

export const compactChipSx = {
  height: 22,
  fontSize: 11,
  fontWeight: 600,
} as const;

export const tableHeaderCellSx = {
  fontWeight: 600,
  fontSize: 11,
  letterSpacing: 0.2,
  textTransform: "none" as const,
  color: "text.secondary",
  py: 1.5,
  borderBottomColor: "grey.100",
} as const;

export const tableHeaderRowSx = {
  bgcolor: "transparent",
} as const;

export const compactActionButtonSx: SxProps<Theme> = {
  p: 0.35,
  borderRadius: 1,
  color: "text.secondary",
};

export const subtleActionButtonSx: SxProps<Theme> = {
  ...compactActionButtonSx,
  opacity: 0.45,
  "&:hover": {
    opacity: 1,
    bgcolor: "grey.100",
  },
};

export const tableContainerSx: SxProps<Theme> = {
  boxShadow: "none",
  borderRadius: 2,
  border: "1px solid",
  borderColor: "grey.200",
  overflow: "hidden",
};

export const getTableBodyRowSx = (theme: Theme): SxProps<Theme> => ({
  "& .MuiTableCell-root": {
    py: "16px !important",
    borderColor: "grey.100",
  },
  "&:hover": {
    bgcolor: alpha(theme.palette.primary.main, 0.03),
  },
});

export const tabsSx: SxProps<Theme> = {
  minHeight: 40,
  "& .MuiTabs-indicator": { height: 2 },
};

export const tabSx: SxProps<Theme> = {
  fontWeight: 600,
  textTransform: "none",
  letterSpacing: 0,
  minHeight: 40,
};

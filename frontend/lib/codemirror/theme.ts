import { EditorView } from "@codemirror/view";
import { alpha, type Theme } from "@mui/material/styles";

export const createPromptEditorTheme = (theme: Theme) => EditorView.theme({
  "&": {
    fontSize: "13px",
    fontFamily: "var(--font-jetbrains-mono), 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",
    borderRadius: `${theme.shape.borderRadius}px`,
    border: `1px solid ${alpha(theme.palette.text.primary, 0.23)}`,
    backgroundColor: alpha(theme.palette.primary.light, 0.04),
  },
  "&.cm-focused": {
    outline: "none",
    borderColor: theme.palette.primary.light,
    borderWidth: "2px",
    margin: "-1px",
  },
  ".cm-content": {
    padding: "12px 0",
    caretColor: theme.palette.primary.main,
  },
  ".cm-scroller": {
    overflow: "auto",
    minHeight: "200px",
  },
  ".cm-gutters": {
    backgroundColor: alpha(theme.palette.primary.light, 0.08),
    borderRight: `1px solid ${alpha(theme.palette.primary.light, 0.18)}`,
    color: theme.palette.text.secondary,
    borderRadius: `${theme.shape.borderRadius}px 0 0 ${theme.shape.borderRadius}px`,
  },
  ".cm-activeLineGutter": {
    backgroundColor: alpha(theme.palette.primary.light, 0.14),
    color: theme.palette.primary.main,
  },
  ".cm-activeLine": {
    backgroundColor: alpha(theme.palette.primary.main, 0.03),
  },
  ".cm-selectionBackground": {
    backgroundColor: `${alpha(theme.palette.primary.main, 0.08)} !important`,
  },
  "&.cm-focused .cm-selectionBackground": {
    backgroundColor: `${alpha(theme.palette.primary.light, 0.15)} !important`,
  },
  ".cm-cursor": {
    borderLeftColor: theme.palette.primary.main,
    borderLeftWidth: "2px",
  },
  ".cm-matchingBracket": {
    backgroundColor: alpha(theme.palette.primary.light, 0.2),
    outline: `1px solid ${alpha(theme.palette.primary.light, 0.4)}`,
  },
  ".cm-placeholder": {
    color: theme.palette.text.disabled,
    fontStyle: "italic",
  },
  ".cm-jinja2-variable": {
    backgroundColor: alpha(theme.palette.primary.light, 0.14),
    color: theme.palette.primary.main,
    borderRadius: "3px",
    padding: "1px 2px",
  },
  ".cm-jinja2-block": {
    backgroundColor: alpha(theme.palette.primary.main, 0.1),
    color: theme.palette.primary.main,
    borderRadius: "3px",
    padding: "1px 2px",
  },
});

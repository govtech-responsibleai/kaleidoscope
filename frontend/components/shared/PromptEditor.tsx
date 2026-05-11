"use client";

import React, { useEffect, useRef } from "react";
import { Box, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { Compartment, EditorState } from "@codemirror/state";
import { EditorView, lineNumbers, placeholder as cmPlaceholder } from "@codemirror/view";
import { bracketMatching } from "@codemirror/language";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { keymap } from "@codemirror/view";
import { jinja2Highlight } from "@/lib/codemirror/jinja2-highlight";
import { createPromptEditorTheme } from "@/lib/codemirror/theme";

interface PromptEditorProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  label?: string;
  helperText?: string;
}

export default function PromptEditor({
  value,
  onChange,
  disabled = false,
  placeholder = "",
  label,
  helperText,
}: PromptEditorProps) {
  const theme = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  const readOnlyCompartment = useRef(new Compartment());
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!containerRef.current) return;

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        onChangeRef.current(update.state.doc.toString());
      }
    });

    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        bracketMatching(),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        cmPlaceholder(placeholder),
        createPromptEditorTheme(theme),
        ...jinja2Highlight,
        updateListener,
        readOnlyCompartment.current.of(EditorState.readOnly.of(disabled)),
      ],
    });

    const view = new EditorView({ state, parent: containerRef.current });
    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const currentDoc = view.state.doc.toString();
    if (currentDoc !== value) {
      view.dispatch({
        changes: { from: 0, to: currentDoc.length, insert: value },
      });
    }
  }, [value]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({
      effects: readOnlyCompartment.current.reconfigure(
        EditorState.readOnly.of(disabled)
      ),
    });
  }, [disabled]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: "4px", flex: 1, minHeight: 0 }}>
      {label && (
        <Typography
          component="label"
          sx={{ fontSize: "0.9rem", fontWeight: 600, mb: "2px" }}
        >
          {label}
        </Typography>
      )}
      {helperText && (
        <Typography
          variant="caption"
          sx={{ color: "text.secondary", mb: "4px" }}
        >
          {helperText}
        </Typography>
      )}
      <Box
        ref={containerRef}
        sx={{
          flex: 1,
          minHeight: 0,
          opacity: disabled ? 0.5 : 1,
          pointerEvents: disabled ? "none" : "auto",
          transition: "opacity 0.2s",
          "& .cm-editor": { height: "100%" },
          "& .cm-scroller": { maxHeight: "none" },
        }}
      />
    </Box>
  );
}

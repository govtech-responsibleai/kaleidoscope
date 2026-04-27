"use client";

import Image from "next/image";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Divider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { IconChevronDown, IconLock, IconSearch, IconTrash } from "@tabler/icons-react";

import { ProviderCredentialFieldStatus, ProviderSetupEntry, ServiceCredentialSetup } from "@/lib/types";

interface ProviderRowProps {
  entry: ProviderSetupEntry | ServiceCredentialSetup;
  drafts: Record<string, string>;
  expanded: boolean;
  saving: boolean;
  isService?: boolean;
  onChange: (fieldKey: string, value: string) => void;
  onToggle: () => void;
  onSave: () => void;
  onDelete: () => void;
}

function getStatusDisplay(isValid: boolean, isReadOnly: boolean) {
  if (isReadOnly) return { color: "text.secondary", label: "Managed", managed: true };
  if (isValid) return { color: "success.main", label: "Configured", managed: false };
  return { color: "grey.400", label: "Not set", managed: false };
}

function hasConfiguredCredential(entry: ProviderSetupEntry | ServiceCredentialSetup) {
  return entry.credential_fields.some((f) => f.is_configured);
}

function renderLogo(entry: ProviderSetupEntry | ServiceCredentialSetup, isService: boolean) {
  if (isService || !("logo_path" in entry)) {
    return (
      <Box sx={{ alignItems: "center", bgcolor: "action.hover", borderRadius: 1.5, display: "flex", height: 32, justifyContent: "center", width: 32 }}>
        <IconSearch size={18} stroke={1.8} />
      </Box>
    );
  }
  return (
    <Box sx={{ alignItems: "center", border: "1px solid", borderColor: "divider", borderRadius: 1.5, display: "flex", height: 32, justifyContent: "center", overflow: "hidden", width: 32 }}>
      <Image src={entry.logo_path} alt={`${entry.display_name} logo`} width={32} height={32} style={{ objectFit: "contain", padding: 4 }} />
    </Box>
  );
}

function CredentialField({
  field,
  value,
  disabled,
  onChange,
  onDelete,
  showTrash,
}: {
  field: ProviderCredentialFieldStatus;
  value: string;
  disabled: boolean;
  onChange: (v: string) => void;
  onDelete?: () => void;
  showTrash?: boolean;
}) {
  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
        <Typography variant="body2" fontWeight={600} color="text.secondary">
          {field.label}{field.required ? " *" : ""}
        </Typography>
        {field.masked_value && !value && (
          <Typography
            variant="caption"
            sx={{
              bgcolor: "success.main",
              color: "white",
              borderRadius: "4px",
              px: 0.75,
              py: 0.1,
              fontWeight: 600,
              fontSize: "0.6rem",
              letterSpacing: "0.04em",
            }}
          >
            SAVED
          </Typography>
        )}
      </Stack>
      {field.masked_value && !value ? (
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography
            variant="body2"
            sx={{
              fontFamily: "monospace",
              bgcolor: "grey.100",
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              px: 1.25,
              py: 0.6,
              color: "text.secondary",
              flex: 1,
            }}
          >
            {field.masked_value}
          </Typography>
          {showTrash && onDelete && (
            <Box
              component="button"
              onClick={onDelete}
              disabled={disabled}
              sx={{
                background: "none",
                border: "none",
                cursor: disabled ? "default" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                p: 0.5,
                borderRadius: 1,
                color: "text.disabled",
                transition: "color 0.15s",
                "&:hover:not(:disabled)": { color: "error.main" },
              }}
            >
              <IconTrash size={16} stroke={1.6} />
            </Box>
          )}
        </Stack>
      ) : (
        <TextField
          disabled={disabled}
          fullWidth
          placeholder={`Enter ${field.label.toLowerCase()}`}
          type="password"
          value={value.trim() === "" ? "" : value}
          onChange={(e) => onChange(e.target.value)}
          size="small"
        />
      )}
    </Box>
  );
}

export default function ProviderRow({
  entry,
  drafts,
  expanded,
  saving,
  isService = false,
  onChange,
  onToggle,
  onSave,
  onDelete,
}: ProviderRowProps) {
  const hasCredential = hasConfiguredCredential(entry);
  const status = entry.is_read_only
    ? getStatusDisplay(entry.is_valid, entry.is_read_only)
    : entry.is_valid
      ? getStatusDisplay(true, false)
      : { color: hasCredential ? "error.main" : "grey.400", label: hasCredential ? "Error" : "Not set", managed: false };

  const provider = !isService ? (entry as ProviderSetupEntry) : null;
  const hasPersonalCredentials = entry.source === "personal" || entry.source === "personal_override";
  const hasDraft = entry.credential_fields.some((f) => drafts[f.key] && drafts[f.key].trim() !== "");

  return (
    <Accordion
      expanded={expanded}
      disableGutters
      onChange={onToggle}
      sx={{
        border: "1px solid",
        borderColor: expanded ? "primary.light" : "divider",
        borderRadius: "10px !important",
        boxShadow: expanded ? "0 0 0 3px rgba(72,97,182,0.08)" : "none",
        transition: "border-color 0.15s, box-shadow 0.15s",
        "&:before": { display: "none" },
      }}
    >
      <AccordionSummary expandIcon={null} sx={{ px: 2, py: 0.75 }}>
        <Stack alignItems="center" direction="row" justifyContent="space-between" spacing={2} sx={{ width: "100%" }}>
          <Stack alignItems="center" direction="row" spacing={1.5}>
            <Box sx={{ alignItems: "center", color: "text.disabled", display: "flex", transform: expanded ? "rotate(0deg)" : "rotate(-90deg)", transition: "transform 0.2s ease" }}>
              <IconChevronDown size={16} stroke={1.8} />
            </Box>
            {renderLogo(entry, isService)}
            <Typography fontWeight={600} variant="body1">{entry.display_name}</Typography>
          </Stack>

          {status.managed ? (
            <Stack alignItems="center" direction="row" spacing={0.75}>
              <IconLock size={14} stroke={1.8} color="var(--mui-palette-text-secondary)" />
              <Typography color="text.secondary" variant="body2">{status.label}</Typography>
            </Stack>
          ) : (
            <Stack alignItems="center" direction="row" spacing={1}>
              <Box sx={{ bgcolor: status.color, borderRadius: "999px", height: 8, width: 8 }} />
              <Typography color="text.secondary" variant="body2">{status.label}</Typography>
            </Stack>
          )}
        </Stack>
      </AccordionSummary>

      <AccordionDetails sx={{ px: 2, pb: 2, pt: 0 }}>
        <Divider sx={{ mb: 2 }} />

        {/* Credential fields */}
        <Stack spacing={2}>
          {entry.credential_fields.map((field, idx) => (
            <CredentialField
              key={field.key}
              field={field}
              value={drafts[field.key] || ""}
              disabled={entry.is_read_only || saving}
              onChange={(v) => onChange(field.key, v)}
              onDelete={onDelete}
              showTrash={hasPersonalCredentials && idx === entry.credential_fields.length - 1}
            />
          ))}
        </Stack>

        {/* Info area: description + models */}
        {(provider?.description || (provider && provider.common_models.length > 0) || provider?.key === "openrouter") && (
          <Box
            sx={{
              mt: 2,
              p: 1.5,
              bgcolor: "grey.50",
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1.5,
            }}
          >
            {provider?.description && (
              <Typography color="text.secondary" variant="body2" sx={{ mb: provider.common_models.length > 0 ? 1 : 0 }}>
                {provider.description}
              </Typography>
            )}
            {provider?.key === "openrouter" && !provider.description && (
              <Typography color="text.secondary" variant="body2" sx={{ mb: provider.common_models.length > 0 ? 1 : 0 }}>
                To use additional models, add them to <code>provider_catalog.yaml</code> and restart.
              </Typography>
            )}
            {provider && provider.common_models.length > 0 && (
              <>
                <Typography variant="caption" color="text.disabled" sx={{ display: "block", mb: 0.5, letterSpacing: "0.06em", textTransform: "uppercase", fontSize: "0.6rem" }}>
                  Registered models
                </Typography>
                <Stack spacing={0.25}>
                  {provider.common_models.map((model) => (
                    <Typography key={model} variant="body2" color="text.secondary" sx={{ fontFamily: "monospace", fontSize: "0.78rem" }}>
                      {model}
                    </Typography>
                  ))}
                </Stack>
              </>
            )}
          </Box>
        )}

        {/* Actions */}
        {!entry.is_read_only && hasDraft && (
          <Stack direction="row" justifyContent="flex-end" sx={{ mt: 2 }}>
            <Button
              variant="contained"
              disabled={saving}
              onClick={onSave}
              size="small"
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </Stack>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

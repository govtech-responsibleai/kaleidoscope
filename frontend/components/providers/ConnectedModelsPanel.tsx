"use client";

import type { ReactNode } from "react";
import Image from "next/image";
import { Box, Stack, Typography } from "@mui/material";

import { ProviderModelOption, ProviderServiceDefaults, ProviderSetupEntry } from "@/lib/types";

interface ConnectedModelsPanelProps {
  defaults: ProviderServiceDefaults;
  providers: ProviderSetupEntry[];
  validEmbeddingModels: ProviderModelOption[];
  validModels: ProviderModelOption[];
}

function findModel(
  modelName: string | null | undefined,
  allModels: ProviderModelOption[],
): ProviderModelOption | null {
  if (!modelName) return null;
  return allModels.find((m) => m.value === modelName) || null;
}

function LogoBadge({ alt, logoPath }: { alt: string; logoPath: string }) {
  return (
    <Box
      sx={{
        alignItems: "center",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        display: "flex",
        flexShrink: 0,
        height: 20,
        justifyContent: "center",
        overflow: "hidden",
        width: 20,
      }}
    >
      <Image src={logoPath} alt={alt} width={20} height={20} style={{ objectFit: "contain", padding: 2 }} />
    </Box>
  );
}

function ModelBadge({ model }: { model: ProviderModelOption | null }) {
  if (!model) {
    return <Typography color="text.secondary" variant="body2">Not set</Typography>;
  }
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <LogoBadge alt={`${model.provider_name} logo`} logoPath={model.logo_path} />
      <Typography variant="body2" sx={{ wordBreak: "break-all" }}>{model.value}</Typography>
    </Stack>
  );
}

function DefaultRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "30% 70%", alignItems: "start", gap: 1 }}>
      <Typography color="text.secondary" fontWeight={600} variant="body2" sx={{ pt: 0.25 }}>
        {label}
      </Typography>
      <Box>{children}</Box>
    </Box>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <Typography
      variant="overline"
      sx={{
        color: "text.disabled",
        fontSize: "0.65rem",
        letterSpacing: "0.1em",
        lineHeight: 1,
        display: "block",
      }}
    >
      {children}
    </Typography>
  );
}

export default function ConnectedModelsPanel({
  defaults,
  providers,
  validEmbeddingModels,
  validModels,
}: ConnectedModelsPanelProps) {
  if (validModels.length === 0) {
    return (
      <Box>
        <Typography fontWeight={600} variant="h6">Connected Models</Typography>
        <Typography color="text.secondary" fontStyle="italic" sx={{ display: "block", mb: 2 }} variant="caption">
          Live defaults and available models from your configured providers.
        </Typography>
        <Typography color="text.secondary" variant="body2">
          No models connected yet — add an API key on the left.
        </Typography>
      </Box>
    );
  }

  const allModels = [...validModels, ...validEmbeddingModels];
  const generationDefault = findModel(defaults.generation_default_model, allModels);
  const embeddingDefault = findModel(defaults.embedding_default_model, allModels);
  const judgeDefaults = providers
    .filter((p) => p.is_valid)
    .map((p) => findModel(p.default_model, allModels))
    .filter((m): m is ProviderModelOption => Boolean(m));
  const validProviders = providers.filter((p) => p.is_valid);

  const modelsByProvider = validModels.reduce<Map<string, ProviderModelOption[]>>((acc, model) => {
    const list = acc.get(model.provider_key) ?? [];
    list.push(model);
    acc.set(model.provider_key, list);
    return acc;
  }, new Map());

  return (
    <Box>
      <Typography fontWeight={600} variant="h6">Connected Models</Typography>
      <Typography color="text.secondary" fontStyle="italic" sx={{ display: "block", mb: 2.5 }} variant="caption">
        Live defaults and available models from your configured providers.
      </Typography>

      <SectionLabel>Live defaults</SectionLabel>

      {/* Live Defaults section */}
      <Box
        sx={{
          borderLeft: "3px solid",
          borderColor: "primary.main",
          borderRadius: "0 4px 4px 0",
          bgcolor: "rgba(29, 39, 102, 0.04)",
          px: 1.5,
          py: 1.25,
          mt: 1.25,
          mb: 3,
        }}
      >
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <DefaultRow label="Generation">
            <ModelBadge model={generationDefault} />
          </DefaultRow>
          <DefaultRow label="Embedding">
            <ModelBadge model={embeddingDefault} />
          </DefaultRow>
          <DefaultRow label="Judges">
            {judgeDefaults.length > 0 ? (
              <Stack spacing={1}>
                {judgeDefaults.map((model) => (
                  <ModelBadge key={model.value} model={model} />
                ))}
              </Stack>
            ) : (
              <Typography color="text.secondary" variant="body2">Not set</Typography>
            )}
          </DefaultRow>
          <DefaultRow label="Web search">
            <Typography variant="body2">
              {defaults.web_search_enabled ? "Enabled" : "Not set"}
            </Typography>
          </DefaultRow>
        <Typography color="text.disabled" sx={{ display: "block", mt: 2.5 }} variant="caption">
          Note: Each rubric uses its own recommended model first.
        </Typography>
        </Stack>
      </Box>
      

      {/* Available Models section */}
      <SectionLabel>All available models</SectionLabel>
      <Stack spacing={1.25} sx={{ mt: 1.25 }}>
        {validProviders.map((provider) => (
          <Stack key={provider.key} spacing={0.5}>
            <Stack alignItems="center" direction="row" spacing={1}>
              <LogoBadge alt={`${provider.display_name} logo`} logoPath={provider.logo_path} />
              <Typography fontWeight={600} variant="body2">{provider.display_name}</Typography>
            </Stack>
            <Stack spacing={0.25} sx={{ pl: 3.5 }}>
              {(modelsByProvider.get(provider.key) ?? []).map((model) => (
                <Typography key={model.value} color="text.secondary" variant="body2">
                  {model.value}
                </Typography>
              ))}
            </Stack>
          </Stack>
        ))}
      </Stack>

    </Box>
  );
}

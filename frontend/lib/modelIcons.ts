const MODEL_ICONS: Record<string, string> = {
  "gpt": "/icons/OpenAI-black-monoblossom.png",
  "claude": "/icons/Claude_AI_symbol.png",
  "gemini": "/icons/Google_Gemini_icon_2025.png",
};

export function getModelIcon(modelName: string): string | null {
  const lowerName = modelName.toLowerCase();
  for (const [prefix, icon] of Object.entries(MODEL_ICONS)) {
    if (lowerName.includes(prefix)) {
      return icon;
    }
  }
  return null;
}

export interface TargetTheme {
  primary: string;
  secondary: string;
  gradient: string;
  light: string;
}

// djb2 hash — good distribution for short strings
function hashString(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function hslToHex(h: number, s: number, l: number): string {
  const a = s / 100;
  const b = l / 100;
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = b - a * Math.min(b, 1 - b) * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

export function getTargetTheme(name: string): TargetTheme {
  const hash = hashString(name.toLowerCase().trim());

  // Constrain hue to cool tones: cyan → blue → purple → pink (180-330)
  const hue = 180 + (hash % 150);
  const primary = hslToHex(hue, 65, 45);
  const secondary = hslToHex(hue, 60, 60);
  const gradientStart = hslToHex(hue, 70, 38);
  const gradientEnd = hslToHex(hue, 55, 58);
  const light = hslToHex(hue, 40, 96);

  return {
    primary,
    secondary,
    gradient: `linear-gradient(135deg, ${gradientStart} 0%, ${gradientEnd} 100%)`,
    light,
  };
}

export function getInitials(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

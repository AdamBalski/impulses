export const DAY_MS = 24 * 60 * 60 * 1000;

export function startOfDay(timestamp: number): number {
  return Math.floor(timestamp / DAY_MS) * DAY_MS;
}

export function parseDuration(duration: string): number {
  const regex = /(\d+)(d|h|min|m|s|ms)/g;
  let match: RegExpExecArray | null;
  let total = 0;
  while ((match = regex.exec(duration)) !== null) {
    const amount = parseInt(match[1], 10);
    const unit = match[2];
    switch (unit) {
      case "d":
        total += amount * DAY_MS;
        break;
      case "h":
        total += amount * 60 * 60 * 1000;
        break;
      case "min":
      case "m":
        total += amount * 60 * 1000;
        break;
      case "s":
        total += amount * 1000;
        break;
      case "ms":
        total += amount;
        break;
      default:
        throw new Error(`Unknown duration unit '${unit}'`);
    }
  }
  if (total === 0) {
    throw new Error(`Invalid duration string '${duration}'`);
  }
  return total;
}


export const DAY_MS = 24 * 60 * 60 * 1000;

export function startOfDay(timestamp: number): number {
  return Math.floor(timestamp / DAY_MS) * DAY_MS;
}

export function startOfYear(timestamp: number): number {
  const date = new Date(timestamp);
  date.setUTCMonth(0, 1);
  date.setUTCHours(0, 0, 0, 0);
  return date.getTime();
}

export function addMonths(timestamp: number, months: number): number {
  const date = new Date(timestamp);
  date.setUTCDate(1);
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCMonth(date.getUTCMonth() + months);
  return date.getTime();
}

export function parseDuration(duration: string): number {
  const regex = /(-?\d+)(d|h|min|ms|m|s)/g;
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
  return total;
}


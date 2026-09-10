export const WEB_ENTRY_URL = 'https://zhumenggy.top/?mini=1';

export function buildRetryUrl(timestamp: number): string {
  return `${WEB_ENTRY_URL}&retry=${timestamp}`;
}

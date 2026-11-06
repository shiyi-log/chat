export const SESSION_MARKER_KEY = 'chat.web.authenticated';

export function shouldRestoreSession(marker: string | null): boolean {
  return marker === 'true';
}

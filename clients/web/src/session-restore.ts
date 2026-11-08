export const SESSION_MARKER_KEY = 'chat.web.authenticated';

export function shouldRestoreSession(marker: string | null): boolean {
  return marker === 'true';
}

export async function restoreSessionWithUpdates<T>(client: {
  getMe: () => Promise<T>;
  startUpdatesLoop: () => Promise<void>;
}): Promise<T> {
  const user = await client.getMe();
  await client.startUpdatesLoop();
  return user;
}

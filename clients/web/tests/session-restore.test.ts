import { describe, expect, it } from 'vitest';
import { restoreSessionWithUpdates, shouldRestoreSession } from '../src/session-restore';

describe('shouldRestoreSession', () => {
  it('only restores when this client has saved an authenticated session', () => {
    expect(shouldRestoreSession('true')).toBe(true);
    expect(shouldRestoreSession(null)).toBe(false);
    expect(shouldRestoreSession('false')).toBe(false);
  });
});

describe('restoreSessionWithUpdates', () => {
  it('starts receiving server updates after restoring the logged-in user', async () => {
    const calls: string[] = [];
    const user = { id: 7 };

    const restored = await restoreSessionWithUpdates({
      getMe: async () => {
        calls.push('getMe');
        return user;
      },
      startUpdatesLoop: async () => {
        calls.push('startUpdatesLoop');
      },
    });

    expect(restored).toBe(user);
    expect(calls).toEqual(['getMe', 'startUpdatesLoop']);
  });

  it('does not start updates when the saved session is no longer authorized', async () => {
    let updatesStarted = false;
    const error = new Error('AUTH_KEY_UNREGISTERED');

    await expect(restoreSessionWithUpdates({
      getMe: async () => { throw error; },
      startUpdatesLoop: async () => { updatesStarted = true; },
    })).rejects.toBe(error);

    expect(updatesStarted).toBe(false);
  });
});

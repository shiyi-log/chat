import { describe, expect, it } from 'vitest';
import { shouldRestoreSession } from '../src/session-restore';

describe('shouldRestoreSession', () => {
  it('only restores when this client has saved an authenticated session', () => {
    expect(shouldRestoreSession('true')).toBe(true);
    expect(shouldRestoreSession(null)).toBe(false);
    expect(shouldRestoreSession('false')).toBe(false);
  });
});

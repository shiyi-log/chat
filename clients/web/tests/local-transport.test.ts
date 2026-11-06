import { describe, expect, it } from 'vitest';
import { createLocalWebSocket } from '../src/local-transport';

describe('local WebSocket transport', () => {
  it('redirects the DC URL to the configured local endpoint and preserves protocols', () => {
    const calls: Array<{ url: string | URL; protocols?: string | string[] }> = [];
    class FakeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        calls.push({ url, protocols });
      }
    }

    const LocalWebSocket = createLocalWebSocket(
      'ws://127.0.0.1:35443',
      FakeWebSocket as unknown as typeof WebSocket,
    );

    new LocalWebSocket('wss://pluto.web.telegram.org/apiws', 'binary');

    expect(calls).toEqual([{ url: 'ws://127.0.0.1:35443', protocols: 'binary' }]);
  });
});

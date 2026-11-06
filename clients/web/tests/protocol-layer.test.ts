import { describe, expect, it } from 'vitest';
import { tl } from '@mtcute/core';

describe('MTProto schema compatibility', () => {
  it('uses the API layer supported by the local server', () => {
    expect(tl.LAYER).toBe(222);
  });
});

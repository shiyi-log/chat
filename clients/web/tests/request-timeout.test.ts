import { describe, expect, it } from 'vitest';
import { withRequestTimeout } from '../src/request-timeout';

describe('withRequestTimeout', () => {
  it('aborts an operation that does not finish before its deadline', async () => {
    await expect(withRequestTimeout(() => new Promise<never>(() => undefined), 5))
      .rejects.toThrow('连接超时，请检查本地服务和网络后重试。');
  });

  it('returns a result when the operation finishes before its deadline', async () => {
    await expect(withRequestTimeout(async () => 'ok', 100)).resolves.toBe('ok');
  });
});

import { describe, expect, it } from 'vitest';
import * as authErrors from '../src/auth-errors';
import { describeAuthError } from '../src/auth-errors';

describe('describeAuthError', () => {
  it('returns a clear Chinese message for invalid and expired codes', () => {
    expect(describeAuthError(new Error('PHONE_CODE_INVALID'))).toBe('验证码不正确，请重试。');
    expect(describeAuthError(new Error('PHONE_CODE_EXPIRED'))).toBe('验证码已过期，请重新获取。');
  });

  it('keeps unknown errors useful without exposing stack details', () => {
    expect(describeAuthError(new Error('NETWORK_TIMEOUT'))).toBe('连接失败，请检查本地服务和网络后重试。');
  });

  it('recognizes the server response that requires account registration', () => {
    const helper = (authErrors as unknown as Record<string, unknown>)
      .isSignUpRequiredAuthorization as ((authorization: { _: string }) => boolean) | undefined;

    expect(helper).toBeTypeOf('function');
    expect(helper?.({ _: 'auth.authorizationSignUpRequired' })).toBe(true);
    expect(helper?.({ _: 'auth.authorization' })).toBe(false);
  });
});

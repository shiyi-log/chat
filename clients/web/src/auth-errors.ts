const AUTH_ERROR_MESSAGES: Record<string, string> = {
  PHONE_NUMBER_INVALID: '手机号格式不正确，请检查后重试。',
  PHONE_NUMBER_BANNED: '该手机号暂时无法登录。',
  PHONE_CODE_INVALID: '验证码不正确，请重试。',
  PHONE_CODE_EXPIRED: '验证码已过期，请重新获取。',
  PHONE_CODE_EMPTY: '请输入验证码。',
  PHONE_CODE_HASH_EMPTY: '验证码请求已失效，请重新获取。',
  PHONE_CODE_HASH_INVALID: '验证码请求已失效，请重新获取。',
  SESSION_PASSWORD_NEEDED: '此账号已开启两步验证，请输入密码。',
  PASSWORD_HASH_INVALID: '密码不正确，请重试。',
  PHONE_NUMBER_UNOCCUPIED: '该手机号尚未注册。',
  NETWORK_TIMEOUT: '连接失败，请检查本地服务和网络后重试。',
};

export function describeAuthError(error: unknown): string {
  const source = error instanceof Error ? error.message : String(error);
  if (source.includes('连接超时')) return source;
  const normalized = source.toUpperCase();
  const code = Object.keys(AUTH_ERROR_MESSAGES).find((item) => normalized.includes(item));
  return code ? AUTH_ERROR_MESSAGES[code] : '登录失败，请检查输入并重试。';
}

export function hasRpcError(error: unknown, code: string): boolean {
  const source = error instanceof Error ? error.message : String(error);
  return source.toUpperCase().includes(code.toUpperCase());
}

export function isSignUpRequiredAuthorization(authorization: { _: string }): boolean {
  return authorization._ === 'auth.authorizationSignUpRequired';
}

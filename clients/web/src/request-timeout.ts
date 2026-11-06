export const REQUEST_TIMEOUT_MESSAGE = '连接超时，请检查本地服务和网络后重试。';

export function withRequestTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs = 15_000,
): Promise<T> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error(REQUEST_TIMEOUT_MESSAGE));
    }, timeoutMs);
  });

  return Promise.race([operation(controller.signal), timeout]).finally(() => clearTimeout(timer));
}

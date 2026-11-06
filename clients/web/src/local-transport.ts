export function createLocalWebSocket(
  localEndpoint: string,
  Implementation: typeof WebSocket = WebSocket,
): typeof WebSocket {
  return class LocalWebSocket extends Implementation {
    constructor(_url: string | URL, protocols?: string | string[]) {
      super(localEndpoint, protocols);
    }
  };
}

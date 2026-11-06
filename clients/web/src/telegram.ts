import { WebSocketTransport, TelegramClient } from '@mtcute/web';
import { WebCryptoProvider } from '@mtcute/web';
import { createLocalWebSocket } from './local-transport';
import { registerServerPublicKey } from './server-key';

const localApiId = 123456;
const localApiHash = '0123456789abcdef0123456789abcdef';

export async function createTelegramClient(): Promise<TelegramClient> {
  const apiId = Number(import.meta.env.VITE_CHAT_API_ID || localApiId);
  const apiHash = import.meta.env.VITE_CHAT_API_HASH || localApiHash;
  const endpoint = import.meta.env.VITE_CHAT_WS_URL || 'ws://127.0.0.1:35443';
  const publicKey = import.meta.env.VITE_CHAT_RSA_PUBLIC_KEY || '';

  if (!Number.isInteger(apiId) || apiId < 1 || !/^[a-f\d]{32}$/i.test(apiHash)) {
    throw new Error('Chat API 配置无效');
  }

  if (!publicKey.trim()) {
    throw new Error('未找到本地服务端 RSA 公钥。请先启动本地服务，再刷新页面。');
  }

  const crypto = new WebCryptoProvider();
  await crypto.initialize();
  registerServerPublicKey(crypto, publicKey);

  return new TelegramClient({
    apiId,
    apiHash,
    crypto,
    storage: 'chat.web.session',
    transport: new WebSocketTransport({ ws: createLocalWebSocket(endpoint) }),
  });
}

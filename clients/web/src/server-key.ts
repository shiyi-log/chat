import { addPublicKey, type ICryptoProvider } from '@mtcute/core/utils.js';

export function registerServerPublicKey(crypto: ICryptoProvider, pem: string): void {
  const normalized = pem.replace(/\\n/g, '\n').trim();
  if (!normalized) throw new Error('未配置本地服务端 RSA 公钥');
  addPublicKey(crypto, normalized);
}

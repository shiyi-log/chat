import { type ICryptoProvider, parsePublicKey } from '@mtcute/core/utils.js';
import { __publicKeyIndex } from '@mtcute/tl/binary/rsa-keys.js';

export function registerServerPublicKey(crypto: ICryptoProvider, pem: string): void {
  const normalized = pem.replace(/\\n/g, '\n').trim();
  if (!normalized) throw new Error('未配置本地服务端 RSA 公钥');

  const key = parsePublicKey(crypto, normalized);
  __publicKeyIndex[key.fingerprint] = key;

  // mtcute's handshake lookup drops leading zeroes when formatting Long fingerprints.
  const wireFingerprint = BigInt(`0x${key.fingerprint}`).toString(16);
  if (wireFingerprint !== key.fingerprint) {
    __publicKeyIndex[wireFingerprint] = key;
  }
}

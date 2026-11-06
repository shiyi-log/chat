import { createHash, generateKeyPairSync } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { findKeyByFingerprints, parsePublicKey, type ICryptoProvider } from '@mtcute/core/utils.js';
import { registerServerPublicKey } from '../src/server-key';

describe('registerServerPublicKey', () => {
  it('adds the configured PEM fingerprint to mtcute trust lookup', () => {
    const { publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
    const pem = publicKey.export({ type: 'pkcs1', format: 'pem' }).toString();
    const crypto = {
      sha1: (data: Uint8Array) => createHash('sha1').update(data).digest(),
    } as unknown as ICryptoProvider;

    registerServerPublicKey(crypto, pem);

    const parsed = parsePublicKey(crypto, pem);
    expect(findKeyByFingerprints([parsed.fingerprint])).toEqual(parsed);
  });
});

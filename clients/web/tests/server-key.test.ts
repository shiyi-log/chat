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

  it('resolves fingerprints whose leading zero is omitted by the server handshake', () => {
    const { publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
    const pem = publicKey.export({ type: 'pkcs1', format: 'pem' }).toString();
    const crypto = {
      sha1: () => {
        const digest = Buffer.alloc(20);
        digest.set(Buffer.from('a79cd79966f46b06', 'hex'), 12);
        return digest;
      },
    } as unknown as ICryptoProvider;

    registerServerPublicKey(crypto, pem);

    const parsed = parsePublicKey(crypto, pem);
    const wireFingerprint = BigInt(`0x${parsed.fingerprint}`).toString(16);
    expect(parsed.fingerprint).toBe('066bf46699d79ca7');
    expect(wireFingerprint).toBe('66bf46699d79ca7');
    expect(findKeyByFingerprints([wireFingerprint])).toEqual(parsed);
  });
});

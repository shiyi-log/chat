import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

const webRoot = dirname(fileURLToPath(import.meta.url));
const localPrivateKey = resolve(webRoot, '../../server/integration/.runtime/server_pkcs1.key');

function getLocalPublicKey(): string {
  if (!existsSync(localPrivateKey)) return '';
  try {
    return execFileSync('openssl', ['rsa', '-in', localPrivateKey, '-RSAPublicKey_out'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return '';
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, webRoot, '');
  const publicKey = (env.VITE_CHAT_RSA_PUBLIC_KEY || getLocalPublicKey()).replace(/\\n/g, '\n');

  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_CHAT_RSA_PUBLIC_KEY': JSON.stringify(publicKey),
    },
  };
});

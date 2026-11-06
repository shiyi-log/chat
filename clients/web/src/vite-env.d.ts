/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CHAT_API_ID?: string;
  readonly VITE_CHAT_API_HASH?: string;
  readonly VITE_CHAT_RSA_PUBLIC_KEY?: string;
  readonly VITE_CHAT_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

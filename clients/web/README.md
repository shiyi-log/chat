# Chat Web Client

The browser client connects to the local MTProto WebSocket by default.

## Run locally

From the monorepo root, start the Web client with:

```sh
npm --prefix clients/web ci
npm --prefix clients/web run dev
```

Open `http://127.0.0.1:5175/`. The local runtime must be running from
`server/integration/LOCAL_RUNTIME.md`. The Vite config derives the matching
public RSA key from the ignored local runtime key file; only the public key is
included in the browser bundle. The server and Web client must use the same
runtime key.

For a separately hosted server, configure these build-time variables:

| Variable | Purpose |
| --- | --- |
| `VITE_CHAT_WS_URL` | Server WebSocket endpoint, including `ws://` or `wss://` |
| `VITE_CHAT_RSA_PUBLIC_KEY` | Server's MTProto RSA public key in PKCS#1 PEM format |
| `VITE_CHAT_API_ID` | Client API identifier |
| `VITE_CHAT_API_HASH` | Client API hash |

The built-in API values are local development placeholders. Supply the
deployment's client values when building a hosted client. The client stores
its MTProto session in browser IndexedDB; use **退出登录** to revoke it.

## Verify

```sh
npm --prefix clients/web run verify:protocol
npm --prefix clients/web test
npm --prefix clients/web run build
```

The client currently supports phone-code login, two-step verification,
registration after the server reports an unregistered number, recent dialogs,
message history, and text messages. Attachments and full multi-client
end-to-end validation remain outstanding.

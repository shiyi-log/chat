import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { User, type Dialog, type Message } from '@mtcute/core';
import type { TelegramClient } from '@mtcute/web';
import {
  ArrowLeft,
  KeyRound,
  LoaderCircle,
  LogOut,
  MessageCircle,
  Search,
  Send,
  Smartphone,
  UserRound,
  UserPlus,
} from 'lucide-react';
import { describeAuthError, hasRpcError, isSignUpRequiredAuthorization } from './auth-errors';
import { normalizeContactPhone, resolveImportedContactUser } from './contact-import';
import { normalizePhoneInput } from './phone';
import { withRequestTimeout } from './request-timeout';
import { restoreSessionWithUpdates, SESSION_MARKER_KEY, shouldRestoreSession } from './session-restore';
import { createTelegramClient } from './telegram';

type AuthStep = 'phone' | 'code' | 'password' | 'profile';
type Country = { code: string; label: string };

const countries: Country[] = [
  { code: '+86', label: '中国 +86' },
  { code: '+1', label: '美国 +1' },
  { code: '+44', label: '英国 +44' },
  { code: '+81', label: '日本 +81' },
];

function isAuthBoundary(error: unknown): boolean {
  return [
    'AUTH_KEY_UNREGISTERED',
    'AUTH_KEY_INVALID',
    'AUTH_KEY_PERM_EMPTY',
    'SESSION_REVOKED',
    'USER_ID_INVALID',
    'SESSION_PASSWORD_NEEDED',
  ].some((code) => hasRpcError(error, code));
}

function initials(name: string): string {
  return name.trim().slice(0, 1) || '聊';
}

function formatListTime(date: Date | undefined): string {
  if (!date) return '';
  const now = new Date();
  return date.toDateString() === now.toDateString()
    ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function formatMessageTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function messagePreview(message: Message | null): string {
  if (!message) return '开始一段新对话';
  if (message.text) return message.text;
  if (message.isService) return '系统消息';
  return '附件';
}

type ChatSelection = Dialog | User;

function selectionPeer(selection: ChatSelection) {
  return selection instanceof User ? selection : selection.peer;
}

function AuthView({
  client,
  onAuthorized,
  startupMessage,
}: {
  client: TelegramClient;
  onAuthorized: (user: User) => Promise<void>;
  startupMessage: string;
}) {
  const [step, setStep] = useState<AuthStep>('phone');
  const [countryCode, setCountryCode] = useState('+86');
  const [phoneInput, setPhoneInput] = useState('');
  const [phone, setPhone] = useState('');
  const [phoneCodeHash, setPhoneCodeHash] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = async (action: (signal: AbortSignal) => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await withRequestTimeout(action);
    } catch (reason) {
      setError(describeAuthError(reason));
    } finally {
      setBusy(false);
    }
  };

  const requestCode = (event: FormEvent) => {
    event.preventDefault();
    void run(async (abortSignal) => {
      const normalized = normalizePhoneInput(phoneInput, countryCode);
      const result = await client.sendCode({ phone: normalized, abortSignal });
      if ('phoneCodeHash' in result) {
        setPhone(normalized);
        setPhoneCodeHash(result.phoneCodeHash);
        setStep('code');
      } else {
        await onAuthorized(result);
      }
    });
  };

  const submitCode = (event: FormEvent) => {
    event.preventDefault();
    void run(async (abortSignal) => {
      try {
        const authorization = await client.call({
          _: 'auth.signIn',
          phoneNumber: phone,
          phoneCodeHash,
          phoneCode: code.trim(),
        }, { abortSignal });
        if (isSignUpRequiredAuthorization(authorization)) {
          setStep('profile');
          return;
        }
        const rawUser = await client.notifyLoggedIn(authorization);
        await onAuthorized(new User(rawUser));
      } catch (reason) {
        if (hasRpcError(reason, 'SESSION_PASSWORD_NEEDED')) {
          setStep('password');
          return;
        }
        if (hasRpcError(reason, 'PHONE_NUMBER_UNOCCUPIED')) {
          setStep('profile');
          return;
        }
        throw reason;
      }
    });
  };

  const submitPassword = (event: FormEvent) => {
    event.preventDefault();
    void run(async (abortSignal) => onAuthorized(await client.checkPassword({ password, abortSignal })));
  };

  const submitProfile = (event: FormEvent) => {
    event.preventDefault();
    void run(async (abortSignal) => {
      const authorization = await client.call({
        _: 'auth.signUp',
        phoneNumber: phone,
        phoneCodeHash,
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        noJoinedNotifications: true,
      }, { abortSignal });
      const rawUser = await client.notifyLoggedIn(authorization);
      await onAuthorized(new User(rawUser));
    });
  };

  const title = step === 'phone'
    ? '用手机号登录'
    : step === 'code'
      ? '输入验证码'
      : step === 'password'
        ? '两步验证'
        : '创建账户';

  return (
    <main className="auth-shell">
      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="brand-lockup">
          <span className="brand-mark"><MessageCircle size={24} strokeWidth={2.4} /></span>
          <span>Chat</span>
        </div>
        <h1 id="auth-title">{title}</h1>
        {step === 'phone' && <p className="auth-copy">使用手机号继续</p>}
        {step === 'code' && <p className="auth-copy">验证码已发送至 {phone}</p>}
        {step === 'password' && <p className="auth-copy">输入账号的两步验证密码</p>}
        {step === 'profile' && <p className="auth-copy">为新账户填写姓名</p>}

        {startupMessage && step === 'phone' && <p className="notice" role="status">{startupMessage}</p>}
        {error && <p className="error-message" role="alert">{error}</p>}

        {step === 'phone' && (
          <form className="auth-form" onSubmit={requestCode}>
            <label className="field-label" htmlFor="country">国家或地区</label>
            <select id="country" value={countryCode} onChange={(event) => setCountryCode(event.target.value)}>
              {countries.map((country) => <option key={country.code} value={country.code}>{country.label}</option>)}
            </select>
            <label className="field-label" htmlFor="phone">手机号</label>
            <div className="input-with-icon">
              <Smartphone size={18} aria-hidden="true" />
              <input
                autoComplete="tel-national"
                id="phone"
                inputMode="tel"
                onChange={(event) => setPhoneInput(event.target.value)}
                placeholder="请输入手机号"
                required
                value={phoneInput}
              />
            </div>
            <button className="primary-button" disabled={busy} type="submit">
              {busy ? <LoaderCircle className="spin" size={18} /> : null}
              请求验证码
            </button>
          </form>
        )}

        {step === 'code' && (
          <form className="auth-form" onSubmit={submitCode}>
            <label className="field-label" htmlFor="code">短信验证码</label>
            <div className="input-with-icon">
              <KeyRound size={18} aria-hidden="true" />
              <input autoComplete="one-time-code" autoFocus id="code" inputMode="numeric" onChange={(event) => setCode(event.target.value)} placeholder="输入验证码" required value={code} />
            </div>
            <button className="primary-button" disabled={busy} type="submit">
              {busy ? <LoaderCircle className="spin" size={18} /> : null}
              继续
            </button>
            <button className="text-button" onClick={() => setStep('phone')} type="button">更换手机号</button>
          </form>
        )}

        {step === 'password' && (
          <form className="auth-form" onSubmit={submitPassword}>
            <label className="field-label" htmlFor="password">两步验证密码</label>
            <div className="input-with-icon">
              <KeyRound size={18} aria-hidden="true" />
              <input autoComplete="current-password" autoFocus id="password" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
            </div>
            <button className="primary-button" disabled={busy} type="submit">
              {busy ? <LoaderCircle className="spin" size={18} /> : null}
              登录
            </button>
            <button className="text-button" onClick={() => setStep('code')} type="button">返回验证码</button>
          </form>
        )}

        {step === 'profile' && (
          <form className="auth-form" onSubmit={submitProfile}>
            <label className="field-label" htmlFor="first-name">名字</label>
            <div className="input-with-icon">
              <UserRound size={18} aria-hidden="true" />
              <input autoFocus id="first-name" onChange={(event) => setFirstName(event.target.value)} required value={firstName} />
            </div>
            <label className="field-label" htmlFor="last-name">姓氏</label>
            <input id="last-name" onChange={(event) => setLastName(event.target.value)} value={lastName} />
            <button className="primary-button" disabled={busy} type="submit">
              {busy ? <LoaderCircle className="spin" size={18} /> : null}
              创建账户并登录
            </button>
          </form>
        )}
      </section>
    </main>
  );
}

function ChatApp({ client }: { client: TelegramClient }) {
  const [user, setUser] = useState<User | null>(null);
  const [dialogs, setDialogs] = useState<Dialog[]>([]);
  const [selected, setSelected] = useState<ChatSelection | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [search, setSearch] = useState('');
  const [draft, setDraft] = useState('');
  const [newChatOpen, setNewChatOpen] = useState(false);
  const [contactCountryCode, setContactCountryCode] = useState('+86');
  const [contactPhone, setContactPhone] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactError, setContactError] = useState('');
  const [startupMessage, setStartupMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [lookingUpContact, setLookingUpContact] = useState(false);
  const [chatError, setChatError] = useState('');
  const selectedRef = useRef<ChatSelection | null>(null);
  const listEndRef = useRef<HTMLDivElement>(null);

  const refreshDialogs = useCallback(async () => {
    const result: Dialog[] = [];
    for await (const dialog of client.iterDialogs({ limit: 100 })) result.push(dialog);
    setDialogs(result);
  }, [client]);

  const onAuthorized = useCallback(async (authorizedUser: User) => {
    try { window.localStorage.setItem(SESSION_MARKER_KEY, 'true'); } catch { /* private browsing may disable storage */ }
    setUser(authorizedUser);
    setStartupMessage('');
    await refreshDialogs();
  }, [refreshDialogs]);

  useEffect(() => {
    let savedSession = false;
    try {
      savedSession = shouldRestoreSession(window.localStorage.getItem(SESSION_MARKER_KEY));
    } catch {
      savedSession = false;
    }
    if (!savedSession) {
      setLoading(false);
      return;
    }

    let active = true;
    const revealLogin = window.setTimeout(() => {
      if (active) setLoading(false);
    }, 1800);
    void restoreSessionWithUpdates(client).then(async (currentUser) => {
      if (!active) return;
      setUser(currentUser);
      await refreshDialogs();
    }).catch((reason: unknown) => {
      if (!active || isAuthBoundary(reason)) return;
      setStartupMessage(describeAuthError(reason));
    }).finally(() => {
      if (active) {
        window.clearTimeout(revealLogin);
        setLoading(false);
      }
    });
    return () => {
      active = false;
      window.clearTimeout(revealLogin);
    };
  }, [client, refreshDialogs]);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  useEffect(() => {
    const handleMessage = (message: Message) => {
      if (selectedRef.current && selectionPeer(selectedRef.current).id === message.chat.id) {
        setMessages((current) => current.some((item) => item.id === message.id)
          ? current
          : [...current, message]);
      }
      void refreshDialogs().catch(() => undefined);
    };
    client.onNewMessage.add(handleMessage);
    return () => client.onNewMessage.remove(handleMessage);
  }, [client, refreshDialogs]);

  useEffect(() => {
    if (!selected) {
      setMessages([]);
      return;
    }
    const peer = selectionPeer(selected);
    let active = true;
    setLoadingHistory(true);
    setChatError('');
    void client.getHistory(peer.inputPeer, { limit: 50 }).then((page) => {
      if (active) setMessages([...page].reverse());
    }).catch((reason: unknown) => {
      if (active) setChatError(describeAuthError(reason));
    }).finally(() => {
      if (active) setLoadingHistory(false);
    });
    return () => { active = false; };
  }, [client, selected]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages]);

  const visibleDialogs = dialogs.filter((dialog) =>
    dialog.peer.displayName.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
  );
  const selectedPeer = selected ? selectionPeer(selected) : null;

  const startContactChat = (event: FormEvent) => {
    event.preventDefault();
    if (lookingUpContact) return;
    setLookingUpContact(true);
    setContactError('');
    try {
      const phone = normalizeContactPhone(contactPhone, contactCountryCode);
      void client.importContacts([{
        phone,
        firstName: contactName.trim() || '联系人',
        lastName: '',
      }]).then((result) => {
        const rawUser = resolveImportedContactUser(result, 1);
        if (!rawUser) {
          setContactError('没有找到使用该手机号注册的用户，请检查号码后重试。');
          return;
        }
        setSearch('');
        setChatError('');
        setSelected(new User(rawUser));
        setNewChatOpen(false);
        setContactPhone('');
        setContactName('');
        void refreshDialogs().catch((reason: unknown) => setChatError(describeAuthError(reason)));
      }).catch((reason: unknown) => {
        setContactError(describeAuthError(reason));
      }).finally(() => setLookingUpContact(false));
    } catch (reason) {
      setContactError(reason instanceof Error ? reason.message : '请输入有效的手机号。');
      setLookingUpContact(false);
    }
  };

  const sendMessage = (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !draft.trim() || sending) return;
    const peer = selectionPeer(selected);
    const text = draft.trim();
    setSending(true);
    setChatError('');
    void client.sendText(peer.inputPeer, text).then((message) => {
      setMessages((current) => current.some((item) => item.id === message.id)
        ? current
        : [...current, message]);
      setDraft('');
      void refreshDialogs().catch((reason: unknown) => setChatError(describeAuthError(reason)));
    }).catch((reason: unknown) => {
      setChatError(describeAuthError(reason));
    }).finally(() => setSending(false));
  };

  const logOut = () => {
    try { window.localStorage.removeItem(SESSION_MARKER_KEY); } catch { /* private browsing may disable storage */ }
    void client.logOut().finally(() => {
      setUser(null);
      setSelected(null);
      setDialogs([]);
      setMessages([]);
    });
  };

  if (loading) {
    return <main className="loading-screen"><LoaderCircle className="spin" size={22} /><span>正在连接 Chat</span></main>;
  }

  if (!user) return <AuthView client={client} onAuthorized={onAuthorized} startupMessage={startupMessage} />;

  return (
    <main className={`chat-shell ${selected ? 'has-selection' : ''}`}>
      <aside className="sidebar" aria-label="会话列表">
        <header className="sidebar-header">
          <div className="brand-lockup compact">
            <span className="brand-mark"><MessageCircle size={20} strokeWidth={2.4} /></span>
            <span>Chat</span>
          </div>
          <div className="sidebar-actions">
            <button
              className="icon-button"
              aria-label="新建聊天"
              title="新建聊天"
              onClick={() => {
                setNewChatOpen((open) => !open);
                setContactError('');
              }}
              type="button"
            ><UserPlus size={18} /></button>
            <button className="icon-button" aria-label="退出登录" title="退出登录" onClick={logOut} type="button"><LogOut size={18} /></button>
          </div>
        </header>
        <div className="profile-line">
          <span className="avatar self-avatar">{initials(user.displayName)}</span>
          <span className="profile-name">{user.displayName}</span>
          <span className="online-dot" aria-label="已连接" title="已连接" />
        </div>
        <label className="search-box">
          <Search size={17} aria-hidden="true" />
          <input aria-label="搜索会话" onChange={(event) => setSearch(event.target.value)} placeholder="搜索" value={search} />
        </label>
        {newChatOpen && (
          <form className="new-chat-form" aria-label="新建聊天" onSubmit={startContactChat}>
            <label className="field-label" htmlFor="contact-country">国家或地区</label>
            <select id="contact-country" onChange={(event) => setContactCountryCode(event.target.value)} value={contactCountryCode}>
              {countries.map((country) => <option key={country.code} value={country.code}>{country.label}</option>)}
            </select>
            <label className="field-label" htmlFor="contact-phone">手机号</label>
            <input
              autoComplete="tel"
              id="contact-phone"
              inputMode="tel"
              onChange={(event) => setContactPhone(event.target.value)}
              placeholder="请输入手机号"
              required
              value={contactPhone}
            />
            <label className="field-label" htmlFor="contact-name">联系人名称（可选）</label>
            <input id="contact-name" onChange={(event) => setContactName(event.target.value)} value={contactName} />
            {contactError && <p className="error-message" role="alert">{contactError}</p>}
            <button className="primary-button" disabled={lookingUpContact} type="submit">
              {lookingUpContact ? <LoaderCircle className="spin" size={16} /> : null}
              查找并开始聊天
            </button>
          </form>
        )}
        <div className="list-heading">最近消息</div>
        <div className="dialog-list">
          {visibleDialogs.map((dialog) => (
            <button
              className={`dialog-row ${selectedPeer?.id === dialog.peer.id ? 'selected' : ''}`}
              key={dialog.peer.id}
              onClick={() => setSelected(dialog)}
              type="button"
            >
              <span className="avatar">{initials(dialog.peer.displayName)}</span>
              <span className="dialog-copy">
                <span className="dialog-title">{dialog.peer.displayName}</span>
                <span className="dialog-preview">{messagePreview(dialog.lastMessage)}</span>
              </span>
              <span className="dialog-meta">
                <time>{formatListTime(dialog.lastMessage?.date)}</time>
                {dialog.unreadCount > 0 && <span className="unread-count">{dialog.unreadCount}</span>}
              </span>
            </button>
          ))}
          {!visibleDialogs.length && <p className="empty-list">{search ? '没有找到会话' : '暂时没有会话'}</p>}
        </div>
        <footer className="sidebar-footer">已连接本地服务</footer>
      </aside>

      <section className="conversation" aria-label="聊天内容">
        {selected ? (
          <>
            <header className="conversation-header">
              <button className="icon-button back-button" aria-label="返回会话列表" onClick={() => setSelected(null)} type="button"><ArrowLeft size={19} /></button>
              <span className="avatar small-avatar">{initials(selectedPeer?.displayName ?? '')}</span>
              <div className="conversation-person">
                <h1>{selectedPeer?.displayName}</h1>
                <span>Chat 会话</span>
              </div>
            </header>
            {chatError && <div className="chat-error" role="alert">{chatError}</div>}
            <div className="message-list" aria-live="polite">
              {loadingHistory ? <div className="history-loading"><LoaderCircle className="spin" size={18} />正在读取消息</div> : null}
              {!loadingHistory && messages.length === 0 && <div className="empty-conversation">还没有消息，发出第一条吧。</div>}
              {messages.map((message) => (
                <article className={`message-row ${message.isOutgoing ? 'outgoing' : ''}`} key={`${message.chat.id}-${message.id}`}>
                  <div className="message-bubble">
                    <p>{messagePreview(message)}</p>
                    <time>{formatMessageTime(message.date)}</time>
                  </div>
                </article>
              ))}
              <div ref={listEndRef} />
            </div>
            <form className="composer" onSubmit={sendMessage}>
              <textarea
                aria-label="输入消息"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="写消息…"
                rows={1}
                value={draft}
              />
              <button className="send-button" aria-label="发送消息" disabled={!draft.trim() || sending} title="发送消息" type="submit">
                {sending ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
              </button>
            </form>
          </>
        ) : (
          <div className="conversation-empty">
            <div className="empty-symbol"><MessageCircle size={26} /></div>
            <h1>选择一段对话</h1>
            <p>你的消息会显示在这里</p>
          </div>
        )}
      </section>
    </main>
  );
}

export function App() {
  const [client, setClient] = useState<TelegramClient | null>(null);
  const [initializationError, setInitializationError] = useState('');

  useEffect(() => {
    let active = true;
    void createTelegramClient().then((createdClient) => {
      if (active) setClient(createdClient);
    }).catch((reason: unknown) => {
      if (active) setInitializationError(reason instanceof Error ? reason.message : '无法初始化本地连接');
    });
    return () => { active = false; };
  }, []);

  if (!client) {
    return (
      <main className="loading-screen">
        {initializationError ? <p className="error-message" role="alert">{initializationError}</p> : <><LoaderCircle className="spin" size={22} /><span>正在准备本地连接</span></>}
      </main>
    );
  }

  return <ChatApp client={client} />;
}

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/**
 * Bnome Connect — browser step of the `npx @bnome/connect` installer.
 *
 * The CLI opens this page with ?cb=http://127.0.0.1:PORT/callback&state=...&agent=Claude.
 * The user is (or logs in) authenticated with ANY method (Google or password), approves,
 * and we mint a long-lived agent token and redirect it back to the CLI's localhost server.
 *
 * SECURITY: cb MUST be a loopback address. We never post the token anywhere else — this
 * prevents a crafted /connect?cb=evil.com link from stealing a logged-in user's token.
 */
const isLoopbackCb = (cb) => {
  if (!cb) return false;
  try {
    const u = new URL(cb);
    return u.protocol === 'http:' && (u.hostname === '127.0.0.1' || u.hostname === 'localhost');
  } catch {
    return false;
  }
};

const shell = {
  display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
  minHeight: '100vh', background: '#09090b', color: '#e4e4e7', textAlign: 'center',
  fontFamily: 'Inter, system-ui, sans-serif', padding: 24, gap: 16,
};
const btn = {
  background: 'linear-gradient(135deg,#ec4899,#a855f7)', color: '#fff', border: 'none',
  padding: '12px 28px', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer',
};
const ghost = {
  background: 'transparent', color: '#a1a1aa', border: '1px solid #27272a',
  padding: '12px 28px', borderRadius: 10, fontSize: 15, cursor: 'pointer',
};

const ConnectPage = () => {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, user, token } = useAuth();
  const [status, setStatus] = useState('idle'); // idle | working | done | error
  const [error, setError] = useState('');

  const cb = searchParams.get('cb') || '';
  const state = searchParams.get('state') || '';
  const agent = searchParams.get('agent') || 'your agent';
  const cbOk = useMemo(() => isLoopbackCb(cb), [cb]);

  const approve = async () => {
    setStatus('working');
    setError('');
    try {
      const res = await fetch('/api/auth/agent-token', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token || localStorage.getItem('auth_token')}` },
      });
      if (!res.ok) throw new Error(`mint failed (${res.status})`);
      const data = await res.json();
      const sep = cb.includes('?') ? '&' : '?';
      const dest = `${cb}${sep}token=${encodeURIComponent(data.token)}&state=${encodeURIComponent(state)}`;
      setStatus('done');
      window.location.href = dest;
    } catch (e) {
      setStatus('error');
      setError(e.message || 'Something went wrong');
    }
  };

  // Bad/missing callback — refuse outright.
  if (!cbOk) {
    return (
      <div style={shell}>
        <h2 style={{ margin: 0 }}>Invalid connect link</h2>
        <p style={{ color: '#a1a1aa', maxWidth: 420 }}>
          This page must be opened by the Bnome installer. Run{' '}
          <code style={{ color: '#ec4899' }}>npx @bnome/connect install</code> in your terminal.
        </p>
      </div>
    );
  }

  // Not logged in → prompt sign-in (works for Google OR password).
  if (!isAuthenticated) {
    return (
      <div style={shell}>
        <h2 style={{ margin: 0 }}>Connect Bnome to {agent}</h2>
        <p style={{ color: '#a1a1aa', maxWidth: 420 }}>Sign in to Bnome to authorize the connection.</p>
        <button style={btn} onClick={() => window.showAuthModal && window.showAuthModal()}>Sign in</button>
      </div>
    );
  }

  return (
    <div style={shell}>
      <h2 style={{ margin: 0 }}>Connect Bnome to {agent}?</h2>
      <p style={{ color: '#a1a1aa', maxWidth: 440 }}>
        Signed in as <strong style={{ color: '#e4e4e7' }}>{user?.email}</strong>. This grants{' '}
        <strong>{agent}</strong> a token to build and manage apps in your Bnome account.
      </p>
      {status === 'error' && <p style={{ color: '#f87171' }}>Error: {error}</p>}
      {status === 'done' ? (
        <p style={{ color: '#4ade80' }}>Approved — return to your terminal. You can close this tab.</p>
      ) : (
        <div style={{ display: 'flex', gap: 12 }}>
          <button style={btn} disabled={status === 'working'} onClick={approve}>
            {status === 'working' ? 'Connecting…' : 'Approve'}
          </button>
          <button style={ghost} onClick={() => window.close()}>Cancel</button>
        </div>
      )}
    </div>
  );
};

export default ConnectPage;

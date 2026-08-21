import { useState, type FormEvent } from 'react';
import { ArrowRight, ShieldCheck, Sparkles } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

type DemoUser = {
  label: string;
  email: string;
  roleHint: string;
  short: string;
};

const DEMO_USERS: DemoUser[] = [
  { label: 'Manager (Card Banking)', short: 'Manager', email: 'manager.card@cbe.et', roleHint: 'Generate unit objectives' },
  { label: 'Director (Card Banking)', short: 'Director', email: 'director.card@cbe.et', roleHint: 'Approve Card Banking' },
  { label: 'Manager (Recon)', short: 'Manager', email: 'manager.recon@cbe.et', roleHint: 'Reconciliation objectives' },
  { label: 'Unit Director (Recon)', short: 'Director', email: 'director.recon@cbe.et', roleHint: 'Approve Recon unit' },
  { label: 'Manager (Merchant Management)', short: 'Manager', email: 'manager.merchant@cbe.et', roleHint: 'Merchant management objectives' },
  // { label: 'Manager (Agent Management)', short: 'Manager', email: 'manager.agent@cbe.et', roleHint: 'Agent management objectives' },
  // { label: 'Manager (Digital Partners)', short: 'Manager', email: 'manager.digitalpartners@cbe.et', roleHint: 'Digital partners objectives' },
  { label: 'Director (Merchant & Agent Mgmt)', short: 'Director', email: 'director.merchant@cbe.et', roleHint: 'Approve Merchant & Agent Mgmt' },
  // { label: 'Manager (Mobile & Internet Banking)', short: 'Manager', email: 'manager.mobilebanking@cbe.et', roleHint: 'Mobile & internet banking objectives' },
  { label: 'Director (Mobile & Internet Banking)', short: 'Director', email: 'director.mobilebanking@cbe.et', roleHint: 'Approve Mobile & Internet Banking' },
  // { label: 'Manager (Mobile Money)', short: 'Manager', email: 'manager.mobilemoney@cbe.et', roleHint: 'Mobile money objectives' },
  { label: 'Director (Mobile Money)', short: 'Director', email: 'director.mobilemoney@cbe.et', roleHint: 'Approve Mobile Money' },
  { label: 'VP', short: 'VP', email: 'vp.digital@cbe.et', roleHint: 'Division sign-off → PMS' },
  { label: 'PMS Department', short: 'PMS', email: 'pms@cbe.et', roleHint: 'Official register' },
  { label: 'HR Director', short: 'HR', email: 'hr.director@cbe.et', roleHint: 'Cross-division oversight' },
];

const WORKFLOW = [
  { step: '01', title: 'Managers', detail: 'Craft unit objectives' },
  { step: '02', title: 'Directors', detail: 'Review & approve' },
  { step: '03', title: 'VP', detail: 'Division sign-off' },
  { step: '04', title: 'PMS', detail: 'Official record' },
];

export default function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [email, setEmail] = useState('manager.card@cbe.et');
  const [password, setPassword] = useState('demo123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json() as { access_token: string };
      localStorage.setItem('pms_access_token', json.access_token);
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden font-login text-slate-100">
      {/* Atmosphere */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 80% 60% at 15% 20%, rgba(162, 59, 168, 0.45) 0%, transparent 55%),' +
            'radial-gradient(ellipse 70% 50% at 85% 75%, rgba(196, 137, 74, 0.22) 0%, transparent 50%),' +
            'linear-gradient(155deg, #2a0c2d 0%, #541b58 32%, #892d8f 58%, #3a123d 100%)',
        }}
      />

      {/* Soft mesh sheen */}
      <div
        className="absolute inset-0 opacity-40 pointer-events-none"
        style={{
          backgroundImage:
            'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.08) 0%, transparent 25%),' +
            'radial-gradient(circle at 75% 20%, rgba(232,201,150,0.1) 0%, transparent 20%)',
        }}
      />

      {/* Liquid blobs */}
      <div
        className="absolute -top-24 -left-20 w-[28rem] h-[28rem] bg-brand-400/35 blur-3xl animate-liquid-1 pointer-events-none"
        aria-hidden
      />
      <div
        className="absolute top-1/3 -right-16 w-[26rem] h-[26rem] bg-gold-500/25 blur-3xl animate-liquid-2 pointer-events-none"
        aria-hidden
      />
      <div
        className="absolute -bottom-28 left-1/3 w-[32rem] h-[32rem] bg-brand-700/50 blur-3xl animate-liquid-3 pointer-events-none"
        aria-hidden
      />
      <div
        className="absolute top-[18%] left-[42%] w-40 h-40 rounded-full bg-gold-300/20 blur-2xl animate-float-soft pointer-events-none"
        aria-hidden
      />

      {/* Content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center px-4 py-10 sm:px-6 lg:px-10">
        <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-center">
          {/* Brand column */}
          <section className="lg:col-span-6 animate-login-rise" style={{ animationDelay: '40ms' }}>
            <div className="flex flex-col items-center lg:items-start text-center lg:text-left">
              <div className="flex items-center gap-4 sm:gap-5">
                <div className="relative shrink-0 animate-float-soft">
                  <div
                    className="absolute inset-0 -m-4 rounded-full blur-2xl opacity-80"
                    style={{ background: 'radial-gradient(circle, rgba(232,201,150,0.5) 0%, transparent 68%)' }}
                  />
                  <div className="relative w-20 h-20 sm:w-24 sm:h-24 flex items-center justify-center">
                    <img
                      src="/cbe-logo.svg"
                      alt="Commercial Bank of Ethiopia"
                      className="w-full h-full object-contain drop-shadow-[0_16px_48px_rgba(0,0,0,0.35)]"
                    />
                  </div>
                </div>

                <div className="min-w-0 text-left">
                  <p className="text-[10px] sm:text-xs font-semibold tracking-[0.18em] uppercase text-gold-300/90">
                    Commercial Bank of Ethiopia
                  </p>
                  <h1 className="mt-1 font-display text-2xl sm:text-3xl lg:text-[2.35rem] leading-[1.1] font-semibold text-white tracking-tight">
                    AI Powered Performance Management System
                  </h1>
                </div>
              </div>

              <p className="mt-5 max-w-md text-sm sm:text-base text-white/70 leading-relaxed">
                Performance Management System — a refined, role-based path from objective drafting to official record.
              </p>

              <div className="mt-8 w-full max-w-md login-glass-soft rounded-2xl p-4 sm:p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles size={14} className="text-gold-300" />
                  <p className="text-[11px] font-semibold tracking-[0.2em] uppercase text-gold-300/90">
                    Approval flow
                  </p>
                </div>
                <ol className="grid grid-cols-2 gap-3">
                  {WORKFLOW.map((item) => (
                    <li key={item.step} className="flex items-start gap-2.5">
                      <span className="mt-0.5 text-[10px] font-bold tracking-wider text-gold-400/90 tabular-nums">
                        {item.step}
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-white leading-tight">{item.title}</p>
                        <p className="mt-0.5 text-xs text-white/55 leading-snug">{item.detail}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </section>

          {/* Sign-in + demo */}
          <section className="lg:col-span-6 animate-login-rise" style={{ animationDelay: '140ms' }}>
            <div className="login-panel-white rounded-[1.75rem] p-6 sm:p-8 lg:p-9">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-display text-3xl font-semibold text-brand-800 tracking-tight">Sign in</h2>
                  <p className="mt-1.5 text-sm text-slate-500">
                    Enter your credentials to continue to CBE PMS.
                  </p>
                </div>
                <div className="hidden sm:flex h-10 w-10 items-center justify-center rounded-full border border-brand-100 bg-brand-50">
                  <ShieldCheck size={18} className="text-brand-500" />
                </div>
              </div>

              {error && (
                <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {error}
                </div>
              )}

              <form className="mt-6 space-y-4" onSubmit={submit}>
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Email
                  </label>
                  <input
                    className="login-field"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@cbe.et"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Password
                  </label>
                  <input
                    className="login-field"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Your password"
                  />
                </div>

                <button type="submit" className="login-btn-primary mt-2" disabled={loading}>
                  {loading ? 'Signing in…' : 'Sign in'}
                  {!loading && <ArrowRight size={16} />}
                </button>
              </form>

              <div className="mt-7 pt-6 border-t border-slate-100">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-500">
                    Demo quick sign-in
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[15.5rem] overflow-y-auto pr-1 [scrollbar-width:thin]">
                  {DEMO_USERS.map((u) => {
                    const active = email === u.email;
                    return (
                      <button
                        key={u.email}
                        type="button"
                        className={`login-demo-chip ${active ? 'is-active' : ''}`}
                        onClick={() => { setEmail(u.email); setPassword('demo123'); }}
                        disabled={loading}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-800 truncate">{u.label}</p>
                          <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded-md bg-brand-50 text-brand-600 border border-brand-100">
                            {u.short}
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] text-slate-400 truncate">{u.email}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">{u.roleHint}</p>
                      </button>
                    );
                  })}
                </div>

                <p className="mt-4 text-[11px] text-slate-400 leading-relaxed">
                  Suggested walkthrough: Manager → Director → VP → PMS.
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

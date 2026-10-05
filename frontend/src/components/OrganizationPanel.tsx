import { useCallback, useEffect, useState } from 'react'
import { Building2, KeyRound, Loader2, ScrollText, ShieldCheck, UserPlus, Users } from 'lucide-react'
import {
  AuthUser,
  Org,
  OrgMember,
  AuditEvent,
  activateOrg,
  configureOrgSso,
  createOrg,
  getOrgAudit,
  inviteOrgMember,
  listMyOrgs,
  listOrgMembers,
} from '../api/climoraApi'
import { makeReceipt } from '../plans'
import { notifyUsageChanged } from '../usageBus'

const inputCls =
  'w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-climora-500'

export default function OrganizationPanel({ user, onSignIn }: { user: AuthUser | null; onSignIn: () => void }) {
  const [orgs, setOrgs] = useState<Org[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [members, setMembers] = useState<OrgMember[]>([])
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  // Forms
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [domain, setDomain] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('member')
  const [issuer, setIssuer] = useState('')
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')

  const refresh = useCallback(async () => {
    if (!user) {
      setOrgs([])
      setLoaded(true)
      return
    }
    try {
      const { orgs: list } = await listMyOrgs()
      setOrgs(list)
      setActiveId(prev => (list.some(o => o.id === prev) ? prev : (list[0]?.id ?? null)))
    } catch {
      // Offline — panel shows last state.
    } finally {
      setLoaded(true)
    }
  }, [user])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!activeId) {
      setMembers([])
      setEvents([])
      return
    }
    let cancelled = false
    listOrgMembers(activeId).then(({ members: m }) => {
      if (!cancelled) setMembers(m)
    }).catch(() => {})
    getOrgAudit(activeId).then(({ events: e }) => {
      if (!cancelled) setEvents(e)
    }).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [activeId])

  if (!user) {
    return (
      <div className="py-4 text-center">
        <Building2 className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
        <p className="text-sm text-slate-600 dark:text-slate-300">Organizations require an account.</p>
        <button onClick={onSignIn} className="mt-3 px-4 py-2 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700">
          Sign in
        </button>
      </div>
    )
  }

  const active = orgs.find(o => o.id === activeId) ?? null
  const role = active?.role ?? null
  const canAdmin = role === 'owner' || role === 'admin'
  const isOwner = role === 'owner'

  const fail = (e: unknown, fallback: string) => {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    setError(detail || fallback)
  }

  const handleCreate = async () => {
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      const { org } = await createOrg(name.trim() || slug.trim(), slug.trim().toLowerCase(), domain.trim().toLowerCase())
      setName('')
      setSlug('')
      setDomain('')
      await refresh()
      setActiveId(org.id)
      setNotice(`Organization "${org.name}" created — members inherit the Enterprise plan.`)
      notifyUsageChanged()
    } catch (e) {
      fail(e, 'Could not create the organization.')
    } finally {
      setBusy(false)
    }
  }

  const handleInvite = async () => {
    if (!active) return
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      await inviteOrgMember(active.id, inviteEmail.trim(), inviteRole)
      setInviteEmail('')
      const { members: m } = await listOrgMembers(active.id)
      setMembers(m)
      const { events: ev } = await getOrgAudit(active.id).catch(() => ({ events: [] }))
      setEvents(ev)
      setNotice('Member added.')
    } catch (e) {
      fail(e, 'Could not add the member.')
    } finally {
      setBusy(false)
    }
  }

  const handleSso = async () => {
    if (!active) return
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      const { org } = await configureOrgSso(active.id, issuer.trim(), clientId.trim(), clientSecret)
      setOrgs(prev => prev.map(o => (o.id === org.id ? org : o)))
      setClientSecret('')
      const { events: ev } = await getOrgAudit(active.id).catch(() => ({ events: [] }))
      setEvents(ev)
      setNotice('Identity provider connected. Members can now use Enterprise SSO from the sign-in dialog.')
    } catch (e) {
      fail(e, 'Could not save the SSO configuration.')
    } finally {
      setBusy(false)
    }
  }

  const handleActivate = async () => {
    if (!active) return
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      // Demo purchase: receipt generated locally, entitlement recorded
      // server-side. A real Stripe webhook would activate the same way.
      const { org } = await activateOrg(active.id, 'annual', makeReceipt())
      setOrgs(prev => prev.map(o => (o.id === org.id ? org : o)))
      setActiveId(org.id)
      const { events: ev } = await getOrgAudit(active.id).catch(() => ({ events: [] }))
      setEvents(ev)
      setNotice('Enterprise activated — unlimited quota for all members.')
      notifyUsageChanged()
    } catch (e) {
      fail(e, 'Could not activate the organization.')
    } finally {
      setBusy(false)
    }
  }

  const trialDaysLeft = (org: Org): number | null => {
    if (org.status !== 'trial' || !org.trial_ends_at) return null
    return Math.max(0, Math.ceil((new Date(org.trial_ends_at).getTime() - Date.now()) / 86400_000))
  }

  return (
    <div className="py-4 space-y-5">
      {orgs.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {orgs.map(o => (
            <button
              key={o.id}
              onClick={() => setActiveId(o.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
                o.id === activeId
                  ? 'border-climora-500 bg-climora-50 dark:bg-climora-900/30 text-climora-800 dark:text-climora-200'
                  : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-climora-300'
              }`}
            >
              {o.name}
            </button>
          ))}
        </div>
      )}

      {active ? (
        <>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {active.name} <span className="text-slate-400 font-normal">· /{active.slug}</span>
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Enterprise plan · your role: {role}
                {active.domain ? ` · domain: ${active.domain}` : ''}
                {active.sso_configured ? ' · SSO connected' : ' · SSO not configured'}
              </p>
            </div>
          </div>

          {active.status === 'trial' && (
            <div className="flex items-center justify-between gap-3 text-xs rounded-xl px-3 py-2 bg-climora-50 dark:bg-climora-900/30 border border-climora-200 dark:border-climora-800 text-climora-700 dark:text-climora-300">
              <span>
                Trial{trialDaysLeft(active) !== null ? ` — ${trialDaysLeft(active)} day${trialDaysLeft(active) === 1 ? '' : 's'} left` : ''}.
                Activate to keep unlimited quota for all members.
              </span>
              {isOwner && (
                <button onClick={handleActivate} disabled={busy} className="px-3 py-1.5 text-xs font-medium bg-climora-600 text-white rounded-lg hover:bg-climora-700 disabled:opacity-60 shrink-0">
                  Activate
                </button>
              )}
            </div>
          )}
          {active.status === 'expired' && (
            <div className="flex items-center justify-between gap-3 text-xs rounded-xl px-3 py-2 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300">
              <span>Trial expired — members are back on personal plans until you activate.</span>
              {isOwner && (
                <button onClick={handleActivate} disabled={busy} className="px-3 py-1.5 text-xs font-medium bg-climora-600 text-white rounded-lg hover:bg-climora-700 disabled:opacity-60 shrink-0">
                  Activate
                </button>
              )}
            </div>
          )}
          {active.status === 'active' && active.receipt && (
            <p className="text-xs text-slate-400">
              Active · {active.billing_cycle} billing · receipt <span className="font-mono">{active.receipt}</span>{' '}
              <span className="text-slate-400">(demo order — no charge)</span>
            </p>
          )}

          <div>
            <p className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 mb-2">
              <Users className="w-4 h-4" /> Members ({members.length})
            </p>
            <ul className="space-y-1.5">
              {members.map(m => (
                <li key={m.id} className="flex items-center justify-between text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2">
                  <span className="text-slate-700 dark:text-slate-200 truncate">{m.name || m.email} <span className="text-slate-400 text-xs">{m.name ? m.email : ''}</span></span>
                  <span className="text-xs text-slate-400 shrink-0 ml-2">{m.org_role}</span>
                </li>
              ))}
            </ul>
            {canAdmin && (
              <div className="flex gap-2 mt-2">
                <input value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="colleague@company.example" type="email" aria-label="Invite email" className={inputCls} />
                <select value={inviteRole} onChange={e => setInviteRole(e.target.value)} aria-label="Invite role" className="rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-2 text-sm shrink-0">
                  <option value="member">member</option>
                  <option value="admin">admin</option>
                </select>
                <button onClick={handleInvite} disabled={busy} className="flex items-center gap-1 px-3 py-2 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700 disabled:opacity-60 shrink-0">
                  <UserPlus className="w-4 h-4" /> Add
                </button>
              </div>
            )}
          </div>

          {isOwner && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 space-y-2">
              <p className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200">
                <KeyRound className="w-4 h-4" /> Identity provider (OIDC SSO)
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Works with Okta, Microsoft Entra ID, Auth0, Google Workspace — any OIDC provider. Redirect URI to register:{' '}
                <code className="text-[11px] bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">/api/v1/auth/sso/callback</code> on your backend origin.
                {active.sso_configured && <> Currently: <code className="text-[11px]">{active.sso_issuer}</code></>}
              </p>
              <input value={issuer} onChange={e => setIssuer(e.target.value)} placeholder="Issuer URL, e.g. https://login.microsoftonline.com/…/v2.0" aria-label="OIDC issuer" className={inputCls} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <input value={clientId} onChange={e => setClientId(e.target.value)} placeholder="Client ID" aria-label="OIDC client ID" className={inputCls} />
                <input value={clientSecret} onChange={e => setClientSecret(e.target.value)} placeholder="Client secret (optional with PKCE)" type="password" autoComplete="new-password" aria-label="OIDC client secret" className={inputCls} />
              </div>
              <button onClick={handleSso} disabled={busy} className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium border border-slate-300 dark:border-slate-600 rounded-xl hover:border-climora-400 disabled:opacity-60">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                Save SSO configuration
              </button>
            </div>
          )}

          {canAdmin && events.length > 0 && (
            <div>
              <p className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 mb-2">
                <ScrollText className="w-4 h-4" /> Audit log
              </p>
              <ul className="space-y-1 max-h-48 overflow-y-auto">
                {events.slice(0, 30).map(ev => (
                  <li key={ev.id} className="text-xs text-slate-500 dark:text-slate-400 font-mono bg-slate-50 dark:bg-slate-800/60 rounded-lg px-2.5 py-1.5">
                    {ev.created_at.slice(0, 19).replace('T', ' ')} · {ev.actor} · {ev.action}{ev.detail ? ` · ${ev.detail}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Create your organization</p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
            {loaded ? 'No organization yet. Members inherit unlimited Enterprise quota.' : 'Loading…'}
          </p>
          <div className="space-y-2">
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Organization name" aria-label="Organization name" className={inputCls} />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input value={slug} onChange={e => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} placeholder="Slug, e.g. ministry" aria-label="Organization slug" className={inputCls} />
              <input value={domain} onChange={e => setDomain(e.target.value.toLowerCase().trim())} placeholder="Email domain (optional)" aria-label="Email domain" className={inputCls} />
            </div>
            <button onClick={handleCreate} disabled={busy || !slug.trim()} className="px-4 py-2 text-sm font-medium bg-climora-600 text-white rounded-xl hover:bg-climora-700 disabled:opacity-60">
              {busy ? <Loader2 className="w-4 h-4 animate-spin inline" /> : 'Create organization'}
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      {notice && <p className="text-xs text-climora-700 dark:text-climora-300 bg-climora-50 dark:bg-climora-900/30 border border-climora-200 dark:border-climora-800 rounded-xl px-3 py-2">{notice}</p>}
    </div>
  )
}

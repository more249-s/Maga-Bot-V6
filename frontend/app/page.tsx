
'use client'
import axios from 'axios'
import { useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API || 'http://localhost:8000'

export default function Page() {
  const [summary, setSummary] = useState<any>(null)
  const [works, setWorks] = useState<any[]>([])
  const [token, setToken] = useState<string>('') // simple token box (admin only panel)

  useEffect(() => {
    if (!token) return;
    axios.get(API + '/api/admin/summary', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setSummary(r.data)).catch(()=>{})
    axios.get(API + '/api/works', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setWorks(r.data)).catch(()=>{})
  }, [token])

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-3xl font-bold">لوحة الإدارة</h1>
      <div className="p-4 rounded-2xl bg-neutral-900">
        <label className="block mb-2">توكن الأدمن (للديمو فقط):</label>
        <input className="w-full p-2 rounded bg-neutral-800" placeholder="ضع التوكن من /auth/oauth/callback?code=DISCORD_ID" value={token} onChange={e=>setToken(e.target.value)} />
        <p className="text-sm text-neutral-400 mt-2">* في الإنتاج استخدم OAuth كامل مع جلسات/كوكيز.</p>
      </div>
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-2xl bg-neutral-900">إجمالي المهام: {summary.total_tasks}</div>
          <div className="p-4 rounded-2xl bg-neutral-900">قيد المراجعة: {summary.submitted}</div>
          <div className="p-4 rounded-2xl bg-neutral-900">مقبولة: {summary.accepted} | مرفوضة: {summary.rejected}</div>
        </div>
      )}
      <div className="p-4 rounded-2xl bg-neutral-900">
        <h2 className="text-xl font-semibold mb-4">الأعمال</h2>
        <ul className="space-y-2">
          {works.map(w => <li key={w.id} className="p-3 rounded bg-neutral-800">{w.name} <span className="text-neutral-400">({w.role_name})</span></li>)}
        </ul>
      </div>
    </div>
  )
}

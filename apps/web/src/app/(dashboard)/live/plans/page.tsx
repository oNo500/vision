'use client'

import { useRouter } from 'next/navigation'

import { Button } from '@workspace/ui/components/button'
import { toast } from '@workspace/ui/components/sonner'

import { appPaths } from '@/config/app-paths'
import { env } from '@/config/env'
import { usePlans } from '@/features/live/hooks/use-plans'

export default function LivePlansPage() {
  const router = useRouter()
  const { plans, loading, fetchPlans, deletePlan, loadPlan } = usePlans()

  async function handleCreate() {
    try {
      const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/live/plans`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          name: '新方案',
          product: { name: '', description: '', price: '', highlights: [], faq: [] },
          persona: { name: '', style: '', catchphrases: [], forbidden_words: [] },
          script: { segments: [] },
        }),
      })
      if (!res.ok) { toast.error('Failed to create plan'); return }
      const plan = await res.json()
      router.push(appPaths.dashboard.livePlan((plan as { id: string }).id).href)
    } catch {
      toast.error('Cannot reach backend')
    }
  }

  async function handleLoad(id: string) {
    const ok = await loadPlan(id)
    if (ok) {
      toast.success('Plan loaded')
      router.push(appPaths.dashboard.live.href)
    }
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">方案库</h1>
        <Button onClick={handleCreate} disabled={loading}>+ 新建方案</Button>
      </div>

      {plans.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无方案，点击「新建方案」开始</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 font-medium">方案名称</th>
              <th className="pb-2 font-medium">更新时间</th>
              <th className="pb-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {plans.map((plan) => (
              <tr key={plan.id} className="border-b last:border-0">
                <td className="py-3">{plan.name}</td>
                <td className="py-3 text-muted-foreground">
                  {new Date(plan.updated_at).toLocaleDateString('zh-CN')}
                </td>
                <td className="flex gap-2 py-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => router.push(appPaths.dashboard.livePlan(plan.id).href)}
                  >
                    编辑
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleLoad(plan.id)}
                    disabled={loading}
                  >
                    加载
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => deletePlan(plan.id)}
                    disabled={loading}
                  >
                    删除
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

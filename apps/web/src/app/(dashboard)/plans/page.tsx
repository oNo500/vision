'use client'

import { useRouter } from 'next/navigation'

import { Button } from '@workspace/ui/components/button'
import { toast } from '@workspace/ui/components/sonner'

import { PageHeader } from '@/components/page-header'
import { appPaths } from '@/config/app-paths'
import { usePlans } from '@/features/live/hooks/use-plans'
import { apiFetch } from '@/lib/api-fetch'

export default function LivePlansPage() {
  const router = useRouter()
  const { plans, loading, deletePlan, loadPlan } = usePlans()

  async function handleCreate() {
    const res = await apiFetch<{ id: string }>('live/plans', {
      method: 'POST',
      body: {
        name: '新方案',
        product: { name: '', description: '', price: '', highlights: [], faq: [] },
        persona: { name: '', style: '', catchphrases: [], forbidden_words: [] },
        script: { segments: [] },
      },
      fallbackError: 'Failed to create plan',
    })
    if (res.ok) router.push(appPaths.dashboard.plan(res.data.id).href)
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
      <PageHeader>
        <h1 className="text-sm font-semibold">方案库</h1>
        <div className="flex flex-1 justify-end">
          <Button size="sm" onClick={handleCreate} disabled={loading}>+ 新建方案</Button>
        </div>
      </PageHeader>

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
                    onClick={() => router.push(appPaths.dashboard.plan(plan.id).href)}
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

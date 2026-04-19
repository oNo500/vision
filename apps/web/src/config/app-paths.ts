// Nextjs 集中式路由的唯一数据源

export const appPaths = {
  home: {
    href: '/',
  },
  dashboard: {
    live: {
      href: '/live',
    },
    plans: {
      href: '/plans',
    },
    plan: (id: string) => ({
      href: `/plans/${id}`,
    }),
    planRag: (id: string) => ({
      href: `/plans/${id}/rag`,
    }),
    libraries: {
      href: '/libraries',
    },
    library: (id: string) => ({
      href: `/libraries/${id}`,
    }),
  },
}

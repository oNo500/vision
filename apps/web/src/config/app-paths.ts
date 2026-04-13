// Nextjs 集中式路由的唯一数据源

export const appPaths = {
  home: {
    href: '/',
  },
  dashboard: {
    live: {
      href: '/live',
    },
    livePlans: {
      href: '/live/plans',
    },
    livePlan: (id: string) => ({
      href: `/live/plans/${id}`,
    }),
  },
}

import { Navigate, type RouteObject } from 'react-router'
import { RequireAuth } from './RequireAuth'
import { DeviationPage } from '@/pages/DeviationPage'
import { LoginPage } from '@/pages/LoginPage'
import { MethodologyPage } from '@/pages/MethodologyPage'
import { NewSiteMethodologyPage } from '@/pages/NewSiteMethodologyPage'
import { NewSitePage } from '@/pages/NewSitePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ObservationsPage } from '@/pages/ObservationsPage'
import { SiteOverviewPage } from '@/pages/SiteOverviewPage'
import { SitesPage } from '@/pages/SitesPage'

/**
 * Карта экранов (макет «ЛЦТ — MVP: экраны»):
 * 1 Стройки · 2 Новая стройка · 3 Методика (шаг 2) · 3а Методика объекта ·
 * 5 Обзор · 6 Наблюдения · 7 Отклонение. Экран 4 «Камеры» не подключён: в backend нет камер.
 */
export const routes: RouteObject[] = [
  { path: 'login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      { index: true, element: <Navigate to="/sites" replace /> },
      { path: 'sites', element: <SitesPage /> },
      { path: 'sites/new', element: <NewSitePage /> },
      { path: 'sites/:siteId/setup', element: <NewSitePage /> },
      { path: 'sites/:siteId/setup/methodology', element: <NewSiteMethodologyPage /> },
      { path: 'sites/:siteId', element: <SiteOverviewPage /> },
      { path: 'sites/:siteId/observations', element: <ObservationsPage /> },
      { path: 'sites/:siteId/methodology', element: <MethodologyPage /> },
      { path: 'sites/:siteId/deviations/:deviationId', element: <DeviationPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

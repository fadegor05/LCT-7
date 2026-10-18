import type { RouteObject } from 'react-router'
import { RequireAuth } from './RequireAuth'
import { CamerasPage } from '@/pages/CamerasPage'
import { DeviationPage } from '@/pages/DeviationPage'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { MethodologyPage } from '@/pages/MethodologyPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { ReportPage } from '@/pages/ReportPage'
import { NewSiteMethodologyPage } from '@/pages/NewSiteMethodologyPage'
import { NewSitePage } from '@/pages/NewSitePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ObservationsPage } from '@/pages/ObservationsPage'
import { SiteOverviewPage } from '@/pages/SiteOverviewPage'
import { SitesPage } from '@/pages/SitesPage'

/**
 * Карта экранов (макет «ЛЦТ — MVP: экраны»):
 * 1 Стройки · 2 Новая стройка · 3 Методика (шаг 2) · 3а Методика объекта ·
 * 4 Камеры · 5 Обзор · 6 Наблюдения · 7 Отклонение.
 */
export const routes: RouteObject[] = [
  { index: true, element: <LandingPage /> },
  { path: 'login', element: <LoginPage /> },
  { path: 'register', element: <RegisterPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: 'sites', element: <SitesPage /> },
      { path: 'sites/new', element: <NewSitePage /> },
      { path: 'sites/:siteId/setup', element: <NewSitePage /> },
      { path: 'sites/:siteId/setup/methodology', element: <NewSiteMethodologyPage /> },
      { path: 'sites/:siteId', element: <SiteOverviewPage /> },
      { path: 'sites/:siteId/observations', element: <ObservationsPage /> },
      { path: 'sites/:siteId/methodology', element: <MethodologyPage /> },
      { path: 'sites/:siteId/cameras', element: <CamerasPage /> },
      { path: 'sites/:siteId/report', element: <ReportPage /> },
      { path: 'sites/:siteId/deviations/:deviationId', element: <DeviationPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

import { screen, within } from '@testing-library/react'
import { sites } from '@/mocks/fixtures'
import { renderRoute, renderWithProviders } from '@/test/render'
import { PageHeader, SectionHeader } from './PageHeader'
import { SiteShell } from './SiteShell'

describe('AppLayout', () => {
  it('renders the header navigation around the page', async () => {
    renderRoute('/sites')
    const nav = screen.getByRole('navigation', { name: 'Основная навигация' })
    expect(within(nav).getByRole('link', { name: 'Стройки' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('link', { name: 'LCT-7' })).toHaveAttribute('href', '/sites')
    expect(await screen.findByRole('heading', { level: 1, name: 'Стройки' })).toBeInTheDocument()
  })

  it('redirects the root to the sites list', async () => {
    const { router } = renderRoute('/')
    await screen.findByRole('heading', { name: 'Стройки' })
    expect(router.state.location.pathname).toBe('/sites')
  })
})

describe('PageHeader', () => {
  it('renders title, subtitle, actions and section headers', () => {
    renderWithProviders(
      <>
        <PageHeader title="Заголовок" subtitle="подзаголовок" actions={<button>Действие</button>} />
        <SectionHeader level={3} title="Раздел" description="пояснение" />
      </>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Заголовок' })).toBeInTheDocument()
    expect(screen.getByText('подзаголовок')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Действие' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Раздел' })).toBeInTheDocument()
  })
})

describe('SiteShell', () => {
  const site = sites[0]!

  it('shows site tabs with the active one', () => {
    renderWithProviders(
      <SiteShell site={site} crumb="Методика">
        тело
      </SiteShell>,
      { path: '/sites/:siteId/methodology', url: `/sites/${site.id}/methodology` },
    )
    const tabs = screen.getByRole('navigation', { name: 'Разделы объекта' })
    expect(
      within(tabs)
        .getAllByRole('link')
        .map((l) => l.textContent),
    ).toEqual(['Обзор', 'Наблюдения', 'Методика'])
    expect(within(tabs).getByRole('link', { name: 'Методика' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(tabs).getByRole('link', { name: 'Обзор' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: site.name })).toHaveAttribute(
      'href',
      `/sites/${site.id}`,
    )
    expect(screen.getByRole('heading', { level: 1, name: site.name })).toBeInTheDocument()
  })

  it('without a crumb the site itself is current', () => {
    renderWithProviders(<SiteShell site={site}>тело</SiteShell>)
    const crumbs = screen.getByRole('navigation', { name: 'Хлебные крошки' })
    expect(within(crumbs).getByText(site.name)).toHaveAttribute('aria-current', 'page')
  })
})

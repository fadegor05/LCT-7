import { screen, within } from '@testing-library/react'
import { renderRoute } from '@/test/render'

describe('DeviationPage', () => {
  it('shows a critical deviation with evidence, rule and limits', async () => {
    renderRoute('/sites/site-berezniki/deviations/dev-missing-pump')
    const title = 'Нет нужной техники · Устройство фундамента'
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    const crumbs = screen.getByRole('navigation', { name: 'Хлебные крошки' })
    expect(within(crumbs).getByText(title)).toHaveAttribute('aria-current', 'page')

    expect(screen.getByRole('link', { name: 'Устройство фундамента' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki',
    )
    expect(screen.getByText('ВТ 15.09.2026 — ПТ 18.09.2026')).toBeInTheDocument()
    expect(screen.getByText(/С 15\.09 на площадке автобетононасос/)).toBeInTheDocument()
    expect(screen.getByText(/только гусеничный экскаватор и самосвал/)).toBeInTheDocument()
    const evidence = screen.getAllByRole('img', { name: /Снимок-доказательство/ })
    expect(evidence).toHaveLength(2)
    expect(evidence[0]).toHaveStyle({
      backgroundImage: 'url(/api/sites/site-berezniki/photos/ph-9/annotated)',
    })
    expect(screen.getByRole('img', { name: 'Уверенность: высокая' })).toBeInTheDocument()
    expect(screen.getByText(/техника могла стоять вне кадра/)).toBeInTheDocument()

    const importance = screen.getByRole('complementary', { name: 'Важность' })
    expect(within(importance).getByText('Критично')).toBeInTheDocument()
    expect(within(importance).getByText(/Вывод верен, пока верны/)).toBeInTheDocument()
    const check = screen.getByRole('complementary', { name: 'Проверить' })
    expect(within(check).getByRole('link', { name: 'Наблюдения за ПТ 18.09' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/observations?date=2026-09-18',
    )
    expect(within(check).getByRole('link', { name: 'Методика этапа' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Методика этапа' })).toHaveLength(2)
  })

  it('pages through the site deviations in order of importance', async () => {
    const { user, router } = renderRoute('/sites/site-berezniki/deviations/dev-missing-pump')
    const nav = await screen.findByRole('navigation', { name: 'Листание отклонений' })
    expect(within(nav).getByText('1 из 3')).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: 'Предыдущее' })).not.toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: 'Предыдущее' })).toBeDisabled()
    await user.click(within(nav).getByRole('link', { name: 'Следующее' }))
    expect(router.state.location.pathname).toBe('/sites/site-berezniki/deviations/dev-idle-truck')
    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Простой техники (гипотеза) · Разработка котлована',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('Гипотеза', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText(/Гипотеза: есть косвенный признак/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Предыдущее' })).toBeInTheDocument()
  })

  it('disables «Следующее» on the last deviation', async () => {
    const { user } = renderRoute('/sites/site-berezniki/deviations/dev-missing-pump')
    const nav = await screen.findByRole('navigation', { name: 'Листание отклонений' })
    await user.click(within(nav).getByRole('link', { name: 'Следующее' }))
    await user.click(
      within(await screen.findByRole('navigation', { name: 'Листание отклонений' })).getByRole(
        'link',
        { name: 'Следующее' },
      ),
    )
    const last = await screen.findByRole('navigation', { name: 'Листание отклонений' })
    expect(await within(last).findByText('3 из 3')).toBeInTheDocument()
    expect(within(last).getByRole('button', { name: 'Следующее' })).toBeDisabled()
    expect(within(last).getByRole('link', { name: 'Предыдущее' })).toBeInTheDocument()
  })

  it('shows a deviation without a stage, rule or evidence', async () => {
    renderRoute('/sites/site-berezniki/deviations/dev-stale')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Нет прогресса' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Все этапы/)).toBeInTheDocument()
    expect(screen.getByText('Правило сервиса')).toBeInTheDocument()
    expect(screen.queryByText('Снимки-доказательства')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Методика этапа' })).not.toBeInTheDocument()
  })

  it('reports an unknown deviation', async () => {
    renderRoute('/sites/site-berezniki/deviations/nope')
    expect(await screen.findByText('Отклонение не найдено')).toBeInTheDocument()
  })
})

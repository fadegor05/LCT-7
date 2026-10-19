import { screen, waitFor, within } from '@testing-library/react'
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
    // Снимок забирается запросом с токеном и показывается из памяти.
    await waitFor(() => expect(evidence[0]).toHaveStyle({ backgroundImage: 'url(blob:test)' }))
    expect(screen.getByRole('img', { name: 'Уверенность: высокая' })).toBeInTheDocument()
    expect(screen.getByText(/техника могла стоять вне кадра/)).toBeInTheDocument()

    const importance = screen.getByRole('complementary', { name: 'Важность' })
    expect(within(importance).getByText('Критично')).toBeInTheDocument()
    expect(within(importance).getByText(/Вывод верен, пока верны/)).toBeInTheDocument()
    const check = screen.getByRole('complementary', { name: 'Проверить' })
    expect(
      within(check).getByRole('link', { name: 'Наблюдения за ПТ 18.09.2026' }),
    ).toHaveAttribute('href', '/sites/site-berezniki/observations?date=2026-09-18')
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

describe('DeviationPage: заголовок по машине и причина', () => {
  it('shows the machine title, captions, duration and the possible cause', async () => {
    const { server } = await import('@/mocks/server')
    const { http, HttpResponse } = await import('msw')
    server.use(
      http.get('/api/sites/:siteId/assessment/deviations/:id', () =>
        HttpResponse.json({
          id: 'dev-drill',
          stage_id: 'site-berezniki-stage-2',
          type: 'stage_mismatch',
          is_hypothesis: false,
          severity: 'critical',
          confidence: 'high',
          period_start: '2026-09-16',
          period_end: '2026-09-18',
          expected: 'Техника этапов, идущих по плану на 18.09: «Разработка котлована».',
          observed: 'Буровая установка (не менее 2) — техника этапа «Свайные работы».',
          limits_text: 'Не доказывает завершённость этапа.',
          rule_id: null,
          created_at: '2026-09-18T12:00:00Z',
          title: 'Буровая установка: техника этапа «Свайные работы»',
          equipment_type_id: 'eq-drill',
          cause_stage_id: 'site-berezniki-stage-1',
          evidence: [
            {
              photo_id: 'ph-1',
              detection_id: 'det-1',
              caption: 'К-2 · свайное поле: Буровая установка',
            },
          ],
        }),
      ),
    )
    renderRoute('/sites/site-berezniki/deviations/dev-drill')
    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Буровая установка: техника этапа «Свайные работы»',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('К-2 · свайное поле: Буровая установка')).toBeInTheDocument()
    expect(await screen.findByText('Возможная причина')).toBeInTheDocument()
    const importance = screen.getByRole('complementary', { name: 'Важность' })
    expect(within(importance).getByText('до 2 дн.')).toBeInTheDocument()
  })
})

describe('DeviationPage: отставание', () => {
  it('shows the stage delay interval, not the period length', async () => {
    const { server } = await import('@/mocks/server')
    const { http, HttpResponse } = await import('msw')
    const stage = 'site-berezniki-stage-2'
    server.use(
      http.get('/api/sites/:siteId/assessment/deviations/:id', () =>
        HttpResponse.json({
          id: 'dev-behind',
          stage_id: stage,
          type: 'behind_schedule',
          is_hypothesis: false,
          severity: 'critical',
          confidence: 'high',
          period_start: '2026-09-11',
          period_end: '2026-09-18',
          expected: 'Этап завершён по графику к 11.09.2026',
          observed: 'Маркерная техника видна и 18.09.2026, отставание 7 дн.',
          limits_text: 'Оценка по снимкам.',
          rule_id: null,
          created_at: '2026-09-18T12:00:00Z',
          title: 'Отставание: Свайные работы',
          evidence: [],
        }),
      ),
      http.get('/api/sites/:siteId/assessment/stages', () =>
        HttpResponse.json([
          {
            stage_id: stage,
            stage_name: 'Свайные работы',
            position: 2,
            status: 'behind',
            delay_days: 7,
            delay_min: 7,
            delay_max: 7,
            confidence: 'high',
            confidence_reason: null,
            computed_at: '2026-09-18T12:00:00Z',
          },
        ]),
      ),
    )
    renderRoute('/sites/site-berezniki/deviations/dev-behind')
    const importance = await screen.findByRole('complementary', { name: 'Важность' })
    // Точный интервал 7–7 — «7 дн.», а не «до 7 дн.» по длине периода
    expect(await within(importance).findByText('7 дн.')).toBeInTheDocument()
  })
})

describe('DeviationPage: решение инженера', () => {
  it('confirms, rejects into the archive and changes the decision', async () => {
    const { user } = renderRoute('/sites/site-berezniki/deviations/dev-idle-truck')
    const panel = await screen.findByRole('region', { name: 'Решение инженера' })
    await user.type(within(panel).getByLabelText('Комментарий (необязательно)'), 'видно по кадрам')
    await user.click(within(panel).getByRole('button', { name: 'Подтвердить простой' }))

    const done = await screen.findByRole('region', { name: 'Решение инженера' })
    expect(await within(done).findByText('Простой подтверждён')).toBeInTheDocument()
    expect(done).toHaveTextContent('Комментарий: видно по кадрам')

    await user.click(within(done).getByRole('button', { name: 'Изменить решение' }))
    const again = await screen.findByRole('button', { name: 'Простоя не было' })
    await user.click(again)
    expect(
      await screen.findByText('Ушло в архив, в списках и отчёте его нет', { exact: false }),
    ).toBeInTheDocument()
  })

  it('marks hypotheses awaiting a decision in the list', async () => {
    renderRoute('/sites/site-berezniki')
    const list = await screen.findByRole('list', { name: 'Отклонения' })
    expect(await within(list).findAllByText('Ждёт решения')).not.toHaveLength(0)
    expect(screen.getByText(/(ждёт|ждут) вашего решения/)).toBeInTheDocument()
  })
})

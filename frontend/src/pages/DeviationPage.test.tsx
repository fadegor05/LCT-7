import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('DeviationPage', () => {
  it('shows a critical deviation with evidence, rule and limits', async () => {
    renderRoute('/sites/site-berezniki/deviations/dev-missing-roller')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Каток не найден' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Жилой дом · Березники · данные на 18.09.2026')).toBeInTheDocument()
    expect(screen.getByText('Нет нужной техники')).toBeInTheDocument()
    expect(screen.getByText('15.09.2026 — 18.09.2026')).toBeInTheDocument()
    expect(screen.getByText(/Каток — не менее 1/)).toBeInTheDocument()
    expect(screen.getByText('Возможная причина')).toBeInTheDocument()
    expect(screen.getAllByRole('img', { name: /катка нет|зона пуста/ })).toHaveLength(3)
    expect(screen.getByText('Уплотнение щебёночного основания катком')).toBeInTheDocument()
    expect(screen.getByText('Чего это не доказывает')).toBeInTheDocument()
    expect(
      screen.queryByRole('complementary', { name: 'Решение инженера' }),
    ).not.toBeInTheDocument()

    const importance = screen.getByRole('complementary', { name: 'Важность' })
    expect(within(importance).getByText('Критично')).toBeInTheDocument()
    expect(within(importance).getByText('от 3 дн.')).toBeInTheDocument()
    const check = screen.getByRole('complementary', { name: 'Проверить' })
    expect(within(check).getByRole('link', { name: 'Наблюдения за 18.09' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/observations?date=2026-09-18',
    )

    const nav = await screen.findByRole('navigation', { name: 'Листание отклонений' })
    expect(nav).toHaveTextContent('1 из 3')
    expect(within(nav).queryByText('‹ Предыдущее')).not.toBeInTheDocument()
  })

  it('pages to the next deviation', async () => {
    const { user, router } = renderRoute('/sites/site-berezniki/deviations/dev-missing-roller')
    await user.click(await screen.findByRole('link', { name: 'Следующее ›' }))
    expect(router.state.location.pathname).toBe('/sites/site-berezniki/deviations/dev-idle-dump')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Самосвал простаивает у въезда' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '‹ Предыдущее' })).toBeInTheDocument()
  })

  it('confirms a hypothesis and changes the decision back', async () => {
    const { user } = renderRoute('/sites/site-berezniki/deviations/dev-idle-dump')
    const panel = await screen.findByRole('complementary', { name: 'Решение инженера' })
    expect(screen.getByText('Гипотеза')).toBeInTheDocument()
    expect(screen.getByText('Зона камеры К-2')).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: /Рабочая зона камеры К-2/ }).querySelector('polygon'),
    ).toBeInTheDocument()

    await user.type(within(panel).getByLabelText('Комментарий (необязательно)'), 'ждёт погрузки')
    await user.click(within(panel).getByRole('button', { name: 'Подтвердить простой' }))
    expect(await within(panel).findByText('Простой подтверждён')).toBeInTheDocument()
    expect(
      within(panel).getByText(
        /Решил: инженер \[ФИО\] · 21\.09\.2026 10:42\. Комментарий: ждёт погрузки\./,
      ),
    ).toBeInTheDocument()

    await user.click(within(panel).getByRole('button', { name: 'Изменить решение' }))
    expect(
      await within(panel).findByRole('button', { name: 'Простоя не было' }),
    ).toBeInTheDocument()
  })

  it('rejects a hypothesis — it leaves the lists', async () => {
    const { user } = renderRoute('/sites/site-berezniki/deviations/dev-idle-dump')
    const panel = await screen.findByRole('complementary', { name: 'Решение инженера' })
    await user.click(within(panel).getByRole('button', { name: 'Простоя не было' }))
    expect(await within(panel).findByText(/Ушло в архив/)).toBeInTheDocument()
    await vi.waitFor(() =>
      expect(
        screen.queryByRole('navigation', { name: 'Листание отклонений' }),
      ).not.toBeInTheDocument(),
    )
  })

  it('shows decision errors', async () => {
    server.use(
      http.post('/api/deviations/:id/decision', () =>
        HttpResponse.json({ detail: 'Сбой' }, { status: 500 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/deviations/dev-idle-dump')
    const panel = await screen.findByRole('complementary', { name: 'Решение инженера' })
    await user.click(within(panel).getByRole('button', { name: 'Подтвердить простой' }))
    expect(await within(panel).findByText('Сбой')).toBeInTheDocument()
  })

  it('uses generic wording for other hypotheses and service rules', async () => {
    server.use(
      http.get('/api/deviations/dev-x', () =>
        HttpResponse.json({
          id: 'dev-x',
          site_id: 'site-synthetic',
          site_name: 'Синтетический объект (демо)',
          type: 'extra_equipment',
          is_hypothesis: true,
          severity: 'attention',
          confidence: 'low',
          stage_id: null,
          stage_name: null,
          title: 'Лишний кран',
          detected_at: '2026-08-16T12:00:00+03:00',
          period_start: null,
          period_end: null,
          delay_days_min: null,
          delay_days_max: null,
          expected_text: 'e',
          observed_text: 'o',
          limits_text: 'l',
          severity_reason: 's',
          cause_text: null,
          confidence_reason: 'c',
          rule: null,
          camera_id: null,
          camera_name: null,
          observation_date: null,
          evidence: [],
          zone_polygon: null,
          decision: 'rejected',
          decision_record: {
            decision: 'rejected',
            comment: null,
            decided_by_name: 'инженер',
            decided_at: '2026-08-17T10:00:00+03:00',
          },
        }),
      ),
    )
    renderRoute('/sites/site-synthetic/deviations/dev-x')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Лишний кран' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Все этапы')).toBeInTheDocument()
    expect(screen.getByText('Правило сервиса')).toBeInTheDocument()
    expect(screen.getByText('Не подтверждается')).toBeInTheDocument()
    expect(
      within(screen.getByRole('complementary', { name: 'Проверить' })).getByRole('link', {
        name: 'Камеры',
      }),
    ).toBeInTheDocument()
  })
})

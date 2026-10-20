/// <reference types="node" />
/**
 * Тесты панели ассистента: монтирование, состояния статуса, успешные ответы,
 * ошибки (отмена, таймаут, переполнение, недоступность), повтор, история чата
 * в localStorage, печать.
 */
import { readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import * as db from '@/mocks/db'
import { BEREZNIKI } from '@/mocks/fixtures'
import { server } from '@/mocks/server'
import { renderWithProviders } from '@/test/render'
import type { AssistantAnswer } from '@/api/schemas'
import { AssistantPanel } from './AssistantPanel'
import { chatStorageKey, loadChat } from './chatHistory'

const __dirname = dirname(fileURLToPath(import.meta.url))
const css = readFileSync(resolve(__dirname, './AssistantPanel.module.css'), 'utf-8')

const ASK_URL = '/api/sites/:siteId/assistant/ask'

const answerBody: AssistantAnswer = {
  answer: 'Этап 1 «Подготовка» отстаёт на 3 дня.',
  verified: true,
  numbers_not_in_report: [],
  numbers_of_other_site: [],
  limits: 'Проверяются числа, а не смысл.',
  site_label: 'p1',
  stages: [{ ref: 'этап 1', stage_id: 'stage-1' }],
}

/**
 * Обработчик, отвечающий по команде теста: считает вызовы и видит аборт запроса.
 */
function gatedAsk() {
  const state = { calls: 0, aborted: false, release: () => {}, bodies: [] as unknown[] }
  const gate = new Promise<void>((resolve) => {
    state.release = resolve
  })
  server.use(
    http.post(ASK_URL, async ({ request }) => {
      state.calls += 1
      state.bodies.push(await request.json())
      request.signal.addEventListener('abort', () => {
        state.aborted = true
      })
      await gate
      return HttpResponse.json(answerBody)
    }),
  )
  return state
}

/**
 * Обработчик, считающий вызовы и запоминающий тело запроса.
 */
function countingAsk() {
  const state = { calls: 0, bodies: [] as unknown[] }
  server.use(
    http.post(ASK_URL, async ({ request }) => {
      state.calls += 1
      state.bodies.push(await request.json())
      return HttpResponse.json(answerBody)
    }),
  )
  return state
}

describe('AssistantPanel', () => {
  afterEach(() => vi.useRealTimers())

  describe('Hidden states', () => {
    it('показывает ничего пока статус загружается', () => {
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      // На первый рендер статус ещё в pending — ничего не показываем
      expect(screen.queryByRole('heading', { name: 'Ассистент по отчёту' })).not.toBeInTheDocument()
    })

    it('показывает колонку когда статус resolved с no_llm', async () => {
      db.setAssistantScenario('no_llm')
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      // Ждём, пока статус загрузится
      await vi.waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Ассистент по отчёту' })).toBeInTheDocument()
      })
      // Проверяем, что console.error не был вызван
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
      expect(spy.mock.calls).toHaveLength(0)
    })

    it('показывает колонку когда статус resolved с unavailable', async () => {
      db.setAssistantScenario('unavailable')
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await vi.waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Ассистент по отчёту' })).toBeInTheDocument()
      })
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
      expect(spy.mock.calls).toHaveLength(0)
    })

    it.each(['no_llm', 'unavailable'] as const)(
      'без языковой модели (%s) колонка видна, но спросить нельзя',
      async (scenario) => {
        const state = countingAsk()
        db.setAssistantScenario(scenario)
        const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
        expect(
          await screen.findByRole('heading', { name: 'Ассистент по отчёту' }),
        ).toBeInTheDocument()
        expect(screen.getByText('Ассистент не подключён')).toBeInTheDocument()
        expect(
          screen.getByText(/Языковая модель на сервере не настроена или недоступна/),
        ).toBeInTheDocument()
        const question = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
        expect(question).toBeDisabled()
        expect(screen.getByRole('button', { name: 'Спросить' })).toBeDisabled()
        const example = screen.getByRole('button', { name: 'где отставание и на сколько' })
        expect(example).toBeDisabled()
        await user.click(example)
        expect(question).toHaveValue('')
        expect(state.calls).toBe(0)
      },
    )

    it('не вызывает ask endpoint когда статус disabled', async () => {
      const state = countingAsk()
      db.setAssistantScenario('no_llm')
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      // Ждём, пока статус загрузится
      await vi.waitFor(() => {
        expect(
          screen.queryByRole('heading', { name: 'Ассистент по отчёту' }),
        ).not.toBeInTheDocument()
      })
      // Никакой запрос не должен быть отправлен
      expect(state.calls).toBe(0)
    })
  })

  describe('Enabled state', () => {
    it('показывает заголовок и форму когда включён', async () => {
      db.setAssistantScenario('ok')
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      expect(
        await screen.findByRole('heading', { name: 'Ассистент по отчёту' }),
      ).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: 'Вопрос по отчёту' })).toBeInTheDocument()
    })
  })

  describe('Success flow', () => {
    it('отправляет вопрос, показывает статус, затем ответ с ограничениями в переписке', async () => {
      const state = gatedAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      // Ждём загрузки заголовка
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      // Печатаем вопрос
      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      // Нажимаем "Спросить"
      const submit = screen.getByRole('button', { name: 'Спросить' })
      await user.click(submit)

      // Проверяем статус-лайн
      await screen.findByRole('status')

      // Отпускаем ответ
      state.release()

      // Проверяем, что ответ появился
      const answerDiv = await screen.findByRole('link')
      expect(answerDiv).toBeInTheDocument()

      // Проверяем, что ограничения видны
      expect(screen.getByText('Проверяются числа, а не смысл.')).toBeInTheDocument()

      // Проверяем, что есть ссылка на этап
      const stageLink = screen.getByRole('link')
      expect(stageLink).toHaveAttribute('href', expect.stringMatching(/^#stage-/))

      // Вопрос и ответ — сообщения в переписке, поле ввода очищено под следующий вопрос
      const log = screen.getByRole('log', { name: 'Переписка с ассистентом' })
      expect(within(log).getByText('Где отставание?')).toBeInTheDocument()
      expect(log.querySelector('[data-role="user"]')).toHaveTextContent('Где отставание?')
      expect(log.querySelector('[data-role="assistant"]')).toContainElement(stageLink)
      expect(textarea).toHaveValue('')
      // Фокус остаётся в поле: чат не уводит его на ответ
      expect(document.activeElement).not.toBe(stageLink.closest('[tabindex="-1"]'))
    })

    it('показывает alert когда ответ не прошёл проверку', async () => {
      db.setAssistantScenario('unverified')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Ответ не прошёл проверку')
      expect(alert).toHaveTextContent('999')
      expect(alert).toHaveTextContent('p1: 5')
    })

    it('не показывает alert когда ответ прошёл проверку', async () => {
      const state = gatedAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      // Ждём статус-лайна
      await screen.findByRole('status')

      state.release()

      // Ждём ответа (ссылка на этап)
      await screen.findByRole('link')

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  describe('Pending state', () => {
    it('отключает кнопку "Спросить" и показывает "Отменить" во время ожидания', async () => {
      const state = gatedAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      const submit = screen.getByRole('button', { name: 'Спросить' })
      await user.click(submit)

      // Кнопка должна быть отключена
      expect(submit).toBeDisabled()

      // Должна появиться кнопка "Отменить"
      expect(screen.getByRole('button', { name: 'Отменить' })).toBeInTheDocument()

      // Отменяем
      state.release()
    })

    it('отправляет ровно один запрос при двойном клике', async () => {
      const state = gatedAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      const submit = screen.getByRole('button', { name: 'Спросить' })
      // Двойной клик
      await user.click(submit)
      await user.click(submit)

      expect(state.calls).toBe(1)

      state.release()
    })

    it('отправляет ровно один запрос при Enter и повторном Enter', async () => {
      const state = gatedAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      // Нажимаем Enter дважды
      await user.keyboard('{Enter}{Enter}')

      expect(state.calls).toBe(1)

      state.release()
    })

    it('отменяет при нажатии "Отменить"', async () => {
      gatedAsk() // Sets up the gated handler; gate is never released to test cancel
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      const submit = screen.getByRole('button', { name: 'Спросить' })
      await user.click(submit)

      // Ждём, пока "Отменить" появится
      const cancel = await screen.findByRole('button', { name: 'Отменить' })
      await user.click(cancel)

      // Статус-лайн должен исчезнуть
      expect(screen.queryByText('Ассистент отвечает')).not.toBeInTheDocument()

      // Форма должна быть снова активна
      expect(submit).not.toBeDisabled()
      expect(screen.queryByRole('button', { name: 'Отменить' })).not.toBeInTheDocument()

      // Никакого текста ошибки
      expect(screen.queryByText(/Не удалось получить ответ/)).not.toBeInTheDocument()

      // Проверяем, что nет блока ошибки (cancelled не должен показывать ошибку)
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()

      // В переписке — вопрос и тихая пометка об отмене
      expect(await screen.findByText('Вопрос отменён')).toBeInTheDocument()
      expect(screen.getByText('Где отставание?')).toBeInTheDocument()
    })
  })

  describe('Error handling', () => {
    it('показывает таймаут с кнопкой "Повторить"', async () => {
      db.setAssistantScenario('timeout')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Модель не ответила')
      expect(alert).toHaveTextContent('Повторите вопрос позже')

      expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument()
    })

    it('повторяет ТОТ ЖЕ вопрос при нажатии "Повторить"', async () => {
      const bodies: unknown[] = []
      server.use(
        http.post(ASK_URL, async ({ request }) => {
          bodies.push(await request.json())
          return bodies.length < 2
            ? HttpResponse.json(
                {
                  detail: 'Модель не ответила. Повторите вопрос позже.',
                  code: 'assistant_timeout',
                },
                { status: 504 },
              )
            : HttpResponse.json(answerBody)
        }),
      )
      db.setAssistantScenario('ok')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Исходный вопрос')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      await screen.findByRole('alert')

      // Нажимаем "Повторить"
      await user.click(screen.getByRole('button', { name: 'Повторить' }))

      // Ошибка должна быть заменена на ответ (ищем ссылку на этап)
      await screen.findByRole('link')
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()

      // Проверяем, что оба запроса содержат ТОТ ЖЕ вопрос
      expect(bodies).toEqual([{ question: 'Исходный вопрос' }, { question: 'Исходный вопрос' }])
    })

    it('retry сохраняет исходный вопрос через несколько ошибок', async () => {
      const bodies: unknown[] = []
      server.use(
        http.post(ASK_URL, async ({ request }) => {
          bodies.push(await request.json())
          return bodies.length < 3
            ? HttpResponse.json(
                {
                  detail: 'Модель не ответила. Повторите вопрос позже.',
                  code: 'assistant_timeout',
                },
                { status: 504 },
              )
            : HttpResponse.json(answerBody)
        }),
      )
      db.setAssistantScenario('ok')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Мой вопрос')

      const button = screen.getByRole('button', { name: 'Спросить' })
      await user.click(button)

      // Первая ошибка (таймаут)
      await screen.findByRole('alert')
      let retryButton = screen.getByRole('button', { name: 'Повторить' })
      await user.click(retryButton)

      // Вторая ошибка (таймаут снова)
      await screen.findByRole('alert')
      retryButton = screen.getByRole('button', { name: 'Повторить' })

      // Нажимаем "Повторить" в третий раз - на этот раз успешно
      await user.click(retryButton)

      // Ждём ответа (ссылка на этап)
      await screen.findByRole('link')

      // Проверяем, что ошибка исчезла
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()

      // Все три запроса содержат ТОТ ЖЕ вопрос
      expect(bodies).toEqual([
        { question: 'Мой вопрос' },
        { question: 'Мой вопрос' },
        { question: 'Мой вопрос' },
      ])
    })

    it('после таймаута редактирование вопроса и повтор спрашивает новый вопрос', async () => {
      const bodies: unknown[] = []
      server.use(
        http.post(ASK_URL, async ({ request }) => {
          bodies.push(await request.json())
          return bodies.length < 3
            ? HttpResponse.json(
                {
                  detail: 'Модель не ответила. Повторите вопрос позже.',
                  code: 'assistant_timeout',
                },
                { status: 504 },
              )
            : HttpResponse.json(answerBody)
        }),
      )
      db.setAssistantScenario('ok')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Вопрос 1')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      // Первая ошибка (таймаут)
      await screen.findByRole('alert')

      // Редактируем вопрос
      await user.clear(textarea)
      await user.paste('Вопрос 2')

      // Отправляем новый вопрос (тоже таймаут)
      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      // Вторая ошибка (таймаут): в переписке теперь два отказа, «Повторить» — только у последнего
      await vi.waitFor(() => expect(screen.getAllByRole('alert')).toHaveLength(2))
      expect(screen.getAllByRole('button', { name: 'Повторить' })).toHaveLength(1)

      // Повторяем - должен спросить "Вопрос 2", который был последний отправлен
      await user.click(screen.getByRole('button', { name: 'Повторить' }))

      // Ждём ответа (ссылка на этап); первый отказ остаётся в истории
      await screen.findByRole('link')
      expect(screen.getAllByRole('alert')).toHaveLength(1)

      // Проверяем, что сохранялся последний вопрос, не первый
      expect(bodies).toEqual([
        { question: 'Вопрос 1' },
        { question: 'Вопрос 2' },
        { question: 'Вопрос 2' },
      ])
    })

    it('показывает rate_limited без "Повторить"', async () => {
      db.setAssistantScenario('rate_limited')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Слишком много вопросов')

      // Но нет кнопки "Повторить"
      expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument()
    })

    it('показывает out_of_scope без "Повторить"', async () => {
      db.setAssistantScenario('out_of_scope')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Расскажи мне политику')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Ассистент отвечает только на вопросы по отчёту')

      expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument()
    })

    it('показывает too_large без "Повторить"', async () => {
      db.setAssistantScenario('too_large')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Отчёт слишком велик')

      expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument()
    })

    it('показывает bad_request (HTTP 400) с точным заголовком и без "Повторить"', async () => {
      server.use(
        http.post(ASK_URL, () =>
          HttpResponse.json(
            { detail: 'Ассистент не принял запрос', code: 'assistant_bad_request' },
            { status: 400 },
          ),
        ),
      )
      db.setAssistantScenario('ok')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      const alert = await screen.findByRole('alert')
      // Точный заголовок (не 'отчёта')
      expect(alert).toHaveTextContent('Площадки нет в отчёте')
      // Сообщение сервера показано
      expect(alert).toHaveTextContent('Ассистент не принял запрос')

      // Но нет кнопки "Повторить"
      expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument()
    })

    it('при недоступности на вопрос пишет отказ в переписку, чат остаётся', async () => {
      db.setAssistantScenario('ok')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('Где отставание?')

      // Меняем сценарий на unavailable
      db.setAssistantScenario('unavailable')

      await user.click(screen.getByRole('button', { name: 'Спросить' }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Ассистент недоступен')
      expect(screen.getByRole('heading', { name: 'Ассистент по отчёту' })).toBeInTheDocument()
      expect(screen.getByText('Где отставание?')).toBeInTheDocument()
    })
  })

  describe('Validation', () => {
    it('показывает ошибку при коротком вопросе и не отправляет', async () => {
      const state = countingAsk()
      db.setAssistantScenario('ok')
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)

      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste('ab')

      const submit = screen.getByRole('button', { name: 'Спросить' })
      await user.click(submit)

      // Ошибка должна быть показана в поле
      expect(screen.getByText('Вопрос должен быть от 3 до 500 символов')).toBeInTheDocument()

      // Запрос не должен быть отправлен
      expect(state.calls).toBe(0)
    })
  })

  describe('История в localStorage', () => {
    async function askOnce(user: ReturnType<typeof renderWithProviders>['user'], q: string) {
      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      await user.click(textarea)
      await user.paste(q)
      await user.click(screen.getByRole('button', { name: 'Спросить' }))
    }

    it('сохраняет вопрос и ответ в localStorage по стройке, sessionStorage не трогает', async () => {
      countingAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      await askOnce(user, 'Где отставание?')
      await screen.findByRole('link')

      await vi.waitFor(() => expect(loadChat(BEREZNIKI)).toHaveLength(2))
      const [question, reply] = loadChat(BEREZNIKI)
      expect(question).toMatchObject({ role: 'user', text: 'Где отставание?' })
      expect(reply).toMatchObject({ role: 'assistant', answer: answerBody })
      expect(sessionStorage.length).toBe(0)
    })

    it('восстанавливает переписку после перемонтирования', async () => {
      countingAsk()
      const view = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      await askOnce(view.user, 'Где отставание?')
      await screen.findByRole('link')
      view.unmount()

      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      const log = await screen.findByRole('log', { name: 'Переписка с ассистентом' })
      expect(within(log).getByText('Где отставание?')).toBeInTheDocument()
      expect(within(log).getByRole('link')).toHaveAttribute('href', '#stage-stage-1')
      // Переписка есть — примеры вопросов не показываются
      expect(screen.queryByRole('button', { name: 'что с этой площадкой' })).not.toBeInTheDocument()
    })

    it('не показывает переписку другой стройки', async () => {
      localStorage.setItem(
        chatStorageKey('other-site'),
        JSON.stringify([
          { id: '1', at: '2026-01-01T10:00:00Z', role: 'user', text: 'Чужой вопрос' },
        ]),
      )
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      expect(screen.queryByText('Чужой вопрос')).not.toBeInTheDocument()
      expect(screen.getByText(/История переписки сохраняется в этом браузере/)).toBeInTheDocument()
    })

    it('игнорирует битые данные в localStorage', async () => {
      localStorage.setItem(chatStorageKey(BEREZNIKI), '{не json')
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      expect(screen.getByText(/История переписки сохраняется/)).toBeInTheDocument()
    })

    it('«Очистить» удаляет переписку и ключ из localStorage', async () => {
      countingAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      expect(screen.queryByRole('button', { name: 'Очистить' })).not.toBeInTheDocument()

      await askOnce(user, 'Где отставание?')
      await screen.findByRole('link')

      await user.click(screen.getByRole('button', { name: 'Очистить' }))
      expect(screen.queryByText('Где отставание?')).not.toBeInTheDocument()
      await vi.waitFor(() => expect(localStorage.getItem(chatStorageKey(BEREZNIKI))).toBeNull())
    })
  })

  describe('Accessibility', () => {
    it('содержит aria-live для объявления ошибок screen reader', async () => {
      db.setAssistantScenario('ok')
      renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      const liveRegion = screen.getByRole('log', { name: 'Переписка с ассистентом' })
      expect(liveRegion).toHaveAttribute('aria-live', 'polite')
    })
  })

  describe('CSS print rule', () => {
    it('применяет класс section с media print rule', async () => {
      db.setAssistantScenario('ok')
      const { container } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      // Проверяем, что CSS содержит media print rule, скрывающее section
      expect(css).toMatch(/@media print\s*\{[\s\S]*?\.section\s*\{[\s\S]*?display:\s*none/)

      // Проверяем, что rendered section имеет класс section
      const section = container.querySelector('section.section')
      expect(section).toBeInTheDocument()
    })
  })

  describe('Развёрнутый чат', () => {
    it('«Развернуть» открывает чат в широком окне, не дублируя поле вопроса', async () => {
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })

      await user.click(screen.getByRole('button', { name: 'Развернуть' }))

      const dialog = screen.getByRole('dialog', { name: 'Ассистент по отчёту' })
      expect(within(dialog).getByRole('textbox', { name: 'Вопрос по отчёту' })).toBeInTheDocument()
      expect(within(dialog).getByRole('log', { name: 'Переписка с ассистентом' })).toBeVisible()
      // Чат один: в колонке остаётся только заголовок с пояснением
      expect(screen.getAllByRole('textbox')).toHaveLength(1)
      expect(screen.getByText('Чат открыт в отдельном окне')).toBeInTheDocument()
    })

    it('вопрос из развёрнутого окна получает ответ, а после закрытия переписка в колонке', async () => {
      countingAsk()
      const { user } = renderWithProviders(<AssistantPanel siteId={BEREZNIKI} />)
      await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      await user.click(screen.getByRole('button', { name: 'Развернуть' }))
      const dialog = screen.getByRole('dialog', { name: 'Ассистент по отчёту' })

      await user.type(
        within(dialog).getByRole('textbox', { name: 'Вопрос по отчёту' }),
        'где отставание',
      )
      await user.click(within(dialog).getByRole('button', { name: 'Спросить' }))
      expect(await within(dialog).findByText(/отстаёт на 3 дня/)).toBeInTheDocument()

      await user.click(within(dialog).getByRole('button', { name: 'Закрыть' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      const log = screen.getByRole('log', { name: 'Переписка с ассистентом' })
      expect(within(log).getByText(/отстаёт на 3 дня/)).toBeInTheDocument()
      expect(screen.queryByText('Чат открыт в отдельном окне')).not.toBeInTheDocument()
    })
  })
})

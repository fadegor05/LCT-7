import { act, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import {
  Audience,
  Compare,
  Demo,
  Facts,
  Faq,
  FinalCta,
  HowItWorks,
  Proof,
  SiteHeader,
  Timeline,
  Trust,
} from './Sections'
import { NAV } from './nav'

function all() {
  return render(
    <MemoryRouter>
      <SiteHeader />
      <Facts />
      <Timeline />
      <HowItWorks />
      <Demo />
      <Trust />
      <Proof />
      <Compare />
      <Audience />
      <Faq />
      <FinalCta />
    </MemoryRouter>,
  )
}

describe('landing sections', () => {
  it('links the header menu to real anchors on the page', () => {
    const { container } = all()
    const menu = screen.getByRole('navigation', { name: 'Разделы страницы' })
    for (const item of NAV) {
      expect(within(menu).getByRole('link', { name: item.label })).toHaveAttribute(
        'href',
        item.href,
      )
      expect(container.querySelector(item.href)).toBeInTheDocument()
    }
  })

  it('numbers the sections in the left margin like a journal', () => {
    all()
    const timeline = screen.getByRole('region', { name: 'Так отставание видно во времени' })
    expect(within(timeline).getByText('02')).toBeInTheDocument()
    expect(within(timeline).getByText('Как видно')).toBeInTheDocument()
  })

  it('states the context with sources', () => {
    all()
    expect(screen.getByText(/1 795/)).toBeInTheDocument()
    expect(screen.getByText('Вручную')).toBeInTheDocument()
    expect(screen.getByText(/mskagency\.ru\/materials\/3489311/)).toBeInTheDocument()
  })

  it('ties every measured number to something a visitor knows, with a caveat in the same row', () => {
    all()
    const proof = screen.getByRole('region', { name: 'Проверили на настоящих стройках' })
    const rows = within(proof).getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    const [statuses, machines, speed] = rows
    expect(within(statuses!).getByText('19 из 20')).toBeInTheDocument()
    expect(within(statuses!).getByText(/Одно расхождение есть/)).toBeInTheDocument()
    expect(within(machines!).getByText('2 из 3')).toBeInTheDocument()
    expect(within(machines!).getByText(/а не на одну рамку/)).toBeInTheDocument()
    expect(within(speed!).getByText('0,4 с')).toBeInTheDocument()
    expect(within(speed!).getByText(/3 600 проверок/)).toBeInTheDocument()
  })

  it('speaks the visitor language, not the team jargon', () => {
    const { container } = all()
    const text = container.textContent ?? ''
    for (const jargon of [
      'mAP',
      'deploy-tunnel',
      '.md',
      'Ultralytics',
      'маркер',
      'мс на кадр',
      'Демо-площадка p03',
      'потолок согласия',
    ]) {
      expect(text).not.toContain(jargon)
    }
  })

  it('lists what makes a conclusion checkable', () => {
    all()
    const trust = screen.getByRole('region', { name: 'Вывод всегда можно проверить' })
    expect(
      within(trust)
        .getAllByRole('term')
        .map((t) => t.textContent),
    ).toEqual(['01Кадр', '02Правило', '03Уверенность', '04Границы'])
    expect(within(trust).getByText(/При «Не начат» работ на стройке нет/)).toBeInTheDocument()
  })

  it('compares with the market in one table, ручной осмотр included', () => {
    all()
    const tables = screen.getAllByRole('table')
    expect(tables).toHaveLength(1)
    const market = tables[0]!
    expect(within(market).getByRole('columnheader', { name: 'Ручной осмотр' })).toBeInTheDocument()
    expect(within(market).getByRole('rowheader', { name: 'Нужен ли BIM' })).toBeInTheDocument()
    expect(within(market).getAllByText('Не раскрыто')).toHaveLength(2)
    expect(screen.queryByText(/Наш вход беднее/)).toBeNull()
  })

  it('keeps the example free of captions and hints', () => {
    all()
    const demo = screen.getByRole('region', { name: 'Посмотрите на настоящем объекте' })
    expect(within(demo).queryByText(/Любой вывод проверяется в два шага/)).toBeNull()
    expect(within(demo).queryByText(/Прогноза сроков/)).toBeNull()
  })

  it('puts a photo into each fact', () => {
    all()
    const context = screen.getByRole('region', { name: /Камеры на стройках/ })
    expect(within(context).getAllByRole('img')).toHaveLength(2)
  })

  it('shows a mini screen above every step and a photo with a hint for every audience', () => {
    all()
    const how = screen.getByRole('region', { name: 'Три шага от графика до вывода' })
    expect(within(how).getAllByRole('img').length).toBeGreaterThanOrEqual(3)
    const audience = screen.getByRole('region', { name: 'Кому это нужно' })
    expect(within(audience).getAllByRole('img')).toHaveLength(3)
    for (const photo of within(audience).getAllByRole('img')) {
      expect(photo).toHaveAttribute('src', expect.stringMatching(/^\/landing\/p03\/.+\.jpg$/))
    }
  })

  it('answers the objections, with the first question open', () => {
    const { container } = all()
    const faq = screen.getByRole('region', { name: 'Вопросы, которые обычно задают первыми' })
    expect(within(faq).getAllByText(/\?$/)).toHaveLength(4)
    const details = container.querySelectorAll('details')
    expect(details[0]).toHaveAttribute('open')
    expect(details[1]).not.toHaveAttribute('open')
    expect(within(faq).getByText(/снимки туда не уходят/)).toBeInTheDocument()
  })

  it('shows three audiences', () => {
    all()
    const audience = screen.getByRole('region', { name: 'Кому это нужно' })
    expect(within(audience).getAllByRole('heading', { level: 3 })).toHaveLength(3)
  })

  it('says nothing about licences, open code or price', () => {
    const { container } = all()
    const text = container.textContent ?? ''
    for (const word of [
      'AGPL',
      'Открытый код',
      'Код открыт',
      'исходник',
      'лицензи',
      'Сколько это стоит',
    ]) {
      expect(text).not.toContain(word)
    }
    expect(screen.queryByRole('region', { name: /Ставится у вас/ })).toBeNull()
  })

  it('hides the pilot contact and the repository link until the team sets them', () => {
    all()
    expect(screen.queryByRole('link', { name: 'Запросить пилот' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Исходный код' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Попробовать самому' })).toHaveAttribute(
      'href',
      '/register',
    )
  })

  it('shows the product window next to the final call instead of a stock picture', () => {
    all()
    const pilot = screen.getByRole('region', { name: 'Покажем на вашем графике' })
    expect(within(pilot).getByRole('img', { name: /Экран «Обзор» Вехи/ })).toBeInTheDocument()
    expect(screen.queryByText(/pngimg/)).toBeNull()
  })

  it('does not promise what the stand cannot show', () => {
    const { container } = all()
    const text = container.textContent ?? ''
    for (const banned of [
      'процент готовности показываем',
      '₽',
      'руб.',
      'внедрено',
      'точность 44',
    ]) {
      expect(text).not.toContain(banned)
    }
    // длинное тире и математические знаки в текстах лендинга запрещены правилами редактуры
    expect(text).not.toContain('—')
  })
})

describe('reveal on scroll', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('keeps a section hidden until it enters the window, then shows it once', () => {
    let notify: (entries: Partial<IntersectionObserverEntry>[]) => void = () => {}
    const disconnect = vi.fn()
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(cb: typeof notify) {
          notify = cb
        }
        observe() {}
        disconnect = disconnect
      },
    )
    render(
      <MemoryRouter>
        <Facts />
      </MemoryRouter>,
    )
    const section = screen.getByRole('region', { name: /Камеры на стройках/ })
    expect(section).toHaveClass('unseen')
    act(() => notify([{ isIntersecting: false }]))
    expect(section).toHaveClass('unseen')
    act(() => notify([{ isIntersecting: true }]))
    expect(section).toHaveClass('seen')
    expect(disconnect).toHaveBeenCalled()
  })

  it('shows everything at once when the system asks for less motion', () => {
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        observe() {}
        disconnect() {}
      },
    )
    vi.stubGlobal(
      'matchMedia',
      vi.fn((q: string) => ({ matches: q.includes('reduce') })),
    )
    render(
      <MemoryRouter>
        <Facts />
      </MemoryRouter>,
    )
    expect(screen.getByRole('region', { name: /Камеры на стройках/ })).toHaveClass('seen')
  })
})

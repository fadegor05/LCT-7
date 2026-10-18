import { useRef, type ReactNode } from 'react'
import { ButtonLink } from '@/components/ui/Button'
import { buttonClassName } from '@/components/ui/buttonClass'
import { Logo } from '@/components/ui/Logo'
import { PhotosArt, ScheduleArt, StatusArt } from './Art'
import { PILOT_CONTACT } from './config'
import { GanttBackdrop } from './GanttBackdrop'
import { LiveDemo } from './LiveDemo'
import { NAV } from './nav'
import { PinnedTimeline } from './PinnedTimeline'
import { ProductWindow } from './ProductWindow'
import { useCursorParallax } from './useParallax'
import { useInView } from './useScroll'
import { InspectorShot, ItShot, SupervisorShot } from './Visuals'
import styles from './Sections.module.css'

interface SectionProps {
  id: string
  /** Номер и рубрика в левом поле, как в журнале. */
  index: string
  label: string
  title: string
  lead?: string
  /** Содержимое на всю ширину, а не в правой колонке. */
  wide?: boolean
  children: ReactNode
}

/** Секция с левым полем (номер и рубрика) и правой колонкой. Блок проявляется один раз при входе в окно. */
function Section({ id, index, label, title, lead, wide = false, children }: SectionProps) {
  const ref = useRef<HTMLElement>(null)
  const seen = useInView(ref)
  return (
    <section
      id={id}
      ref={ref}
      className={`${styles.section} ${seen ? styles.seen : styles.unseen}`}
      aria-labelledby={`${id}-h`}
    >
      <div className={styles.inner}>
        <p className={styles.side}>
          <span>{index}</span>
          {label}
        </p>
        <div className={styles.head}>
          <h2 id={`${id}-h`} className={styles.h2}>
            {title}
          </h2>
          {lead ? <p className={styles.lead}>{lead}</p> : null}
        </div>
        <div className={wide ? styles.bodyWide : styles.body}>{children}</div>
      </div>
    </section>
  )
}

/** Липкая шапка: меню по якорям и вход. Кнопки входа всегда на виду. */
export function SiteHeader() {
  return (
    <header className={styles.header}>
      <a href="#top" className={styles.brand}>
        <Logo />
        Веха
      </a>
      <nav className={styles.nav} aria-label="Разделы страницы">
        {NAV.map((n) => (
          <a key={n.href} href={n.href}>
            {n.label}
          </a>
        ))}
      </nav>
      <div className={styles.headerCta}>
        <ButtonLink to="/login" variant="ghost" size="sm" className={styles.login}>
          Войти
        </ButtonLink>
        <ButtonLink to="/register" size="sm">
          Попробовать
        </ButtonLink>
      </div>
    </header>
  )
}

export function Facts() {
  return (
    <Section
      id="context"
      index="01"
      label="Контекст"
      title="Камеры на стройках уже есть. Ответа «идёт ли по графику» нет"
      lead="Ход работ по-прежнему проверяют вручную. Инспектор смотрит кадры и звонит подрядчику, поэтому отставание находят поздно."
    >
      <ul className={styles.ledger}>
        <li>
          <img
            className={styles.factPhoto}
            src="/landing/p03/fact-1.jpg"
            alt="Строительная площадка сверху: котлован среди городских кварталов"
            loading="lazy"
            width="960"
          />
          <b className={styles.big}>
            1 795<i> проверок</i>
          </b>
          <p>За первые полгода, по всей Москве. На каждой нужно сверить стройку с графиком.</p>
          <small>Агентство городских новостей «Москва», mskagency.ru/materials/3489311</small>
        </li>
        <li>
          <img
            className={styles.factPhoto}
            src="/landing/p03/fact-2.jpg"
            alt="Рабочие на заснеженной площадке рядом со сваебойной установкой"
            loading="lazy"
            width="960"
          />
          <b className={`${styles.big} ${styles.warn}`}>Вручную</b>
          <p>Снимки сверяют с календарным графиком глазами. Это долго и зависит от человека.</p>
        </li>
      </ul>
    </Section>
  )
}

export function Timeline() {
  return (
    <Section
      id="timeline"
      index="02"
      label="Как видно"
      title="Так отставание видно во времени"
      lead="Листайте. Линия даты идёт по графику настоящей стройки, на датах появляются снимки с неё, а Веха сверяет их с планом."
      wide
    >
      <PinnedTimeline />
    </Section>
  )
}

const STEPS = [
  {
    title: 'Загрузите график',
    text: 'CSV или Excel. Веха разобьёт работы на крупные этапы и покажет, какие из них можно проверить по технике.',
    art: <ScheduleArt />,
  },
  {
    title: 'Добавьте снимки',
    text: 'Дату и время она возьмёт из метаданных или со штампа в кадре. Если не сможет, спросит у вас и не станет угадывать.',
    art: <PhotosArt />,
  },
  {
    title: 'Получите статус каждого этапа',
    text: 'Идёт по плану, опережает, отстаёт на столько-то дней, не начат или не наблюдался. К каждому выводу кадр и правило.',
    art: <StatusArt />,
  },
]

export function HowItWorks() {
  return (
    <Section id="how" index="03" label="Как работает" title="Три шага от графика до вывода">
      <ol className={styles.steps}>
        {STEPS.map((s, i) => (
          <li key={s.title}>
            <div className={styles.art}>{s.art}</div>
            <span className={styles.num}>0{i + 1}</span>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
          </li>
        ))}
      </ol>
      <p className={styles.note}>
        Правка графика или методики пересчитывает все выводы заново, снимки повторно обрабатывать не
        нужно.
      </p>
    </Section>
  )
}

export function Demo() {
  return (
    <Section
      id="demo"
      index="04"
      label="Пример"
      title="Посмотрите на настоящем объекте"
      lead="Настоящая стройка: её календарный график и снимки, которых модель при обучении не видела. Регистрация не нужна."
      wide
    >
      <LiveDemo />
    </Section>
  )
}

const TRUST = [
  {
    title: 'Кадр',
    text: 'Каждый вывод привязан к снимкам с рамками на технике.',
  },
  {
    title: 'Правило',
    text: 'Какая техника ожидалась на этапе и откуда взято требование: расценка ГЭСН или логика работы.',
  },
  {
    title: 'Уверенность',
    text: 'Высокая, средняя или низкая, с причиной. Низкая уверенность не даёт статуса «критично».',
  },
  {
    title: 'Границы',
    text: 'У каждого отклонения написано, чего сервис утверждать не вправе. Отсутствие самосвалов не доказывает остановку вывоза грунта.',
  },
]

export function Trust() {
  return (
    <Section id="trust" index="05" label="Почему верить" title="Вывод всегда можно проверить">
      <dl className={styles.defs}>
        {TRUST.map((t, i) => (
          <div key={t.title}>
            <dt>
              <span>0{i + 1}</span>
              {t.title}
            </dt>
            <dd>{t.text}</dd>
          </div>
        ))}
      </dl>
      <p className={styles.quote}>
        При «Не начат» работ на стройке нет. При «Не наблюдалось» не хватает снимков. Одно мы не
        выдаём за другое.
      </p>
    </Section>
  )
}

/** Цифры привязаны к тому, что человек видит на странице: стройки, снимки, проверки из блока «Контекст». */
const PROOF = [
  {
    value: '19 из 20',
    label: 'этапов получили тот же статус, что и при ручной разметке техники на тех же снимках',
    caveat: 'Одно расхождение есть. Оно разобрано в документации проекта, а не спрятано.',
  },
  {
    value: '2 из 3',
    label: 'машин на снимке сервис находит сам, на стройках, которых не видел при обучении',
    caveat:
      'Поэтому вывод по этапу опирается на все снимки за период и на технику, характерную для этапа, а не на одну рамку.',
  },
  {
    value: '0,4 с',
    label: 'на снимок на обычном ноутбуке, видеокарта не нужна',
    caveat:
      'Годовой объём надзора по Москве, около 3 600 проверок по сотне снимков, один компьютер разберёт примерно за полтора дня.',
  },
]

export function Proof() {
  return (
    <Section
      id="proof"
      index="06"
      label="Измерено"
      title="Проверили на настоящих стройках"
      lead="Площадки для проверки модель при обучении не видела."
    >
      <ul className={styles.proof}>
        {PROOF.map((p) => (
          <li key={p.value}>
            <b className={styles.proofValue}>{p.value}</b>
            <span className={styles.proofLabel}>{p.label}</span>
            <small>{p.caveat}</small>
          </li>
        ))}
      </ul>
    </Section>
  )
}

const MARKET_HEAD = [
  'Веха',
  'Ручной осмотр',
  'BIM и обход площадки',
  'BIM и лазерный скан',
  'Видеоаналитика по охране труда',
]

const MARKET = [
  {
    row: 'Что нужно на входе',
    cells: [
      'Календарный график и обычные снимки',
      'Выезд на площадку и звонок подрядчику',
      'Модель BIM и обход с 360-камерой',
      'Модель BIM и лазерный скан',
      'Видеопоток с камер',
    ],
  },
  { row: 'Нужен ли BIM', cells: ['Нет', 'Нет', 'Да', 'Да', 'Нет'] },
  {
    row: 'Отвечает «идёт ли по графику»',
    cells: [
      'Да, по этапам, в днях',
      'Да, на глаз',
      'Сравнивает с моделью BIM',
      'Да, по геометрии',
      'Нет, ищет нарушения',
    ],
  },
  {
    row: 'Показывает кадр-доказательство',
    cells: ['Да, на каждый вывод', 'Не всегда', 'Да', 'Да', 'Да, по нарушению'],
  },
  {
    row: 'Отличает «работ нет» от «плохо видно»',
    cells: ['Да', 'Нет', 'Не раскрыто', 'Не раскрыто', 'Нет'],
  },
]

export function Compare() {
  return (
    <Section
      id="compare"
      index="07"
      label="Сравнение"
      title="Чем Веха отличается от привычного и от продуктов рынка"
      wide
    >
      <table className={styles.table}>
        <caption className={styles.srOnly}>
          Сравнение Вехи с ручным осмотром и классами продуктов рынка
        </caption>
        <thead>
          <tr>
            <th scope="col">&nbsp;</th>
            {MARKET_HEAD.map((h, i) => (
              <th key={h} scope="col" className={i === 0 ? styles.usHead : undefined}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {MARKET.map((r) => (
            <tr key={r.row}>
              <th scope="row">{r.row}</th>
              {r.cells.map((c, i) => (
                <td
                  key={MARKET_HEAD[i]}
                  data-label={MARKET_HEAD[i]}
                  className={i === 0 ? styles.us : undefined}
                >
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}

const AUDIENCE = [
  {
    title: 'Инспектор, надзор',
    text: 'Список объектов с итогом и критичными отклонениями. Видно, куда смотреть в первую очередь. Объект без свежих снимков не выглядит благополучным.',
    shot: <InspectorShot />,
  },
  {
    title: 'Технадзор и руководитель проекта',
    text: 'Отставание по этапам и кадры для разговора с подрядчиком. Методика правится под ваш объект, пересчёт мгновенный.',
    shot: <SupervisorShot />,
  },
  {
    title: 'ИТ и департамент данных',
    text: 'Ставится на ваш сервер, работает на обычном процессоре без видеокарты. Выгрузки CSV, XLSX и печатная версия.',
    shot: <ItShot />,
  },
]

export function Audience() {
  return (
    <Section id="audience" index="08" label="Для кого" title="Кому это нужно" wide>
      <ul className={styles.cols}>
        {AUDIENCE.map((a) => (
          <li key={a.title}>
            {a.shot}
            <h3>{a.title}</h3>
            <p>{a.text}</p>
          </li>
        ))}
      </ul>
    </Section>
  )
}

const FAQ = [
  {
    q: 'Что если Веха ошибётся?',
    a: 'Вывод по этапу строится на технике, характерной для этапа, например буровой установке для свай, и показывается интервалом, а не точным числом. Низкая уверенность понижает важность. Решение остаётся за инженером: гипотезы он подтверждает или отклоняет сам.',
  },
  {
    q: 'Нужны ли особые камеры или BIM?',
    a: 'Нет. Нужны график таблицей и снимки. Подойдут камеры, которые уже стоят. Чем чаще съёмка, тем точнее срок: точность не выше частоты кадров, и сервис это показывает.',
  },
  {
    q: 'Что если снимков мало или площадка видна плохо?',
    a: 'Сервис оценивает, насколько хорошо площадка видна на снимках. Если видна плохо, он пишет, что участок вне контроля, и не делает вывод «работы не ведутся».',
  },
  {
    q: 'Где хранятся данные?',
    a: 'Снимки и графики лежат на сервере, где развёрнута Веха: у вас, если вы ставите её у себя. Оригиналы снимков не меняются. Каждая стройка видна только тому, кто её завёл. Пароли хранятся в виде хеша, частота попыток входа ограничена. Вопросы ассистенту и разбор графика языковой моделью отправляют текст отчёта или строки таблицы выбранному вами провайдеру модели, снимки туда не уходят. Без настроенной модели эти две функции выключены, остальное работает.',
  },
]

export function Faq() {
  return (
    <Section id="faq" index="09" label="Вопросы" title="Вопросы, которые обычно задают первыми">
      <div className={styles.faq}>
        {FAQ.map((f, i) => (
          <details key={f.q} open={i === 0}>
            <summary>{f.q}</summary>
            <p>{f.a}</p>
          </details>
        ))}
      </div>
    </Section>
  )
}

export function FinalCta() {
  const panel = useRef<HTMLDivElement>(null)
  useCursorParallax(panel)
  return (
    <section id="pilot" className={styles.final} aria-labelledby="pilot-h">
      <div ref={panel} className={styles.finalPanel}>
        <div className={styles.finalGantt}>
          <GanttBackdrop labels={false} />
        </div>
        <div className={styles.finalVeil} aria-hidden="true" />
        <div className={styles.finalWin}>
          <ProductWindow />
        </div>
        <div className={styles.finalCopy}>
          <h2 id="pilot-h" className={styles.finalTitle}>
            Покажем на вашем графике
          </h2>
          <p className={styles.lead}>
            Пришлите график работ и несколько снимков с площадки. Покажем статусы этапов и
            кадры-доказательства.
          </p>
          <div className={styles.finalCta}>
            <ButtonLink to="/register" size="lg">
              Попробовать самому
            </ButtonLink>
            {PILOT_CONTACT ? (
              <a href={PILOT_CONTACT} className={buttonClassName('ghost', 'lg')}>
                Запросить пилот
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  )
}

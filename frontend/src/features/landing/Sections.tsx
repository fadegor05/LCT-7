import { useRef, type ReactNode } from 'react'
import { Link } from 'react-router'
import { Logo } from '@/components/ui/Logo'
import { PhotosArt, ScheduleArt, StatusArt } from './Art'
import { PILOT_CONTACT, REPO_URL } from './config'
import { LiveDemo } from './LiveDemo'
import { NAV } from './nav'
import { PinnedTimeline } from './PinnedTimeline'
import { ProductWindow } from './ProductWindow'
import { useInView } from './useScroll'
import { CodeArt, CpuArt, InspectorShot, ItShot, RunArt, SupervisorShot } from './Visuals'
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
        <Link to="/login" className={styles.ghostSm}>
          Войти
        </Link>
        <Link to="/register" className={styles.primarySm}>
          Попробовать
        </Link>
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
      lead="Листайте. Линия среза идёт по плану площадки p03, на датах появляются настоящие снимки, а Веха сверяет их с графиком."
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
      lead="Демо-площадка p03: календарный график и снимки, которых модель при обучении не видела. Регистрация не нужна."
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

const PROOF = [
  {
    value: '19 из 20',
    label: 'статусов этапов совпали с эталоном',
    caveat: 'Цепочка ML на демо-наборе. На стенде расхождения есть, они описаны в тестах проекта.',
  },
  {
    value: '0.445',
    label: 'mAP50 на площадках, которых модель не видела',
    caveat:
      '28 кадров, 215 рамок, 13 групп классов. mAP50 считается по рамкам, это другая мера, чем доля верных ответов, и с числами других команд её сравнивать нельзя.',
  },
  {
    value: '364 мс',
    label: 'на кадр на процессоре',
    caveat:
      'Одно ядро обработает снимки годового надзора Москвы за 36 часов при сотне снимков на проверку.',
  },
  {
    value: '70%',
    label: 'потолок согласия двух независимых разметок',
    caveat: 'Разметили инженер и языковая модель. Выше этого числа метрика простоя теряет смысл.',
  },
]

export function Proof() {
  return (
    <Section id="proof" index="06" label="Измерено" title="Что измерено">
      <ul className={styles.proof}>
        {PROOF.map((p) => (
          <li key={p.value}>
            <b className={styles.proofValue}>{p.value}</b>
            <span className={styles.proofLabel}>{p.label}</span>
            <small>{p.caveat}</small>
          </li>
        ))}
      </ul>
      {REPO_URL ? (
        <a className={styles.link} href={`${REPO_URL}/blob/main/ml/EXPERIMENTS.md`}>
          Все эксперименты, включая неудачные
        </a>
      ) : null}
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
    row: 'Различает виды «нет»',
    cells: ['Да, четыре вида', 'Нет', 'Не раскрыто', 'Не раскрыто', 'Нет'],
  },
  {
    row: 'Код открыт',
    cells: [
      'Да, AGPL-3.0',
      'Не применимо',
      'Закрытый продукт',
      'Закрытый продукт',
      'Закрытый продукт',
    ],
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
      <p className={styles.note}>
        Сведения о других продуктах взяты из их открытых материалов на 20.09.2026. Где не раскрыто,
        так и написано. Источники в репозитории: ml/research/part_Q_products.md.
      </p>
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
    text: 'Открытый код, запуск через Docker Compose, работа на процессоре, выгрузки CSV, XLSX и печатная версия.',
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
    a: 'Вывод по этапу строится на технике-маркере и показывается интервалом, а не точным числом. Низкая уверенность понижает важность. Решение остаётся за инженером: гипотезы он подтверждает или отклоняет сам.',
  },
  {
    q: 'Нужны ли особые камеры или BIM?',
    a: 'Нет. Нужны график таблицей и снимки. Подойдут камеры, которые уже стоят. Чем чаще съёмка, тем точнее срок: точность не выше частоты кадров, и сервис это показывает.',
  },
  {
    q: 'Что если снимков мало или площадка видна плохо?',
    a: 'Сервис оценивает наблюдаемость. Когда она низкая, он пишет, что участок вне контроля, и не делает вывод «работы не ведутся».',
  },
  {
    q: 'Где хранятся данные?',
    a: 'Снимки и графики лежат на сервере, где развёрнута Веха: у вас, если вы ставите её у себя. Оригиналы снимков не меняются. Каждая стройка видна только тому, кто её завёл. Пароли хранятся в виде хеша, частота попыток входа ограничена. Вопросы ассистенту и разбор графика языковой моделью отправляют текст отчёта или строки таблицы выбранному вами провайдеру модели, снимки туда не уходят. Без настроенной модели эти две функции выключены, остальное работает.',
  },
  {
    q: 'Сколько это стоит?',
    a: 'Лицензия бесплатная, AGPL-3.0. Закрытое внедрение без открытия кода потребует коммерческой лицензии на детектор Ultralytics. Стоимость пилота обсуждаем отдельно.',
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

const OPEN = [
  {
    title: 'Открытый код',
    text: 'Лицензия AGPL-3.0, исходники можно прочитать и проверить.',
    art: <CodeArt />,
  },
  {
    title: 'Запуск у вас',
    text: 'Docker Compose и одна команда: make deploy-tunnel.',
    art: <RunArt />,
  },
  {
    title: 'Без видеокарты',
    text: 'Детектор работает на процессоре ноутбука, 364 мс на кадр.',
    art: <CpuArt />,
  },
]

export function OpenSource() {
  return (
    <Section
      id="open"
      index="10"
      label="Открытость"
      title="Ставится у вас и проверяется вашими людьми"
      wide
    >
      <ul className={styles.trio}>
        {OPEN.map((o) => (
          <li key={o.title}>
            <div className={styles.art}>{o.art}</div>
            <h3>{o.title}</h3>
            <p>{o.text}</p>
          </li>
        ))}
      </ul>
      {REPO_URL ? (
        <a className={styles.link} href={REPO_URL}>
          Репозиторий проекта
        </a>
      ) : null}
    </Section>
  )
}

export function FinalCta() {
  return (
    <section id="pilot" className={styles.final} aria-labelledby="pilot-h">
      <div className={styles.finalPanel}>
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
            <Link to="/register" className={styles.primary}>
              Попробовать самому
            </Link>
            {PILOT_CONTACT ? (
              <a href={PILOT_CONTACT} className={styles.ghost}>
                Запросить пилот
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  )
}

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footInner}>
        <span className={styles.brand}>
          <Logo />
          Веха
        </span>
        <p>Проект команды XX_prod, ЛЦТ-2026, задача 7. Лицензия AGPL-3.0.</p>
        {REPO_URL ? <a href={REPO_URL}>Исходный код</a> : null}
      </div>
    </footer>
  )
}

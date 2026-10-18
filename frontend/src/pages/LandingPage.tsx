import { Navigate, useLocation } from 'react-router'
import { Hero } from '@/features/landing/Hero'
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
} from '@/features/landing/Sections'
import { getToken } from '@/lib/authStorage'
import styles from './LandingPage.module.css'

/**
 * Первая страница для гостя. История: оффер и продукт на настоящем снимке, контекст, закреплённый
 * таймлайн «план против факта», три шага, живой пример на данных p03 без входа, доказательства,
 * сравнение с рынком, ответы на возражения. Вошедшего ведём к стройкам, но не когда он пришёл
 * с логотипа «Веха» (`state.landing`): тогда вместо входа и регистрации одна ссылка «К стройкам».
 */
export function LandingPage() {
  const location = useLocation()
  const signedIn = Boolean(getToken())
  const fromLogo = Boolean((location.state as { landing?: boolean } | null)?.landing)
  if (signedIn && !fromLogo) return <Navigate to="/sites" replace />

  return (
    <div id="top" className={styles.page}>
      <SiteHeader signedIn={signedIn} />
      <main>
        <Hero signedIn={signedIn} />
        <Facts />
        <Timeline />
        <HowItWorks />
        <Demo />
        <Trust />
        <Proof />
        <Compare />
        <Audience />
        <Faq />
        <FinalCta signedIn={signedIn} />
      </main>
    </div>
  )
}

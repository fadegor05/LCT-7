import { Navigate } from 'react-router'
import { Hero } from '@/features/landing/Hero'
import {
  Audience,
  Compare,
  Demo,
  Facts,
  Faq,
  FinalCta,
  Footer,
  HowItWorks,
  OpenSource,
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
 * сравнение с рынком, ответы на возражения. Вошедшего сразу ведём к стройкам.
 */
export function LandingPage() {
  if (getToken()) return <Navigate to="/sites" replace />

  return (
    <div id="top" className={styles.page}>
      <SiteHeader />
      <main>
        <Hero />
        <Facts />
        <Timeline />
        <HowItWorks />
        <Demo />
        <Trust />
        <Proof />
        <Compare />
        <Audience />
        <Faq />
        <OpenSource />
        <FinalCta />
      </main>
      <Footer />
    </div>
  )
}

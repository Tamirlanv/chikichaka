import Image from "next/image";
import Link from "next/link";
import styles from "./page.module.css";

const RESOURCES = [
  {
    button: "GitHub inVision",
    description: "GitHub репозитории",
    link: "https://github.com",
  },
  {
    button: "Google Disk",
    description: "Презентация проекта",
    link: "https://drive.google.com",
  },
  {
    button: "Google Disk",
    description: "Документация решения",
    link: "https://drive.google.com",
  },
  {
    button: "Telegram Bot",
    description: "FAQ и поддержка по проекту",
    link: "https://telegram.org",
  },
] as const;

export default function HomePage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.logo}>
          inVision
        </Link>
        <nav className={styles.nav}>
          <Link href="/register" className={styles.navReg}>
            Регистрация
          </Link>
          <Link href="/login" className={styles.navLogin}>
            Войти
          </Link>
        </nav>
      </header>

      <div className={styles.hero}>
        <Image
          src="/assets/images/img.png"
          alt="inVision U"
          width={1920}
          height={445}
          priority
          className={styles.heroImg}
          sizes="100vw"
          unoptimized
        />
      </div>

      <main className={styles.main}>
        <p className={styles.byline}>by KOMO</p>

        <section className={styles.resources} aria-labelledby="resources-heading">
          <h2 id="resources-heading" className={styles.resourcesTitle}>
            Ресурсы
          </h2>
          <div className={styles.resourceGrid}>
            {RESOURCES.map((resource) => (
              <div key={resource.description} className={styles.resourceItem}>
                <a
                  href={resource.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.resourceBtn}
                >
                  {resource.button}
                </a>
                <p className={styles.resourceDesc}>{resource.description}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

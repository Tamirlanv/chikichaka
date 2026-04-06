import styles from "./page.module.css";
import { DEMO_VIDEOS, getYouTubeEmbedSrc, getYouTubeWatchHref } from "./demo-videos.config";

const INTRO = "В видео описываются следующий функционал:";

const BULLETS_STAGE_2 = [
  "-Новые этапы в заявке Путь и Достижение",
  "-Сторона кандидата",
  "-Нулевой этап валидации",
  "-Система кэша Redis",
  "-Валидация ссылок на видео",
  "-Регистрация JWT-токены",
  "-Модернизация раздела “тест”",
  "-Собственная LLM расположенная на сервере",
  "-Соответствие с законодательством",
  "-Сторона комиссии: частично",
  "-Горизонтальное масштабирование",
] as const;

const BULLETS_FULL = ["-Все функции"] as const;

const IFRAME_ALLOW =
  "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";

function BulletList({ items }: { items: readonly string[] }) {
  return (
    <ul className={styles.demoList}>
      {items.map((line) => (
        <li key={line} className={styles.demoListItem}>
          {line}
        </li>
      ))}
    </ul>
  );
}

function WatchButton({ youtubeUrl }: { youtubeUrl: string }) {
  const href = getYouTubeWatchHref(youtubeUrl);
  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={styles.demoWatchBtn}
      >
        Смотреть
      </a>
    );
  }
  return (
    <button type="button" className={styles.demoWatchBtn} disabled title="Укажите полную ссылку YouTube в demo-videos.config.ts">
      Смотреть
    </button>
  );
}

function VideoPreview({ youtubeUrl, title }: { youtubeUrl: string; title: string }) {
  const embedSrc = getYouTubeEmbedSrc(youtubeUrl);
  return (
    <div className={styles.demoPreviewCol}>
      <p className={styles.demoPreviewLabel}>Предпросмотр</p>
      <div className={styles.demoPreviewFrame}>
        {embedSrc ? (
          <iframe
            title={title}
            className={styles.demoPreviewIframe}
            src={embedSrc}
            allow={IFRAME_ALLOW}
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        ) : (
          <div className={styles.demoPreviewPlaceholder}>
            Укажите корректную ссылку YouTube в файле demo-videos.config.ts — предпросмотр подставится автоматически.
          </div>
        )}
      </div>
    </div>
  );
}

export function DemoVideosSection() {
  const stage2Url = DEMO_VIDEOS[0]!.youtubeUrl;
  const stage3FullUrl = DEMO_VIDEOS[1]!.youtubeUrl;

  return (
    <section className={styles.demoSection} aria-label="Демо-видео">
      <div className={styles.demoRow}>
        <div className={styles.demoTextCol}>
          <p className={`${styles.demoTitle} ${styles.demoTitleLeft}`}>
            ДЕМО-ВИДЕО | 3 ЭТАП
            <br aria-hidden="true" />
            ПОЛНАЯ ВЕРСИЯ
          </p>
          <p className={styles.demoIntro}>{INTRO}</p>
          <BulletList items={BULLETS_FULL} />
          <WatchButton youtubeUrl={stage3FullUrl} />
        </div>
        <VideoPreview youtubeUrl={stage3FullUrl} title="Демо-видео, этап 3, полная версия" />
      </div>

      <div className={styles.demoRow}>
        <div className={styles.demoTextCol}>
          <p className={styles.demoTitle}>ДЕМО-ВИДЕО | 2 ЭТАП</p>
          <p className={styles.demoIntro}>{INTRO}</p>
          <BulletList items={BULLETS_STAGE_2} />
          <WatchButton youtubeUrl={stage2Url} />
        </div>
        <VideoPreview youtubeUrl={stage2Url} title="Демо-видео, этап 2" />
      </div>
    </section>
  );
}

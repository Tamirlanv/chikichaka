"use client";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function CommissionBoardHelpModal({ open, onClose }: Props) {
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="commission-board-help-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.45)",
        padding: 16,
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "min(520px, 100%)",
          maxHeight: "min(85vh, 640px)",
          overflow: "auto",
          background: "#fff",
          borderRadius: 16,
          padding: "24px 20px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
        }}
      >
        <h2 id="commission-board-help-title" style={{ margin: "0 0 16px", fontSize: 18, fontWeight: 600 }}>
          Справка: обзор заявлений
        </h2>
        <div style={{ fontSize: 14, lineHeight: 1.5, color: "#262626" }}>
          <p style={{ margin: "0 0 12px", fontWeight: 600 }}>Этапы колонок</p>
          <ul style={{ margin: "0 0 20px", paddingLeft: 20 }}>
            <li style={{ marginBottom: 8 }}>
              <strong>Проверка данных</strong> — проверка материалов и данных кандидата. Перенос карточки между
              колонками вручную недоступен.
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong>Оценка заявки</strong> — работа комиссии с рубриками и подготовка к собеседованию (в т.ч. AI).
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong>Собеседование</strong> — AI-собеседование и собеседование с комиссией.
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong>Решение комиссии</strong> — финальное рассмотрение заявки.
            </li>
            <li>
              <strong>Результат</strong> — итоговый статус зачисления.
            </li>
          </ul>
          <p style={{ margin: "0 0 12px", fontWeight: 600 }}>Обводка карточек</p>
          <p style={{ margin: "0 0 8px" }}>
            <strong>Колонка «Проверка данных»:</strong> цвет рамки соответствует агрегированному статусу
            автоматической проверки (data-check).
          </p>
          <ul style={{ margin: "0 0 16px", paddingLeft: 20 }}>
            <li style={{ marginBottom: 8 }}>
              <strong>Синяя</strong> — обработка ещё идёт (ожидание / в работе), критических ошибок по run ещё не
              зафиксировано.
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong>Оранжевая</strong> — проверка завершилась с ошибками или требует внимания (например,{" "}
              <code>partial</code> или <code>failed</code>).
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong>Зелёная</strong> — все обязательные шаги проверки успешно завершены (<code>ready</code>
              ), заявка может перейти на следующий этап автоматически.
            </li>
          </ul>
          <p style={{ margin: "0 0 8px" }}>
            На этапах <strong>«Оценка заявки»</strong> и <strong>«Собеседование»</strong> рамка отражает прогресс
            рубрики и AI/собеседования:
          </p>
          <ul style={{ margin: "0 0 0", paddingLeft: 20 }}>
            <li style={{ marginBottom: 8 }}>
              <strong>Серая</strong> — базовое состояние на «Оценке заявки» до выполнения условий ниже.
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong>Синяя</strong> — на «Оценке заявки»: первый этап данных готов, но рубрика ещё не заполнена
              полностью. На «Собеседовании»: AI-собеседование завершено, но дата с комиссией ещё не назначена.
            </li>
            <li style={{ marginBottom: 8 }}>
              <strong>Оранжевая</strong> — на «Собеседовании»: AI-собеседование ещё не завершено.
            </li>
            <li>
              <strong>Зелёная</strong> — на «Оценке заявки»: рубрика заполнена по всем трём разделам. На
              «Собеседовании»: AI завершён и собеседование с комиссией запланировано.
            </li>
          </ul>
        </div>
        <div className="modal-actions modal-actions--single" style={{ marginTop: 20 }}>
          <button type="button" className="btn" onClick={onClose}>
            Понятно
          </button>
        </div>
      </div>
    </div>
  );
}

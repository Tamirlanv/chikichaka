"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  type DragEndEvent,
  type DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useRouter } from "next/navigation";
import { COMMISSION_STAGE_ORDER, COMMISSION_STAGE_TITLES } from "@/lib/commission/constants";
import { isNextStageOnly, resolveDropStage } from "@/lib/commission/dnd";
import { permissionsFromRole } from "@/lib/commission/permissions";
import {
  createQuickComment,
  getCommissionBoard,
  getCommissionRole,
  getStageAdvancePreview,
  moveApplicationToNextStage,
  setAttentionFlag,
} from "@/lib/commission/query";
import { subscribeToUpdates, unsubscribeFromUpdates, stopPolling } from "@/lib/commission/revalidate";
import { sortColumnCards, type ColumnSortMode } from "@/lib/commission/columnSort";
import type {
  CommissionBoardFilters,
  CommissionBoardResponse,
  CommissionRole,
  CommissionStage,
  StageAdvancePreviewResponse,
} from "@/lib/commission/types";
import { ApplicationCardDragOverlay } from "./ApplicationCard";
import { BoardColumn } from "./BoardColumn";
import { SkipMandatoryStageModal } from "./SkipMandatoryStageModal";
import { StageTransitionModal } from "./StageTransitionModal";
import styles from "./BoardContainer.module.css";

type Props = {
  filters: CommissionBoardFilters;
  onError: (msg: string) => void;
};

const MAIN_BOARD_STAGES: CommissionStage[] = COMMISSION_STAGE_ORDER.filter((s) => s !== "result");

function errorStatusCode(error: unknown): number | null {
  if (!error || typeof error !== "object") return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

function initialColumnSortModes(): Record<CommissionStage, ColumnSortMode> {
  const r = {} as Record<CommissionStage, ColumnSortMode>;
  for (const s of MAIN_BOARD_STAGES) {
    r[s] = 0;
  }
  return r;
}

export function BoardContainer({ filters, onError }: Props) {
  const router = useRouter();
  const [role, setRole] = useState<CommissionRole | null>(null);
  const [data, setData] = useState<CommissionBoardResponse | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);
  const [pollingEnabled, setPollingEnabled] = useState(true);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [columnSortModes, setColumnSortModes] = useState<Record<CommissionStage, ColumnSortMode>>(initialColumnSortModes);
  const [transitionModal, setTransitionModal] = useState<{
    variant: "confirm" | "blocked";
    applicationId: string;
    toStage: CommissionStage;
    fromStage: CommissionStage;
    preview: StageAdvancePreviewResponse;
  } | null>(null);

  const permissions = useMemo(() => permissionsFromRole(role), [role]);
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  );

  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const pendingBoardSnapshotRef = useRef<CommissionBoardResponse | null>(null);
  const advancingRef = useRef(false);
  const [isAdvancingTransition, setIsAdvancingTransition] = useState(false);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [skipMandatoryStageModalOpen, setSkipMandatoryStageModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [r, d] = await Promise.all([getCommissionRole(), getCommissionBoard(filtersRef.current)]);
      setRole(r);
      setData(d);
      setDataLoaded(true);
      setPollingEnabled(true);
    } catch (e) {
      const status = errorStatusCode(e);
      if (status === 401 || status === 403) {
        setPollingEnabled(false);
      }
      onErrorRef.current(e instanceof Error ? e.message : "Не удалось загрузить board");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [filters.search, filters.program, filters.range, refresh]);

  useEffect(() => {
    if (!pollingEnabled || !dataLoaded || !permissions.canViewBoard) {
      return;
    }
    const listener = () => { void refresh(); };
    subscribeToUpdates(listener, {
      onUnauthorized: () => { setPollingEnabled(false); },
    });
    return () => { unsubscribeFromUpdates(listener); };
  }, [pollingEnabled, dataLoaded, permissions.canViewBoard, refresh]);

  async function onDropCard(applicationId: string, toStage: CommissionStage) {
    if (!permissions.canMove || !data) return;
    const from = data.columns.find((c) => c.applications.some((a) => a.applicationId === applicationId));
    if (!from) return;
    if (from.stage === toStage) return;
    if (!isNextStageOnly(from.stage, toStage)) {
      setSkipMandatoryStageModalOpen(true);
      return;
    }
    try {
      const preview = await getStageAdvancePreview(applicationId);
      if (preview.allowed) {
        pendingBoardSnapshotRef.current = structuredClone(data) as CommissionBoardResponse;
        setTransitionModal({
          variant: "confirm",
          applicationId,
          toStage,
          fromStage: from.stage,
          preview,
        });
      } else {
        setTransitionModal({
          variant: "blocked",
          applicationId,
          toStage,
          fromStage: from.stage,
          preview,
        });
      }
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось проверить переход");
    }
  }

  async function executeConfirmedMove() {
    if (advancingRef.current) return;
    const modal = transitionModal;
    if (!modal || modal.variant !== "confirm") return;
    const snapshot = pendingBoardSnapshotRef.current;
    if (!snapshot) {
      setTransitionModal(null);
      return;
    }
    const { applicationId, toStage, fromStage } = modal;
    advancingRef.current = true;
    setIsAdvancingTransition(true);
    setMovingId(applicationId);
    setData((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev) as CommissionBoardResponse;
      const src = next.columns.find((c) => c.stage === fromStage);
      const dst = next.columns.find((c) => c.stage === toStage);
      if (!src || !dst) return prev;
      const idx = src.applications.findIndex((a) => a.applicationId === applicationId);
      if (idx < 0) return prev;
      const [card] = src.applications.splice(idx, 1);
      card.currentStage = toStage;
      dst.applications.unshift(card);
      return next;
    });
    try {
      await moveApplicationToNextStage(applicationId);
      try {
        await refresh();
      } catch {
        onError("Переход выполнен, но не удалось обновить доску. Повторная попытка…");
        try {
          await refresh();
        } catch {
          onError("Не удалось обновить доску. Обновите страницу вручную.");
        }
      }
      setTransitionModal(null);
      pendingBoardSnapshotRef.current = null;
    } catch (e) {
      setData(snapshot);
      pendingBoardSnapshotRef.current = null;
      setTransitionModal(null);
      onError(e instanceof Error ? e.message : "Не удалось переместить заявку");
    } finally {
      advancingRef.current = false;
      setIsAdvancingTransition(false);
      setMovingId(null);
    }
  }

  function navigateBlockedPrimary() {
    const modal = transitionModal;
    if (!modal) return;
    const pa = modal.preview.blocked?.primaryAction;
    setTransitionModal(null);
    if (pa?.kind === "open_application") {
      const q = new URLSearchParams();
      if (pa.query.interviewSubTab) q.set("interviewSubTab", pa.query.interviewSubTab);
      const qs = q.toString();
      router.push(`/commission/applications/${pa.applicationId}${qs ? `?${qs}` : ""}`);
    } else {
      router.push(`/commission/applications/${modal.applicationId}`);
    }
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveDragId(String(event.active.id));
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveDragId(null);
    if (!data) return;
    const applicationId = String(event.active.id);
    const overId = event.over?.id ? String(event.over.id) : null;
    const toStage = resolveDropStage(overId, data.columns);
    if (!toStage) return;
    void onDropCard(applicationId, toStage);
  }

  function handleDragCancel() {
    setActiveDragId(null);
  }

  const activeDragCard = useMemo(() => {
    if (!activeDragId || !data) return null;
    for (const col of data.columns) {
      const card = col.applications.find((a) => a.applicationId === activeDragId);
      if (card) return { card, stage: col.stage };
    }
    return null;
  }, [activeDragId, data]);

  async function onQuickComment(applicationId: string, body: string) {
    try {
      await createQuickComment(applicationId, body);
      await refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось добавить комментарий");
    }
  }

  async function onToggleAttention(applicationId: string, value: boolean) {
    try {
      await setAttentionFlag(applicationId, value);
      await refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось обновить attention");
    }
  }

  function cycleColumnSort(stage: CommissionStage) {
    setColumnSortModes((prev) => ({
      ...prev,
      [stage]: ((((prev[stage] ?? 0) + 1) % 4) as ColumnSortMode),
    }));
  }

  if (!data) return <p className="muted">Загрузка доски…</p>;
  if (!permissions.canViewBoard) return <p className="error">Нет доступа к странице комиссии.</p>;

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      {skipMandatoryStageModalOpen ? (
        <SkipMandatoryStageModal onDismiss={() => { setSkipMandatoryStageModalOpen(false); }} />
      ) : null}
      {transitionModal ? (
        <StageTransitionModal
          preview={transitionModal.preview}
          variant={transitionModal.variant}
          onConfirm={() => { void executeConfirmedMove(); }}
          onPrimaryAction={navigateBlockedPrimary}
          onCancel={() => {
            if (isAdvancingTransition) return;
            setTransitionModal(null);
            pendingBoardSnapshotRef.current = null;
          }}
          confirmDisabled={isAdvancingTransition}
          cancelDisabled={isAdvancingTransition}
        />
      ) : null}
      <section className={styles.boardScrollStrip}>
        {MAIN_BOARD_STAGES.map((stage, idx) => {
          const col = data.columns.find((c) => c.stage === stage) ?? {
            stage,
            title: COMMISSION_STAGE_TITLES[stage],
            applications: [],
          };
          const mode = columnSortModes[stage] ?? 0;
          const cards = sortColumnCards(stage, col.applications, mode);
          return (
            <SortableContext key={stage} items={cards.map((a) => a.applicationId)} strategy={verticalListSortingStrategy}>
              <BoardColumn
                order={idx + 1}
                stage={stage}
                title={col.title}
                cards={cards}
                sortMode={mode}
                onCycleSort={() => cycleColumnSort(stage)}
                permissions={permissions}
                movingId={movingId}
                onQuickComment={onQuickComment}
                onToggleAttention={onToggleAttention}
              />
            </SortableContext>
          );
        })}
      </section>

      <DragOverlay dropAnimation={{ duration: 200, easing: "ease" }}>
        {activeDragCard ? (
          <ApplicationCardDragOverlay
            card={activeDragCard.card}
            columnStage={activeDragCard.stage}
            showHandle={
              permissions.canMove &&
              (
                activeDragCard.stage !== "data_check" ||
                activeDragCard.card.dataCheckRunStatus === "partial" ||
                activeDragCard.card.dataCheckRunStatus === "failed"
              )
            }
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

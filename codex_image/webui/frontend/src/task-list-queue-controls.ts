import {
  cancelRunningTask,
  deleteQueuedTask,
  handleQueueDragEnd,
  handleQueueDragOver,
  handleQueueDragStart,
  moveQueueTask,
  promoteQueueTask,
  reorderQueue,
} from "./queue";
import { getLegacyBridge } from "./state";
import { cssEscape, prefersReducedMotion } from "./webui-utils";

const bridge = getLegacyBridge();
const state = bridge.state;
const els = bridge.els;

let taskListQueueControlsInitialized = false;
let taskListQueueControlsBound = false;
let queueDragOriginalOrder: string[] = [];
let queueDragCommitted = false;
let queueDragOverTargetId = "";
let queueDragOverPlacement: "before" | "after" = "after";
let queueTransparentDragImage: HTMLElement | null = null;

function eventTargetElement(event: Event): Element | null {
  return event.target instanceof Element ? event.target : null;
}

function stopQueueControlEvent(event: Event): void {
  event.preventDefault();
  event.stopPropagation();
}

function stopQueueDragEvent(event: Event): void {
  event.stopPropagation();
}

function taskListQueueControlRoots(): HTMLElement[] {
  return [els.taskActiveList, els.taskList].filter((root): root is HTMLElement => root instanceof HTMLElement);
}

function bindTaskListQueueControls(): void {
  if (taskListQueueControlsBound) return;
  taskListQueueControlsBound = true;
  taskListQueueControlRoots().forEach((root) => {
    root.addEventListener("click", handleTaskListQueueClick);
    root.addEventListener("dragstart", handleTaskListQueueDragStart);
    root.addEventListener("dragover", handleTaskListQueueDragOver);
    root.addEventListener("drop", handleTaskListQueueDrop);
    root.addEventListener("dragend", handleTaskListQueueDragEnd);
  });
}

function handleTaskListQueueClick(event: MouseEvent): void {
  const target = eventTargetElement(event);
  const dragHandle = target?.closest("[data-task-queue-drag-handle-id]");
  if (dragHandle instanceof HTMLElement) {
    stopQueueControlEvent(event);
    return;
  }

  const cancelButton = target?.closest("[data-task-queue-cancel-id]");
  if (cancelButton instanceof HTMLElement) {
    stopQueueControlEvent(event);
    cancelRunningTask(cancelButton, cancelButton.dataset.taskQueueCancelId);
    return;
  }

  const moveButton = target?.closest("[data-task-queue-move-id]");
  if (moveButton instanceof HTMLElement) {
    stopQueueControlEvent(event);
    moveQueueTask(moveButton.dataset.taskQueueMoveId, moveButton.dataset.taskQueueDirection);
    return;
  }

  const promoteButton = target?.closest("[data-task-queue-promote-id]");
  if (promoteButton instanceof HTMLElement) {
    stopQueueControlEvent(event);
    void promoteQueueTask(promoteButton.dataset.taskQueuePromoteId);
    return;
  }

  const deleteButton = target?.closest("[data-task-queue-delete-id]");
  if (deleteButton instanceof HTMLElement) {
    stopQueueControlEvent(event);
    deleteQueuedTask(deleteButton, deleteButton.dataset.taskQueueDeleteId);
  }
}

function waitingDropTarget(event: DragEvent): Element | null {
  return eventTargetElement(event)?.closest("[data-active-task-section=\"waiting\"]") || null;
}

function waitingQueueSectionItems(): HTMLElement | null {
  for (const root of taskListQueueControlRoots()) {
    const section = root.querySelector("[data-active-task-section=\"waiting\"] .task-active-section-items");
    if (section instanceof HTMLElement) return section;
  }
  return null;
}

function waitingQueueDomOrder(): string[] {
  const section = waitingQueueSectionItems();
  return Array.from(section?.querySelectorAll("[data-queue-task-id]") || [])
    .map((card) => String((card as HTMLElement).dataset.queueTaskId || ""))
    .filter(Boolean);
}

function sameQueueOrder(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((taskId, index) => taskId === right[index]);
}

function restoreWaitingQueueDomOrder(taskIds: string[]): void {
  const section = waitingQueueSectionItems();
  if (!section) return;
  const cards = new Map(
    Array.from(section.querySelectorAll("[data-queue-task-id]"))
      .map((card) => [String((card as HTMLElement).dataset.queueTaskId || ""), card as HTMLElement] as [string, HTMLElement]),
  );
  taskIds.forEach((taskId) => {
    const card = cards.get(taskId);
    if (card) section.append(card);
  });
}

function animateWaitingQueueReorder(applyReorder: () => void): void {
  const section = waitingQueueSectionItems();
  if (!section || prefersReducedMotion()) {
    applyReorder();
    return;
  }
  const cards = Array.from(section.querySelectorAll("[data-queue-task-id]")) as HTMLElement[];
  const previousTops = new Map(cards.map((card) => [card, card.getBoundingClientRect().top]));
  applyReorder();
  cards.forEach((card) => {
    const previousTop = previousTops.get(card);
    if (previousTop === undefined) return;
    const dy = previousTop - card.getBoundingClientRect().top;
    if (Math.abs(dy) > 0.5) {
      card.animate(
        [{ transform: `translateY(${dy}px)` }, { transform: "translateY(0px)" }],
        { duration: 180, easing: "ease" },
      );
    }
  });
}

function taskQueueTransparentDragImage(): HTMLElement {
  if (queueTransparentDragImage?.isConnected) return queueTransparentDragImage;
  const element = document.createElement("div");
  element.className = "task-queue-transparent-drag-image";
  element.setAttribute("aria-hidden", "true");
  document.body.append(element);
  queueTransparentDragImage = element;
  return element;
}

function moveWaitingQueueDragPlaceholder(targetCard: HTMLElement, placement: "before" | "after"): void {
  const draggedId = String(state.queueDragTaskId || "");
  if (!draggedId) return;
  const parent = targetCard.parentElement;
  if (!parent) return;
  const draggedCard = parent.querySelector(`[data-queue-task-id="${cssEscape(draggedId)}"]`);
  if (!(draggedCard instanceof HTMLElement) || draggedCard === targetCard) return;
  animateWaitingQueueReorder(() => {
    if (placement === "before") {
      parent.insertBefore(draggedCard, targetCard);
    } else {
      parent.insertBefore(draggedCard, targetCard.nextSibling);
    }
  });
}

function resetQueueDragTracking(): void {
  queueDragOriginalOrder = [];
  queueDragCommitted = false;
  queueDragOverTargetId = "";
  queueDragOverPlacement = "after";
}

function handleTaskListQueueDragStart(event: DragEvent): void {
  const target = eventTargetElement(event);
  const handle = target?.closest("[data-task-queue-drag-handle-id]");
  if (!(handle instanceof HTMLElement)) {
    if (target?.closest(".task-thumb")) {
      event.preventDefault();
      event.stopPropagation();
    }
    return;
  }
  const card = handle.closest("[data-queue-task-id]");
  if (!(card instanceof HTMLElement)) return;
  stopQueueDragEvent(event);
  card.classList.add("queue-dragging");
  if (event.dataTransfer) {
    event.dataTransfer.setDragImage(taskQueueTransparentDragImage(), 0, 0);
  }
  handleQueueDragStart(event);
  queueDragOriginalOrder = waitingQueueDomOrder();
  queueDragCommitted = false;
  queueDragOverTargetId = "";
  queueDragOverPlacement = "after";
}

function handleTaskListQueueDragOver(event: DragEvent): void {
  if (!state.queueDragTaskId || !waitingDropTarget(event)) return;
  handleQueueDragOver(event);
  const targetCard = eventTargetElement(event)?.closest("[data-queue-task-id]");
  if (!(targetCard instanceof HTMLElement)) return;
  const targetId = String(targetCard.dataset.queueTaskId || "");
  if (!targetId || targetId === String(state.queueDragTaskId)) return;
  const rect = targetCard.getBoundingClientRect();
  const placement: "before" | "after" = event.clientY < rect.top + rect.height / 2 ? "before" : "after";
  if (queueDragOverTargetId === targetId && queueDragOverPlacement === placement) return;
  queueDragOverTargetId = targetId;
  queueDragOverPlacement = placement;
  moveWaitingQueueDragPlaceholder(targetCard, placement);
}

function handleTaskListQueueDrop(event: DragEvent): void {
  if (!state.queueDragTaskId || !waitingDropTarget(event)) return;
  event.preventDefault();
  event.stopPropagation();
  const draggedId = String(state.queueDragTaskId);
  const reorderedIds = waitingQueueDomOrder();
  queueDragCommitted = true;
  if (!reorderedIds.includes(draggedId) || sameQueueOrder(queueDragOriginalOrder, reorderedIds)) return;
  void reorderQueue(reorderedIds);
}

function handleTaskListQueueDragEnd(event: DragEvent): void {
  if (!state.queueDragTaskId) return;
  const originalOrder = queueDragOriginalOrder.slice();
  const committed = queueDragCommitted;
  handleQueueDragEnd(event);
  taskListQueueControlRoots().forEach((root) => {
    root.querySelectorAll(".queue-dragging").forEach((element: Element) => {
      element.classList.remove("queue-dragging");
    });
  });
  if (!committed && originalOrder.length && !sameQueueOrder(originalOrder, waitingQueueDomOrder())) {
    animateWaitingQueueReorder(() => restoreWaitingQueueDomOrder(originalOrder));
  }
  resetQueueDragTracking();
}

export function initTaskListQueueControlsFeature(): void {
  if (taskListQueueControlsInitialized) return;
  taskListQueueControlsInitialized = true;
  Object.assign(getLegacyBridge().methods, {
    bindTaskListQueueControls,
    handleTaskListQueueClick,
    handleTaskListQueueDragStart,
    handleTaskListQueueDragOver,
    handleTaskListQueueDrop,
    handleTaskListQueueDragEnd,
  });
  bindTaskListQueueControls();
}

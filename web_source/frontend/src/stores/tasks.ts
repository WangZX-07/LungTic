import { defineStore } from "pinia";
import { ref, computed } from "vue";

export type TaskType = "segmentation" | "igtv" | "trajectory";
export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface Task {
  id: string;
  type: TaskType;
  studyId: number;
  status: TaskStatus;
  message: string;
  createdAt: number;
  progress?: number;
}

export const useTaskStore = defineStore("tasks", () => {
  const tasks = ref<Task[]>([]);

  const runningTasks = computed(() =>
    tasks.value.filter((t) => t.status === "running")
  );

  const recentTasks = computed(() =>
    [...tasks.value].sort((a, b) => b.createdAt - a.createdAt).slice(0, 20)
  );

  const hasRunning = computed(() => runningTasks.value.length > 0);

  function addTask(type: TaskType, studyId: number, message: string): string {
    const id = `${type}-${studyId}-${Date.now()}`;
    tasks.value.push({
      id,
      type,
      studyId,
      status: "running",
      message,
      createdAt: Date.now(),
      progress: 0,
    });
    return id;
  }

  function updateProgress(taskId: string, progress: number) {
    const task = tasks.value.find((t) => t.id === taskId);
    if (task) task.progress = Math.min(100, Math.max(0, progress));
  }

  function completeTask(taskId: string, message?: string) {
    const task = tasks.value.find((t) => t.id === taskId);
    if (task) {
      task.status = "completed";
      task.progress = 100;
      if (message) task.message = message;
    }
  }

  function failTask(taskId: string, message?: string) {
    const task = tasks.value.find((t) => t.id === taskId);
    if (task) {
      task.status = "failed";
      if (message) task.message = message;
    }
  }

  function removeTask(taskId: string) {
    tasks.value = tasks.value.filter((t) => t.id !== taskId);
  }

  function clearCompleted() {
    tasks.value = tasks.value.filter((t) => t.status !== "completed" && t.status !== "failed");
  }

  return {
    tasks,
    runningTasks,
    recentTasks,
    hasRunning,
    addTask,
    updateProgress,
    completeTask,
    failTask,
    removeTask,
    clearCompleted,
  };
});
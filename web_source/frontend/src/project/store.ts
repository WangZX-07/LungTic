import { computed, ref } from "vue";
import { defineStore } from "pinia";
import api from "./api";
import type { ProjectMember, ProjectRole } from "./types";

const ranks: Record<ProjectRole, number> = {
  unassigned: 0, observer: 1, contributor: 2, team_lead: 3, project_lead: 4, project_admin: 5,
};

export const useProjectStore = defineStore("project", () => {
  const member = ref<ProjectMember | null>(null);
  const configured = ref(true);
  const appId = ref("");
  const checking = ref(false);

  const authenticated = computed(() => Boolean(member.value));
  const canContribute = computed(() => roleAtLeast("contributor"));
  const canLead = computed(() => roleAtLeast("team_lead"));
  const canManageProject = computed(() => roleAtLeast("project_lead"));
  const isAdmin = computed(() => roleAtLeast("project_admin"));

  function roleAtLeast(role: ProjectRole) {
    return ranks[member.value?.role || "unassigned"] >= ranks[role];
  }

  async function loadConfig() {
    const { data } = await api.get("/auth/config");
    configured.value = data.configured;
    appId.value = data.app_id || "";
  }

  async function verify() {
    checking.value = true;
    try {
      const { data } = await api.get<ProjectMember>("/me");
      member.value = data;
      return true;
    } catch {
      member.value = null;
      return false;
    } finally {
      checking.value = false;
    }
  }

  async function loginWithCode(code: string) {
    const { data } = await api.post<ProjectMember>("/auth/feishu-client", { code });
    member.value = data;
  }

  async function logout() {
    await api.post("/auth/logout");
    member.value = null;
  }

  return {
    member, configured, appId, checking, authenticated,
    canContribute, canLead, canManageProject, isAdmin,
    roleAtLeast, loadConfig, verify, loginWithCode, logout,
  };
});

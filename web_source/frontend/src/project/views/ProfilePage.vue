<template>
  <div class="page-stack">
    <header class="page-heading"><div><h2>我的项目页</h2><p>飞书组织信息会在每次登录时刷新；角色由映射规则或管理员覆写决定。</p></div></header>
    <section class="surface profile-panel">
      <n-avatar round :size="64" :src="member?.avatar_url || undefined">{{ member?.name?.slice(0, 1) }}</n-avatar>
      <div><h3>{{ member?.name }}</h3><n-tag :bordered="false" type="info">{{ roleLabel }}</n-tag></div>
    </section>
    <section class="surface profile-fields">
      <dl><dt>飞书部门</dt><dd>{{ member?.department_names?.join("、") || member?.department_ids?.join("、") || "未同步" }}</dd></dl>
      <dl><dt>飞书职位</dt><dd>{{ member?.job_title_name || member?.job_title_id || "未同步" }}</dd></dl>
      <dl><dt>GitHub 账号</dt><dd>{{ member?.github_login || "尚未绑定" }}</dd></dl>
      <dl><dt>权限来源</dt><dd>{{ member?.manual_role ? "管理员手动设置" : "飞书部门/职位自动映射" }}</dd></dl>
    </section>
    <section class="surface quick-links">
      <RouterLink to="/risks"><span><strong>风险与决策</strong><small>查看或登记项目风险</small></span><n-icon><ChevronForwardOutline /></n-icon></RouterLink>
      <RouterLink v-if="store.isAdmin" to="/admin"><span><strong>项目设置</strong><small>角色映射、成员与集成状态</small></span><n-icon><ChevronForwardOutline /></n-icon></RouterLink>
    </section>
  </div>
</template>
<script setup lang="ts">
import { computed } from "vue";
import { NAvatar, NIcon, NTag } from "naive-ui";
import { ChevronForwardOutline } from "@vicons/ionicons5";
import { useProjectStore } from "../store";
const store = useProjectStore(); const member = computed(() => store.member);
const labels: Record<string,string> = { project_admin: "项目管理员", project_lead: "项目负责人", team_lead: "小组负责人", contributor: "项目成员", observer: "观察者" };
const roleLabel = computed(() => labels[member.value?.role || ""] || "未分配");
</script>
<style scoped>
.profile-panel { padding: 24px; display: flex; align-items: center; gap: 16px; }
.profile-panel h3 { margin-bottom: 6px; color: #172033; font-size: 19px; }
.profile-fields { display: grid; grid-template-columns: repeat(2, 1fr); }
.profile-fields dl { padding: 18px 20px; border-bottom: 1px solid #edf1f5; }
.profile-fields dl:nth-child(odd) { border-right: 1px solid #edf1f5; }
.profile-fields dt { color: #64748b; font-size: 12px; }
.profile-fields dd { margin-top: 5px; color: #334155; font-size: 14px; overflow-wrap: anywhere; }
.quick-links a { min-height: 68px; padding: 12px 20px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #edf1f5; color: #334155; }
.quick-links a:last-child { border-bottom: 0; }
.quick-links a:hover { background: #f8fafc; }
.quick-links span { min-width: 0; flex: 1; display: flex; flex-direction: column; }
.quick-links small { margin-top: 2px; color: #64748b; }
@media (max-width: 600px) { .profile-fields { grid-template-columns: 1fr; } .profile-fields dl:nth-child(odd) { border-right: 0; } }
</style>

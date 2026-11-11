<template>
  <div class="page-stack">
    <header class="page-heading">
      <div><h2>风险与决策</h2><p>尽早暴露阻塞和不确定性；解决方案与负责人保持可追踪。</p></div>
      <n-space>
        <n-button v-if="store.canLead" @click="showDecision = true">记录决策</n-button>
        <n-button v-if="store.canContribute" type="primary" @click="showCreate = true">登记风险</n-button>
      </n-space>
    </header>
    <n-skeleton v-if="loading" text :repeat="7" />
    <section v-else class="surface">
      <div v-if="!risks.length" class="empty-state"><div><strong>当前没有登记风险</strong>发现阻塞或不确定性时及时登记，而不是等到延期后再补充。</div></div>
      <article v-for="risk in risks" :key="risk.id" class="risk-row list-row">
        <span class="risk-level" :class="`risk-level--${risk.severity}`">{{ severityLabel(risk.severity) }}</span>
        <div class="list-row__main">
          <div class="list-row__title">{{ risk.title }}</div>
          <div class="list-row__meta">{{ statusLabel(risk.status) }} · {{ risk.owner_name || "未指定负责人" }} · {{ risk.due_date ? `截止 ${risk.due_date}` : "无截止日期" }}</div>
          <p v-if="risk.description">{{ risk.description }}</p>
          <p v-if="risk.mitigation" class="mitigation"><strong>应对：</strong>{{ risk.mitigation }}</p>
        </div>
        <n-select v-if="store.canLead" :value="risk.status" :options="statusOptions" size="small" style="width: 112px" @update:value="(value) => updateStatus(risk.id, value)" />
      </article>
    </section>

    <section class="surface">
      <div class="section-header"><div><h3>项目决策记录</h3><p>记录决定、背景与理由，减少重复讨论和信息丢失</p></div></div>
      <div v-if="!decisions.length" class="empty-state"><div><strong>还没有正式决策</strong>小组负责人可记录影响范围较大的项目决定。</div></div>
      <article v-for="item in decisions" :key="item.id" class="decision-row list-row">
        <div class="list-row__main">
          <div class="list-row__title">{{ item.title }} <n-tag v-if="item.status === 'superseded'" size="small">已替代</n-tag></div>
          <div class="list-row__meta">{{ item.decided_by_name || "未知成员" }} · {{ formatTime(item.decided_at) }}</div>
          <p v-if="item.context"><strong>背景：</strong>{{ item.context }}</p>
          <p class="decision-result"><strong>决定：</strong>{{ item.decision }}</p>
          <p v-if="item.rationale"><strong>理由：</strong>{{ item.rationale }}</p>
        </div>
      </article>
    </section>
    <n-alert v-if="message" :type="messageType" :show-icon="true">{{ message }}</n-alert>

    <n-modal v-model:show="showCreate" preset="card" title="登记项目风险" class="risk-modal">
      <n-form label-placement="top">
        <n-form-item label="风险标题" required><n-input v-model:value="form.title" maxlength="240" /></n-form-item>
        <div class="form-grid">
          <n-form-item label="级别"><n-select v-model:value="form.severity" :options="severityOptions" /></n-form-item>
          <n-form-item label="负责人"><n-select v-model:value="form.owner_member_id" clearable :options="memberOptions" /></n-form-item>
          <n-form-item class="span-2" label="风险说明"><n-input v-model:value="form.description" type="textarea" :rows="3" /></n-form-item>
          <n-form-item class="span-2" label="应对方案"><n-input v-model:value="form.mitigation" type="textarea" :rows="3" /></n-form-item>
        </div>
        <n-space justify="end"><n-button @click="showCreate = false">取消</n-button><n-button type="primary" :loading="saving" :disabled="!form.title.trim()" @click="createRisk">保存风险</n-button></n-space>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showDecision" preset="card" title="记录项目决策" class="risk-modal">
      <n-form label-placement="top">
        <n-form-item label="决策标题" required><n-input v-model:value="decisionForm.title" maxlength="240" /></n-form-item>
        <n-form-item label="背景"><n-input v-model:value="decisionForm.context" type="textarea" :rows="2" /></n-form-item>
        <n-form-item label="最终决定" required><n-input v-model:value="decisionForm.decision" type="textarea" :rows="3" /></n-form-item>
        <n-form-item label="理由"><n-input v-model:value="decisionForm.rationale" type="textarea" :rows="2" /></n-form-item>
        <n-form-item label="决策人"><n-select v-model:value="decisionForm.decided_by_member_id" clearable :options="memberOptions" placeholder="默认当前用户" /></n-form-item>
        <n-space justify="end"><n-button @click="showDecision = false">取消</n-button><n-button type="primary" :loading="saving" :disabled="!decisionForm.title.trim() || !decisionForm.decision.trim()" @click="createDecision">保存决策</n-button></n-space>
      </n-form>
    </n-modal>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { NAlert, NButton, NForm, NFormItem, NInput, NModal, NSelect, NSkeleton, NSpace, NTag } from "naive-ui";
import api, { errorMessage } from "../api";
import { useProjectStore } from "../store";
const store = useProjectStore();
const risks = ref<any[]>([]); const decisions = ref<any[]>([]); const members = ref<any[]>([]); const loading = ref(true); const saving = ref(false); const showCreate = ref(false); const showDecision = ref(false);
const message = ref(""); const messageType = ref<"success" | "error">("success");
const form = ref({ title: "", description: "", severity: "medium", mitigation: "", owner_member_id: null as number | null });
const decisionForm = ref({ title: "", context: "", decision: "", rationale: "", decided_by_member_id: null as number | null });
const severityOptions = [{ label: "低", value: "low" }, { label: "中", value: "medium" }, { label: "高", value: "high" }, { label: "严重", value: "critical" }];
const statusOptions = [{ label: "开放", value: "open" }, { label: "应对中", value: "mitigating" }, { label: "已解决", value: "resolved" }, { label: "已接受", value: "accepted" }];
const memberOptions = computed(() => members.value.map((item) => ({ label: item.name, value: item.id })));
const severityLabel = (value: string) => ({ low: "低", medium: "中", high: "高", critical: "严重" } as Record<string,string>)[value] || value;
const statusLabel = (value: string) => ({ open: "开放", mitigating: "应对中", resolved: "已解决", accepted: "已接受" } as Record<string,string>)[value] || value;
const formatTime = (value: string) => new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "numeric", day: "numeric" }).format(new Date(value));
async function load() {
  loading.value = true;
  try { const [riskRes, decisionRes, memberRes] = await Promise.all([api.get("/risks"), api.get("/decisions"), api.get("/members")]); risks.value = riskRes.data; decisions.value = decisionRes.data; members.value = memberRes.data; }
  catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "风险列表加载失败"); }
  finally { loading.value = false; }
}
async function createDecision() {
  saving.value = true; message.value = "";
  try { await api.post("/decisions", decisionForm.value); showDecision.value = false; decisionForm.value = { title: "", context: "", decision: "", rationale: "", decided_by_member_id: null }; messageType.value = "success"; message.value = "项目决策已记录。"; await load(); }
  catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "决策保存失败"); }
  finally { saving.value = false; }
}
async function createRisk() {
  saving.value = true; message.value = "";
  try { await api.post("/risks", form.value); showCreate.value = false; form.value = { title: "", description: "", severity: "medium", mitigation: "", owner_member_id: null }; messageType.value = "success"; message.value = "风险已登记。"; await load(); }
  catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "风险保存失败"); }
  finally { saving.value = false; }
}
async function updateStatus(id: number, status: string) {
  try { await api.patch(`/risks/${id}`, { status }); await load(); }
  catch (reason) { messageType.value = "error"; message.value = errorMessage(reason, "风险状态更新失败"); }
}
onMounted(load);
</script>
<style scoped>
.risk-row { align-items: flex-start; }
.risk-row p { margin-top: 8px; color: #52647b; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
.risk-level { min-width: 44px; padding: 3px 7px; border-radius: 999px; color: #334155; background: #e2e8f0; font-size: 11px; text-align: center; }
.risk-level--high { color: #92400e; background: #fef3c7; }
.risk-level--critical { color: #991b1b; background: #fee2e2; }
.risk-level--low { color: #166534; background: #dcfce7; }
.mitigation { padding: 8px 10px; border-radius: 6px; background: #f8fafc; }
.decision-row { align-items: flex-start; }
.decision-row p { margin-top: 7px; color: #52647b; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
.decision-result { color: #1e293b !important; }
.risk-modal { width: min(620px, calc(100vw - 24px)); }
@media (max-width: 600px) { .risk-row { flex-wrap: wrap; } .risk-row > .n-select { width: 100% !important; } }
</style>

<template>
  <n-modal v-model:show="showModal" :mask-closable="true" preset="card" title="密码重置" style="width: min(420px, calc(100vw - 24px)); max-height: calc(100dvh - 24px)">
    <n-steps :current="step" :status="stepStatus" style="margin-bottom: 24px">
      <n-step title="验证邮箱" description="输入注册邮箱" />
      <n-step title="设置密码" description="输入验证码和新密码" />
    </n-steps>

    <!-- Step 1: Email input -->
    <n-form v-if="step === 0" :model="step1Form" :rules="step1Rules" ref="step1Ref">
      <n-form-item path="email" label="邮箱">
        <n-input v-model:value="step1Form.email" placeholder="请输入注册时使用的邮箱" />
      </n-form-item>
      <n-button type="primary" block :loading="sending" @click="handleSendCode">
        发送验证码
      </n-button>
      <p v-if="step1Msg" class="msg" :class="{ success: step1Success }">{{ step1Msg }}</p>
    </n-form>

    <!-- Step 2: Code + New Password -->
    <n-form v-if="step === 1" :model="step2Form" :rules="step2Rules" ref="step2Ref">
      <n-form-item path="token" label="验证码">
        <n-input v-model:value="step2Form.token" placeholder="请输入6位验证码" maxlength="6" />
      </n-form-item>
      <n-form-item path="new_password" label="新密码">
        <n-input v-model:value="step2Form.new_password" type="password" placeholder="至少6位" show-password-on="click" />
      </n-form-item>
      <n-form-item path="confirm_password" label="确认密码">
        <n-input v-model:value="step2Form.confirm_password" type="password" placeholder="再次输入新密码" />
      </n-form-item>
      <n-button type="primary" block :loading="resetting" @click="handleReset">
        重置密码
      </n-button>
      <p v-if="step2Msg" class="msg" :class="{ success: step2Success }">{{ step2Msg }}</p>
    </n-form>

    <!-- Step 2 complete -->
    <div v-if="step === 2" class="complete-state">
      <n-icon size="48" color="#22C55E"><CheckmarkCircleOutline /></n-icon>
      <p>密码重置成功！请使用新密码登录。</p>
      <n-button type="primary" block @click="handleClose" style="margin-top: 16px">关闭</n-button>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import {
  NModal, NSteps, NStep, NForm, NFormItem, NInput, NButton, NIcon,
} from "naive-ui";
import { CheckmarkCircleOutline } from "@vicons/ionicons5";
import api from "@/api";

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{ "update:show": [value: boolean] }>();

const showModal = computed({
  get: () => props.show,
  set: (val) => emit("update:show", val),
});

const step = ref(0);
const sending = ref(false);
const resetting = ref(false);
const step1Msg = ref("");
const step1Success = ref(false);
const step2Msg = ref("");
const step2Success = ref(false);

const step1Form = ref({ email: "" });
const step2Form = ref({ token: "", new_password: "", confirm_password: "" });

const step1Rules = {
  email: { required: true, message: "请输入邮箱", trigger: "blur" },
};

const step2Rules = {
  token: { required: true, message: "请输入验证码", trigger: "blur" },
  new_password: { required: true, min: 6, message: "密码至少6位", trigger: "blur" },
  confirm_password: [
    { required: true, message: "请确认密码", trigger: "blur" },
    { validator: (_: any, value: string) => value === step2Form.value.new_password, message: "两次密码不一致", trigger: "blur" },
  ],
};

const stepStatus = computed(() => {
  if (step.value === 0 && step1Success.value) return "finish";
  if (step.value === 1 && step2Success.value) return "finish";
  return "process";
});

async function handleSendCode() {
  sending.value = true;
  step1Msg.value = "";
  try {
    await api.post("/auth/reset-password", { email: step1Form.value.email });
    step1Msg.value = "验证码已发送至您的邮箱，请查收";
    step1Success.value = true;
    setTimeout(() => { step.value = 1; }, 1500);
  } catch (e: any) {
    step1Msg.value = e.response?.data?.detail || "发送失败";
    step1Success.value = false;
  } finally {
    sending.value = false;
  }
}

async function handleReset() {
  resetting.value = true;
  step2Msg.value = "";
  try {
    await api.post("/auth/reset-password/confirm", {
      token: step2Form.value.token,
      new_password: step2Form.value.new_password,
    });
    step2Msg.value = "密码重置成功";
    step2Success.value = true;
    setTimeout(() => { step.value = 2; }, 1000);
  } catch (e: any) {
    step2Msg.value = e.response?.data?.detail || "重置失败";
    step2Success.value = false;
  } finally {
    resetting.value = false;
  }
}

function handleClose() {
  showModal.value = false;
  step.value = 0;
  step1Form.value = { email: "" };
  step2Form.value = { token: "", new_password: "", confirm_password: "" };
  step1Msg.value = "";
  step1Success.value = false;
  step2Msg.value = "";
  step2Success.value = false;
}
</script>

<style scoped>
.msg {
  font-size: 13px;
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  color: #EF4444;
  background: #FEF2F2;
}
.msg.success {
  color: #22C55E;
  background: #F0FDF4;
}
.complete-state {
  text-align: center;
  padding: 24px 0;
}
.complete-state p {
  margin-top: 12px;
  color: #64748B;
}
</style>

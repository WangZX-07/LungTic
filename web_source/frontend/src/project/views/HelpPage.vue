<template>
  <div class="page-stack help-page">
    <header class="page-heading help-heading">
      <div><h2>项目门户使用帮助</h2><p>飞书身份、角色规则、进度协作和 GitHub 自动同步的操作手册。</p></div>
      <RouterLink v-if="store.isAdmin" class="settings-link" to="/admin">前往项目设置</RouterLink>
    </header>

    <div class="docs-layout">
      <aside class="docs-nav surface" aria-label="帮助目录">
        <strong>本页目录</strong>
        <button v-for="item in sections" :key="item.id" type="button" @click="scrollToSection(item.id)">{{ item.label }}</button>
      </aside>

      <article class="docs-content surface">
        <section id="quick-start">
          <h3>首次登录</h3>
          <ol>
            <li>在浏览器或飞书工作台打开项目门户，使用飞书完成授权。</li>
            <li>首次登录会同步姓名、部门和职位。未匹配角色的成员暂时不能进入项目数据。</li>
            <li>管理员进入“项目设置”创建部门/职位映射规则。</li>
            <li>飞书组织资料修改后，成员需要退出并重新登录，才能刷新同步数据。</li>
          </ol>
        </section>

        <section id="department-id">
          <h3>部门 ID 怎么填</h3>
          <div class="docs-callout"><strong>只填 open_department_id</strong><span>正确值以 <code>od-</code> 开头，并且应从“项目设置 → 项目成员”复制。</span></div>
          <div class="format-list" aria-label="ID 格式说明">
            <div><code>od-...</code><span>部门 open_department_id，正确</span></div>
            <div><code>ou_...</code><span>用户 Open ID，不是部门</span></div>
            <div><code>cli_...</code><span>飞书应用 ID，不是部门</span></div>
            <div><code>0</code><span>根部门标识，不能用于成员映射</span></div>
          </div>
          <ol>
            <li>让成员先登录门户一次。</li>
            <li>管理员进入“项目设置”，在成员姓名下找到 <code>od-...</code>。</li>
            <li>点击“复制部门 ID”，再点击“新增规则”。</li>
            <li>把它粘贴进“飞书部门 open_department_id”，职位可以先留空。</li>
          </ol>
          <p>成员属于多个部门时会显示多个 ID，可以分别建立规则。项目后端已固定请求 <code>department_id_type=open_department_id</code>，不要混用飞书自定义 department_id。</p>
        </section>

        <section id="role-rules">
          <h3>角色映射规则</h3>
          <div class="docs-table-wrap"><table>
            <thead><tr><th>字段</th><th>填写方法</th></tr></thead>
            <tbody>
              <tr><td>规则名称</td><td>例如“研发部项目成员”</td></tr>
              <tr><td>部门 ID</td><td>从成员列表复制的 <code>od-...</code></td></tr>
              <tr><td>职位 ID</td><td>仅填写真正的职位 ID，不能填写 <code>od-...</code></td></tr>
              <tr><td>职位名称</td><td>按飞书通讯录的完整文本匹配，例如“技术负责人”</td></tr>
              <tr><td>优先级</td><td>数值越大越优先；建议成员 100、组长 200、负责人 300</td></tr>
            </tbody>
          </table></div>
          <p>同一条规则里的多个条件是“并且”关系。成员命中多条规则时，优先级最高的规则生效。成员下拉框中的手动角色优先于所有自动规则，清空后恢复自动映射。</p>
          <div class="docs-warning"><strong>你截图中的两条规则填错了</strong><span>“任意部门 · 职位 0”和“任意部门 · 职位 od-...”都应删除。重新建规则，把 <code>od-...</code> 放到部门字段，职位留空。</span></div>
        </section>

        <section id="job-title">
          <h3>为什么显示“职位未同步”</h3>
          <p>门户读取飞书通讯录用户资料中的职位字段。如果成员已经有部门 ID，但显示“飞书资料未填写职位”，通常表示该成员的飞书资料没有填写职位；如果部门也没有同步，则更可能是应用通讯录权限或可用范围不足。</p>
          <ol>
            <li>飞书管理员进入组织架构/成员管理，打开该成员资料，确认“职位”已填写并保存。</li>
            <li>开放平台进入该自建应用的“权限管理”，检查“获取单个用户”Contact v3 所需权限。</li>
            <li>确认应用通讯录可用范围包含该成员和部门，并重新发布、完成审核。</li>
            <li>让成员退出门户并重新登录。</li>
          </ol>
          <p>不需要按职位细分时，只按部门 ID 创建规则最简单，所有职位字段都可以留空。</p>
        </section>

        <section id="roles">
          <h3>项目角色与权限</h3>
          <div class="docs-table-wrap"><table>
            <thead><tr><th>角色</th><th>主要权限</th></tr></thead>
            <tbody>
              <tr><td>项目管理员</td><td>成员、规则、集成和全部项目数据</td></tr>
              <tr><td>项目负责人</td><td>里程碑、任务、风险、决策和全部进度</td></tr>
              <tr><td>小组负责人</td><td>创建/分配任务，更新任务和风险，提交进度</td></tr>
              <tr><td>项目成员</td><td>更新本人任务、提交本人进度、登记风险</td></tr>
              <tr><td>观察者</td><td>只读查看</td></tr>
              <tr><td>未分配</td><td>等待管理员完成角色映射</td></tr>
            </tbody>
          </table></div>
        </section>

        <section id="daily-use">
          <h3>日常使用</h3>
          <ul>
            <li><strong>总览：</strong>查看总体完成度、里程碑、近期进度和风险。</li>
            <li><strong>任务：</strong>负责人分配任务，成员更新本人任务状态与完成比例。</li>
            <li><strong>进度：</strong>填写本期完成、下一步、阻塞项和证据链接。</li>
            <li><strong>风险与决策：</strong>记录风险等级、处置方案和关键决策。</li>
            <li><strong>动态：</strong>查看 GitHub Push、PR、Issue、工作流和 Release。</li>
          </ul>
        </section>

        <section id="github">
          <h3>GitHub 历史、动态与完成度</h3>
          <p>“已配置”只表示服务器环境变量完整。管理员可以在“动态”页点击“同步历史”，回填已有提交、Issue、PR、工作流和 Release；之后的新事件继续由 Webhook 记录。</p>
          <ol>
            <li>选择历史范围；最多扫描 20 个分支、每类导入 300 条，提交按 SHA 去重，重复同步会更新而不是重复创建。</li>
            <li>勾选“同时导入 Issue/PR 为任务”，关闭的 Issue 和已合并 PR 会作为已完成任务参与计算。</li>
            <li>提交、工作流和 Release 只作为证据，不会用数量直接换算百分比。</li>
            <li>Webhook 异常时，在 GitHub 仓库 Settings → Webhooks → Recent Deliveries 检查；正常投递应返回 HTTP <code>202</code>。</li>
          </ol>
          <p>没有任何任务时，总览显示“—”而不是 0%。有任务后，完成度按任务权重和各任务完成比例计算；管理员仍应根据真实交付范围调整任务权重。</p>
        </section>

        <section id="troubleshooting">
          <h3>常见问题</h3>
          <dl class="faq-list">
            <div><dt>成员列表没有某人</dt><dd>让该成员先通过飞书登录一次。</dd></div>
            <div><dt>部门 ID 为空</dt><dd>检查通讯录权限、应用可用范围和发布状态，然后重新登录。</dd></div>
            <div><dt>自动角色未分配</dt><dd>确认 <code>od-...</code> 位于部门字段、规则已启用，并检查优先级。</dd></div>
            <div><dt>改规则后角色仍不对</dt><dd>先检查成员是否设置了手动角色，手动角色优先。</dd></div>
            <div><dt>飞书资料已修改但页面没变</dt><dd>退出门户并重新登录，触发组织信息同步。</dd></div>
          </dl>
        </section>

        <section id="security">
          <h3>安全注意事项</h3>
          <ul>
            <li>App Secret、GitHub Webhook Secret 和数据库密码只保存在服务器受限环境文件。</li>
            <li>Secret 不发送到聊天，不进入截图、帮助文档或 GitHub 仓库。</li>
            <li>飞书应用仅申请最小通讯录权限，并限制应用可用范围。</li>
            <li>项目角色与临床病例权限完全隔离。</li>
          </ul>
          <p class="official-links">官方参考：<a href="https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/contact-v3/department" target="_blank" rel="noopener noreferrer">飞书部门资源介绍</a> · <a href="https://open.feishu.cn/document/server-docs/contact-v3/user/get" target="_blank" rel="noopener noreferrer">获取单个用户</a></p>
        </section>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useProjectStore } from "../store";

const store = useProjectStore();
const sections = [
  { id: "quick-start", label: "首次登录" },
  { id: "department-id", label: "部门 ID 怎么填" },
  { id: "role-rules", label: "角色映射规则" },
  { id: "job-title", label: "职位未同步" },
  { id: "roles", label: "角色与权限" },
  { id: "daily-use", label: "日常使用" },
  { id: "github", label: "GitHub 动态" },
  { id: "troubleshooting", label: "常见问题" },
  { id: "security", label: "安全说明" },
];
function scrollToSection(id: string) {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.getElementById(id)?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
}
</script>

<style scoped>
.help-heading { align-items: center; }
.settings-link { min-height: 34px; padding: 7px 13px; border-radius: 6px; background: var(--color-primary); color: #fff; font-size: 13px; font-weight: 600; }
.settings-link:hover { background: #1478d0; }
.docs-layout { display: grid; grid-template-columns: 210px minmax(0, 1fr); align-items: start; gap: 20px; }
.docs-nav { position: sticky; top: 84px; padding: 14px 0; display: flex; flex-direction: column; }
.docs-nav strong { padding: 4px 16px 10px; color: #1e293b; font-size: 13px; }
.docs-nav button { width: 100%; padding: 8px 16px; border: 0; background: transparent; color: #526178; font: inherit; font-size: 12px; line-height: 18px; text-align: left; cursor: pointer; }
.docs-nav button:hover { background: #f1f6fb; color: var(--color-primary); }
.docs-nav button:focus-visible { outline: 2px solid #90caf9; outline-offset: -2px; }
.docs-content { padding: 4px 32px 32px; color: #334155; font-size: 14px; line-height: 1.75; }
.docs-content section { padding-top: 28px; scroll-margin-top: 80px; }
.docs-content section + section { margin-top: 8px; border-top: 1px solid #e8edf3; }
.docs-content h3 { margin-bottom: 12px; color: #172033; font-size: 20px; line-height: 28px; text-wrap: balance; }
.docs-content p { max-width: 75ch; margin: 10px 0; }
.docs-content ol, .docs-content ul { max-width: 75ch; margin: 10px 0; padding-left: 22px; }
.docs-content li + li { margin-top: 6px; }
.docs-content code { padding: 2px 5px; border-radius: 4px; background: #eef3f8; color: #174f85; font-family: Consolas, "SFMono-Regular", monospace; font-size: 0.92em; overflow-wrap: anywhere; }
.docs-callout, .docs-warning { max-width: 75ch; margin: 14px 0; padding: 13px 15px; border-radius: 8px; display: flex; flex-direction: column; gap: 3px; }
.docs-callout { background: #eaf5ff; color: #194f7d; }
.docs-warning { background: #fff5df; color: #7c4a03; }
.docs-callout strong, .docs-warning strong { color: inherit; }
.format-list { max-width: 75ch; margin: 14px 0; border-top: 1px solid #e6ebf1; }
.format-list div { padding: 9px 4px; border-bottom: 1px solid #e6ebf1; display: grid; grid-template-columns: 120px 1fr; gap: 12px; }
.docs-table-wrap { max-width: 75ch; margin: 14px 0; overflow-x: auto; }
.docs-content table { width: 100%; border-collapse: collapse; text-align: left; }
.docs-content th, .docs-content td { padding: 10px 12px; border-bottom: 1px solid #e5eaf0; vertical-align: top; }
.docs-content th { background: #f6f8fb; color: #334155; font-size: 12px; }
.faq-list { max-width: 75ch; margin: 8px 0; }
.faq-list div { padding: 12px 0; border-bottom: 1px solid #e8edf3; }
.faq-list dt { color: #1e293b; font-weight: 650; }
.faq-list dd { margin-top: 3px; color: #526178; }
.official-links { color: #64748b; font-size: 12px; }
.official-links a { color: var(--color-primary); }
@media (max-width: 800px) {
  .docs-layout { grid-template-columns: 1fr; }
  .docs-nav { position: static; padding: 12px; flex-direction: row; flex-wrap: wrap; gap: 6px; }
  .docs-nav strong { width: 100%; padding: 0 4px 6px; }
  .docs-nav button { width: auto; padding: 6px 9px; border-radius: 5px; background: #f4f7fa; }
  .docs-content { padding: 0 18px 24px; }
}
@media (max-width: 520px) {
  .help-heading { align-items: flex-start; }
  .format-list div { grid-template-columns: 90px 1fr; }
  .docs-content { font-size: 13px; }
  .docs-content h3 { font-size: 18px; }
}
</style>

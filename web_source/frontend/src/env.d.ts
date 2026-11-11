/// <reference types="vite/client" />

interface FeishuAuthResult { code: string }
interface FeishuAuthError { errno?: number; errString?: string }
interface FeishuWebApi {
  requestAccess?: (options: {
    appID: string; scopeList: string[];
    success: (result: FeishuAuthResult) => void;
    fail: (error: FeishuAuthError) => void;
  }) => void;
  requestAuthCode?: (options: {
    appId: string;
    success: (result: FeishuAuthResult) => void;
    fail: (error: FeishuAuthError) => void;
  }) => void;
}

interface Window { tt?: FeishuWebApi }
declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

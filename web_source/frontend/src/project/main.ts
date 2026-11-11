import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "@/App.vue";
import router from "./router";
import "@/styles/grid.css";
import "./project.css";

createApp(App).use(createPinia()).use(router).mount("#app");

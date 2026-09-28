<template>
  <footer class="icp-footer" :class="{ 'icp-footer--inverse': inverse }">
    <a
      href="http://beian.miit.gov.cn/"
      target="_blank"
      rel="noopener noreferrer"
    >
      辽ICP备2026005104号-2
    </a>
  </footer>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ inverse?: boolean }>(), {
  inverse: false,
});
</script>

<style scoped>
.icp-footer {
  flex: 0 0 auto;
  padding: 12px 16px;
  color: #52647b;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
}

.icp-footer a {
  color: inherit;
  text-decoration: none;
  text-underline-offset: 3px;
}

.icp-footer a:hover {
  color: #1565c0;
  text-decoration: underline;
}

.icp-footer a:focus-visible {
  border-radius: 3px;
  outline: 2px solid #1e88e5;
  outline-offset: 3px;
}

.icp-footer--inverse {
  color: rgba(255, 255, 255, 0.82);
}

.icp-footer--inverse a:hover {
  color: #fff;
}

.icp-footer--inverse a:focus-visible {
  outline-color: #fff;
}
</style>

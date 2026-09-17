<template>
  <div class="target-3d">
    <n-grid cols="4" x-gap="16">
      <n-grid-item span="3">
        <n-card size="small" title="IGTV 三维靶区" class="viewer-card">
          <template #header-extra>
            <n-space>
              <n-tag v-if="igtvData" type="success" size="small">
                体积 {{ igtvData.volume_cc?.toFixed(2) || "-" }} cc
              </n-tag>
            </n-space>
          </template>
          <div class="threejs-container" ref="containerRef">
            <div v-if="!sceneReady && !loadingMesh" class="placeholder">
              <n-icon size="64" color="#CBD5E1"><CubeOutline /></n-icon>
              <p>3D IGTV 靶区视图</p>
              <p class="hint">执行分割和 IGTV 重建后将在此显示三维模型</p>
            </div>
            <n-spin v-if="loadingMesh" class="loading-overlay" />
          </div>
        </n-card>
      </n-grid-item>

      <n-grid-item span="1">
        <n-space vertical :size="16">
          <n-card size="small" title="IGTV 信息">
            <div v-if="igtvData" class="info">
              <div class="info-item">
                <span class="label">体积</span>
                <span class="value">{{ igtvData.volume_cc?.toFixed(2) || "-" }} cc</span>
              </div>
              <div class="info-item">
                <span class="label">网格</span>
                <span class="value">{{ igtvData.mesh_path ? "已生成" : "暂无" }}</span>
              </div>
            </div>
            <p v-else class="text-muted">未重建 IGTV</p>
          </n-card>

          <n-button type="primary" block @click="reconstruct" :loading="reconstructing">
            重建 IGTV
          </n-button>

          <n-card size="small" title="视图控制">
            <n-space vertical :size="8">
              <n-button size="small" quaternary @click="resetCamera">
                <template #icon><n-icon><LocateOutline /></n-icon></template>
                重置视角
              </n-button>
              <n-button size="small" quaternary @click="toggleWireframe">
                <template #icon><n-icon><GitNetworkOutline /></n-icon></template>
                {{ wireframe ? "实体" : "线框" }}
              </n-button>
              <n-button size="small" quaternary @click="toggleAutoRotate">
                <template #icon><n-icon><SyncOutline /></n-icon></template>
                {{ autoRotate ? "停止旋转" : "自动旋转" }}
              </n-button>
            </n-space>
          </n-card>

          <n-card size="small" title="显示设置">
            <n-space vertical :size="8">
              <div class="setting-row">
                <span>透明度</span>
                <n-slider v-model:value="opacity" :min="0.2" :max="1" :step="0.1" style="width:100px" @update:value="updateOpacity" />
              </div>
            </n-space>
          </n-card>
        </n-space>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import {
  NGrid, NGridItem, NCard, NSpace, NButton, NIcon, NTag, NSpin, NSlider, useMessage,
} from "naive-ui";
import {
  CubeOutline, LocateOutline, GitNetworkOutline, SyncOutline,
} from "@vicons/ionicons5";
import * as THREE from "three";
import api from "@/api";

const props = defineProps<{ studyId: number }>();
const message = useMessage();

const containerRef = ref<HTMLDivElement>();
const sceneReady = ref(false);
const reconstructing = ref(false);
const loadingMesh = ref(false);
const igtvData = ref<any>(null);
const wireframe = ref(false);
const autoRotate = ref(false);
const opacity = ref(0.8);

let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let meshGroup: THREE.Group;
let animationId: number;
let isDragging = false;
let prevMouse = { x: 0, y: 0 };
let spherical = { theta: Math.PI / 4, phi: Math.PI / 3, radius: 200 };

function initScene() {
  if (!containerRef.value) return;

  const width = containerRef.value.clientWidth;
  const height = containerRef.value.clientHeight;

  scene = new THREE.Scene();
  scene.background = new THREE.Color("#0F172A");

  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
  camera.position.set(120, 80, 160);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  containerRef.value.appendChild(renderer.domElement);

  // Lights
  const ambientLight = new THREE.AmbientLight(0x404060, 1.5);
  scene.add(ambientLight);

  const directionalLight1 = new THREE.DirectionalLight(0xffffff, 1.2);
  directionalLight1.position.set(1, 1, 1);
  scene.add(directionalLight1);

  const directionalLight2 = new THREE.DirectionalLight(0x1E88E5, 0.5);
  directionalLight2.position.set(-1, -0.5, -0.5);
  scene.add(directionalLight2);

  // Grid
  const gridHelper = new THREE.GridHelper(200, 20, "#334155", "#1E293B");
  scene.add(gridHelper);

  // Axes indicator
  const axesHelper = new THREE.AxesHelper(80);
  scene.add(axesHelper);

  meshGroup = new THREE.Group();
  scene.add(meshGroup);

  // Default placeholder geometry
  addPlaceholderGeometry();

  // Mouse events
  renderer.domElement.addEventListener("mousedown", onMouseDown);
  renderer.domElement.addEventListener("mousemove", onMouseMove);
  renderer.domElement.addEventListener("mouseup", onMouseUp);
  renderer.domElement.addEventListener("wheel", onWheel);

  window.addEventListener("resize", onResize);

  sceneReady.value = true;
  animate();
}

function addPlaceholderGeometry() {
  // A simple sphere as placeholder until IGTV mesh loads
  const geometry = new THREE.SphereGeometry(30, 32, 32);
  const material = new THREE.MeshPhongMaterial({
    color: "#1E88E5",
    transparent: true,
    opacity: 0.3,
    wireframe: wireframe.value,
  });
  const sphere = new THREE.Mesh(geometry, material);
  sphere.name = "placeholder";
  meshGroup.add(sphere);
}

function add体积Visualization(volumeCc: number, vertices?: number[][]) {
  // Clear previous
  while (meshGroup.children.length > 0) {
    meshGroup.remove(meshGroup.children[0]);
  }

  if (vertices && vertices.length > 0) {
    // Create mesh from vertices (point cloud + convex hull approximation)
    const points: THREE.Vector3[] = vertices.map(
      (v) => new THREE.Vector3(v[0], v[1], v[2])
    );

    // Point cloud
    const pointGeo = new THREE.BufferGeometry().setFromPoints(points);
    const pointMat = new THREE.PointsMaterial({
      color: "#22C55E",
      size: 1.5,
      transparent: true,
      opacity: 0.6,
    });
    const pointCloud = new THREE.Points(pointGeo, pointMat);
    meshGroup.add(pointCloud);

    // Wireframe bounding sphere
    const radius = Math.cbrt((volumeCc * 3) / (4 * Math.PI)) * 5; // approximate
    const sphereGeo = new THREE.SphereGeometry(radius, 32, 32);
    const sphereMat = new THREE.MeshPhongMaterial({
      color: "#1E88E5",
      transparent: true,
      opacity: opacity.value,
      wireframe: wireframe.value,
    });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    sphere.name = "igtv-volume";
    meshGroup.add(sphere);
  } else {
    // 体积-based sphere approximation
    const radius = Math.cbrt((volumeCc * 3) / (4 * Math.PI)) * 5;
    const geometry = new THREE.SphereGeometry(radius, 48, 48);
    const material = new THREE.MeshPhongMaterial({
      color: "#1E88E5",
      transparent: true,
      opacity: opacity.value,
      wireframe: wireframe.value,
      emissive: "#0D47A1",
      emissiveIntensity: 0.2,
    });
    const volumeSphere = new THREE.Mesh(geometry, material);
    volumeSphere.name = "igtv-volume";
    meshGroup.add(volumeSphere);

    // Add wireframe overlay
    const wireGeo = new THREE.SphereGeometry(radius * 1.02, 24, 24);
    const wireMat = new THREE.MeshBasicMaterial({
      color: "#42A5F5",
      wireframe: true,
      transparent: true,
      opacity: 0.15,
    });
    meshGroup.add(new THREE.Mesh(wireGeo, wireMat));
  }
}

function onMouseDown(e: MouseEvent) {
  isDragging = true;
  prevMouse = { x: e.clientX, y: e.clientY };
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging) return;
  const dx = e.clientX - prevMouse.x;
  const dy = e.clientY - prevMouse.y;

  spherical.theta -= dx * 0.005;
  spherical.phi -= dy * 0.005;
  spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi));

  updateCameraPosition();
  prevMouse = { x: e.clientX, y: e.clientY };
}

function onMouseUp() { isDragging = false; }

function onWheel(e: WheelEvent) {
  e.preventDefault();
  spherical.radius += e.deltaY * 0.5;
  spherical.radius = Math.max(40, Math.min(500, spherical.radius));
  updateCameraPosition();
}

function updateCameraPosition() {
  camera.position.set(
    spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta),
    spherical.radius * Math.cos(spherical.phi),
    spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta)
  );
  camera.lookAt(0, 0, 0);
}

function onResize() {
  if (!containerRef.value || !renderer) return;
  const w = containerRef.value.clientWidth;
  const h = containerRef.value.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

function animate() {
  animationId = requestAnimationFrame(animate);
  if (autoRotate.value) {
    spherical.theta += 0.005;
    updateCameraPosition();
  }
  renderer.render(scene, camera);
}

function resetCamera() {
  spherical = { theta: Math.PI / 4, phi: Math.PI / 3, radius: 200 };
  updateCameraPosition();
}

function toggleWireframe() {
  wireframe.value = !wireframe.value;
  meshGroup.children.forEach((child: THREE.Object3D) => {
    if (child instanceof THREE.Mesh && child.name === "igtv-volume") {
      const mat = child.material as THREE.MeshPhongMaterial;
      mat.wireframe = wireframe.value;
    }
  });
}

function toggleAutoRotate() {
  autoRotate.value = !autoRotate.value;
}

function updateOpacity() {
  meshGroup.children.forEach((child: THREE.Object3D) => {
    if (child instanceof THREE.Mesh && child.name === "igtv-volume") {
      const mat = child.material as THREE.MeshPhongMaterial;
      mat.opacity = opacity.value;
    }
  });
}

async function loadIgtv() {
  loadingMesh.value = true;
  try {
    const res = await api.get(`/igtv/${props.studyId}`);
    if (res.data) {
      igtvData.value = res.data;
      if (igtvData.value.volume_cc) {
        await nextTick();
        if (!sceneReady.value) initScene();
        add体积Visualization(igtvData.value.volume_cc);
      }
    }
  } catch {}
  finally { loadingMesh.value = false; }
}

async function reconstruct() {
  reconstructing.value = true;
  try {
    const res = await api.post("/igtv/reconstruct", { study_id: props.studyId });
    message.success(res.data.message || "IGTV 重建已启动");
    // Poll for completion
    let retries = 0;
    while (retries < 20) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        const result = await api.get(`/igtv/${props.studyId}`);
        if (result.data?.volume_cc) {
          igtvData.value = result.data;
          await nextTick();
          if (!sceneReady.value) initScene();
          add体积Visualization(result.data.volume_cc);
          message.success("IGTV 重建完成");
          break;
        }
      } catch {}
      retries++;
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || "重建失败");
  } finally { reconstructing.value = false; }
}

onMounted(() => {
  nextTick(() => {
    initScene();
    loadIgtv();
  });
});

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId);
  window.removeEventListener("resize", onResize);
  if (renderer) {
    renderer.dispose();
    if (containerRef.value && renderer.domElement) {
      containerRef.value.removeChild(renderer.domElement);
    }
  }
});
</script>

<style scoped>
.target-3d { width: 100%; }
.viewer-card { height: 100%; }
.threejs-container {
  position: relative;
  min-height: 450px;
  background: #0F172A;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: grab;
}
.threejs-container:active { cursor: grabbing; }
.placeholder { text-align: center; color: #94A3B8; z-index: 1; position: absolute; }
.placeholder p { margin-top: 16px; }
.hint { font-size: 12px; color: #64748B; margin-top: 8px !important; }
.loading-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex; align-items: center; justify-content: center;
  z-index: 2;
}
.info { font-size: 12px; }
.info-item { display: flex; justify-content: space-between; padding: 4px 0; }
.label { color: #64748B; }
.value { font-weight: 600; color: #1E88E5; }
.text-muted { color: #94A3B8; font-size: 12px; }
.setting-row { display: flex; align-items: center; justify-content: space-between; font-size: 12px; }
</style>
import * as THREE from 'three';
import type { Engine } from './model';

export type Effects = {
  group: THREE.Group;
  update: (time: number, delta: number, running: boolean, intensity: number) => void;
  setVisible: (visible: boolean) => void;
};

export function createEffects(engine: Engine): Effects {
  const group = new THREE.Group();
  group.name = 'operating-effects';
  const combustor = engine.modules.find(m => m.meta.id === 'combustor')?.group;
  const exhaust = engine.modules.find(m => m.meta.id === 'exhaust')?.group;

  const count = 1400;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const lanes = new Float32Array(count * 4); // x, radius, angle, speed
  const cold = new THREE.Color('#5fd8ff');
  const warm = new THREE.Color('#ff8a3d');
  const startX = 2.25, spanX = 4.1;
  for (let i = 0; i < count; i++) {
    const core = Math.random() < 0.42;
    lanes[i * 4] = startX - Math.random() * spanX;
    lanes[i * 4 + 1] = core ? 0.08 + Math.random() * 0.26 : 0.42 + Math.random() * 0.28;
    lanes[i * 4 + 2] = Math.random() * Math.PI * 2;
    lanes[i * 4 + 3] = 0.55 + Math.random() * 0.75;
    const color = lanes[i * 4] < 0.35 ? warm : cold;
    colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const material = new THREE.PointsMaterial({
    size: 0.022, vertexColors: true, transparent: true, opacity: 0.9,
    blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
  });
  const flow = new THREE.Points(geometry, material);
  flow.frustumCulled = false;
  group.add(flow);

  const glowMaterial = new THREE.MeshBasicMaterial({
    color: '#ff7a2a', transparent: true, opacity: 0, blending: THREE.AdditiveBlending,
    depthWrite: false, side: THREE.DoubleSide,
  });
  const glow = new THREE.Mesh(new THREE.TorusGeometry(0.38, 0.1, 12, 48), glowMaterial);
  glow.rotation.y = Math.PI / 2;
  glow.position.set(0.08, 0, 0);
  group.add(glow);

  const flameMaterial = new THREE.MeshBasicMaterial({
    color: '#ff9a3c', transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const flame = new THREE.Mesh(new THREE.ConeGeometry(0.42, 0.9, 24, 1, true), flameMaterial);
  flame.rotation.z = Math.PI / 2;
  flame.position.set(0.0, 0, 0);
  group.add(flame);

  const plumeMaterial = new THREE.MeshBasicMaterial({
    color: '#ff6a1f', transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const plume = new THREE.Mesh(new THREE.ConeGeometry(0.32, 1.5, 24, 1, true), plumeMaterial);
  plume.rotation.z = -Math.PI / 2;
  plume.position.set(-2.45, 0, 0);
  group.add(plume);

  const lights = [
    new THREE.PointLight('#ff8a3a', 0, 3.2, 2),
    new THREE.PointLight('#ffb066', 0, 2.6, 2),
  ];
  lights[0].position.set(0.08, 0, 0);
  lights[1].position.set(-1.6, 0, 0);
  group.add(lights[0], lights[1]);
  // Keep effects in world space next to the module they describe.
  if (combustor) engine.root.add(group);
  else engine.root.add(group);

  let strength = 0;
  const positionAttr = geometry.getAttribute('position') as THREE.BufferAttribute;

  return {
    group,
    setVisible(visible: boolean) { group.visible = visible; },
    update(time: number, delta: number, running: boolean, intensity: number) {
      strength += ((running ? 1 : 0) - strength) * Math.min(1, delta * 3);
      const visible = strength > 0.01;
      flow.visible = visible;
      glow.visible = visible;
      flame.visible = visible;
      plume.visible = visible;
      if (!visible) return;

      for (let i = 0; i < count; i++) {
        let x = lanes[i * 4] - delta * lanes[i * 4 + 3] * strength * 1.35;
        if (x < -2.1) {
          x += spanX;
          lanes[i * 4 + 1] = Math.random() < 0.42 ? 0.08 + Math.random() * 0.26 : 0.42 + Math.random() * 0.28;
          lanes[i * 4 + 2] = Math.random() * Math.PI * 2;
        }
        lanes[i * 4] = x;
        const r = lanes[i * 4 + 1];
        const a = lanes[i * 4 + 2] + time * 0.6;
        positionAttr.setXYZ(i, x, Math.sin(a) * r, Math.cos(a) * r);
      }
      positionAttr.needsUpdate = true;

      const flicker = 0.82 + Math.sin(time * 17) * 0.1 + Math.sin(time * 29.3) * 0.08;
      glowMaterial.opacity = 0.55 * strength * flicker * intensity;
      flameMaterial.opacity = 0.42 * strength * flicker * intensity;
      plumeMaterial.opacity = 0.3 * strength * (0.9 + Math.sin(time * 9) * 0.1);
      plume.scale.set(1, 0.85 + Math.sin(time * 7) * 0.15, 1);
      lights[0].intensity = 2.6 * strength * flicker;
      lights[1].intensity = 1.6 * strength;
      material.opacity = 0.55 + 0.35 * strength;
    },
  };
}

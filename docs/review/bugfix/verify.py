import asyncio, json, math, time
from playwright.async_api import async_playwright

URL = 'http://127.0.0.1:5181/'
OUT = 'review/bugfix'
results = []

def dist(a, b):
    return math.dist(a, b)

async def cam(page):
    return await page.evaluate("""() => ({
        p: window.__app.camera.position.toArray(),
        t: window.__app.controls.target.toArray(),
    })""")

async def wait_idle(page, timeout=8.0):
    last = None
    stable = 0
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        c = await cam(page)
        await page.wait_for_timeout(120)
        if last and dist(c['p'], last['p']) < 1e-4 and dist(c['t'], last['t']) < 1e-4:
            stable += 1
        else:
            stable = 0
        last = c
        if stable >= 3:
            return c
    return last

async def ready(page):
    await page.goto(URL, wait_until='load')
    await page.wait_for_function(
        "window.__app && window.__app.engine && performance.getEntriesByName('engine-ready').length > 0",
        timeout=90000)
    await page.wait_for_timeout(500)

async def drag(page, x0, y0, x1, y1, steps=14):
    await page.mouse.move(x0, y0)
    await page.mouse.down()
    await page.mouse.move(x1, y1, steps=steps)
    await page.mouse.up()

async def project(page, pid, dro=0.0, dang=0.0):
    return await page.evaluate("""([pid, dro, dang]) => {
        const app = window.__app;
        const c = app.engine.getPart(pid).center;
        let y = c[1], z = c[2];
        const r = Math.hypot(y, z) || 1;
        const k = (r + dro) / r;
        y *= k; z *= k;
        const ca = Math.cos(dang), sa = Math.sin(dang);
        const yy = y * ca - z * sa, zz = y * sa + z * ca;
        const v = app.camera.position.clone().set(c[0], yy, zz).project(app.camera);
        return { x: (v.x * 0.5 + 0.5) * innerWidth, y: (-v.y * 0.5 + 0.5) * innerHeight };
    }""", [pid, dro, dang])

async def place_camera(page, pos, target):
    await page.evaluate("""([pos, target]) => {
        const app = window.__app;
        app.controls.dispatchEvent({ type: 'start' });
        app.camera.position.set(...pos);
        app.controls.target.set(...target);
        app.controls.update();
    }""", [pos, target])
    await page.wait_for_timeout(250)

async def click_part(page, pid, pos, target, expect, label):
    await place_camera(page, pos, target)
    pt = await project(page, pid)
    await page.mouse.click(pt['x'], pt['y'])
    await page.wait_for_timeout(300)
    title = await page.locator('#info-title').text_content()
    ok = expect in (title or '')
    results.append({'check': f'pick {label}', 'ok': ok, 'title': title, 'expect': expect})
    print('PICK', label, '->', title, 'OK' if ok else 'FAIL')
    return ok

async def isolation(page, pid, label, rotate=True):
    info = await page.evaluate("""(pid) => {
        const app = window.__app, e = app.engine;
        const all = [...e.parts.keys()];
        const visible = all.filter(id => e.parts.get(id).visible);
        const ring = all.filter(id => id.startsWith('turbine.stage-1-blades.'));
        const neighbor = ring.find(id => id !== pid && e.parts.get(id).visible);
        const scale = (id) => {
            const s = e.parts.get(id);
            const arr = s.group.mesh.instanceMatrix.array;
            if (s.index < 0) return 1;
            const o = s.index * 16;
            return Math.abs(arr[o]) + Math.abs(arr[o + 5]) + Math.abs(arr[o + 10]);
        };
        return { total: all.length, visible: visible.length, visibleIds: visible.slice(0, 5),
                 selectedVisible: e.parts.get(pid)?.visible, selectedScale: scale(pid),
                 neighbor: neighbor, neighborScale: neighbor ? scale(neighbor) : null,
                 ringVisible: ring.filter(id => e.parts.get(id).visible).length };
    }""", pid)
    title = await page.locator('#info-title').text_content()
    ok = info['visible'] == 1 and info['selectedVisible'] and info['selectedScale'] > 0.01
    if info['neighbor'] is not None:
        ok = ok and info['neighborScale'] is not None and info['neighborScale'] < 1e-6
    results.append({'check': f'isolate only one part [{label}]', 'ok': ok, 'title': title, **info})
    print('ISOLATE', label, info, 'OK' if ok else 'FAIL')
    return ok

async def rotate_around(page):
    for _ in range(3):
        await drag(page, 720, 450, 1180, 450)
        await page.wait_for_timeout(250)
    await page.wait_for_timeout(600)

async def restore(page, pid, label):
    await page.click('#clear')
    await wait_idle(page, timeout=6)
    info = await page.evaluate("""(pid) => {
        const e = window.__app.engine;
        const all = [...e.parts.keys()];
        const visible = all.filter(id => e.parts.get(id).visible);
        const ring = all.filter(id => id.startsWith('turbine.stage-1-blades.'));
        const zero = all.filter(id => {
            const s = e.parts.get(id);
            if (s.index < 0) return false;
            const arr = s.group.mesh.instanceMatrix.array;
            const o = s.index * 16;
            return Math.abs(arr[o]) + Math.abs(arr[o + 5]) + Math.abs(arr[o + 10]) < 1e-6;
        });
        return { total: all.length, visible: visible.length, ringVisible: ring.filter(id => e.parts.get(id).visible).length,
                 zeroMatrices: zero.length, zeroFirst: zero.slice(0, 5),
                 partVisible: e.parts.get(pid)?.visible };
    }""", pid)
    ok = info['visible'] == info['total'] and info['ringVisible'] == 100 and info['zeroMatrices'] == 0
    results.append({'check': f'restore all parts [{label}]', 'ok': ok, **info})
    print('RESTORE', label, info, 'OK' if ok else 'FAIL')
    return ok

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True,
            args=['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: print('PAGEERROR', e))
        page.on('console', lambda m: print('CONSOLE', m.type, m.text[:160]) if m.type in ('error',) else None)

        # ---- Problem 1, scenario A: settle, drag, release, wait, must not snap back.
        await ready(page)
        start = await cam(page)
        await page.click('#part-list button[data-part="turbine"]')
        settled = await wait_idle(page)
        moved = dist(settled['p'], start['p'])
        results.append({'check': 'module focus still animates and settles', 'ok': moved > 0.2 and settled is not None,
                        'start': start['p'], 'settled': settled['p'], 'moved': moved})
        print('FOCUS turbine settled', settled, 'moved', moved)
        pre = await cam(page)
        await drag(page, 720, 450, 1000, 450)
        await page.wait_for_timeout(100)
        at_release = await cam(page)
        # OrbitControls damping keeps the user's rotation going for a moment;
        # wait it out, then make sure nothing pulls the camera back to the old goal.
        await page.wait_for_timeout(4500)
        after = await cam(page)
        await page.wait_for_timeout(1000)
        settled_after = await cam(page)
        drag_delta = dist(after['p'], pre['p'])
        damping_drift = dist(settled_after['p'], after['p'])
        ok = drag_delta > 0.3 and damping_drift < 0.02
        results.append({'check': 'drag keeps its view after release (no snap back)', 'ok': ok,
                        'before': pre['p'], 'release': at_release['p'], 'after4.5s': after['p'],
                        'after5.5s': settled_after['p'],
                        'moved_from_before': drag_delta, 'drift_4.5_to_5.5s': damping_drift})
        print('DRAG-A before', pre['p'], 'release', at_release['p'], 'after4.5s', after['p'],
              'moved', drag_delta, 'settled drift', damping_drift, 'OK' if ok else 'FAIL')
        await page.screenshot(path=f'{OUT}/problem1-drag-result.png')

        # ---- Problem 1, scenario B: press while the auto move is running, it must stop.
        await ready(page)
        await page.click('#part-list button[data-part="compressor"]')
        await page.wait_for_timeout(120)
        during = await cam(page)
        await page.mouse.move(720, 450)
        await page.mouse.down()
        await page.wait_for_timeout(100)
        held1 = await cam(page)
        await page.wait_for_timeout(600)
        held2 = await cam(page)
        await page.mouse.move(760, 450, steps=4)
        await page.mouse.up()
        frozen = dist(held2['p'], held1['p'])
        ok = frozen < 0.002
        results.append({'check': 'pointer down during auto move cancels it', 'ok': ok,
                        'during': during['p'], 'held_start': held1['p'], 'held_600ms': held2['p'],
                        'movement_while_held': frozen})
        print('CANCEL held movement', frozen, 'OK' if ok else 'FAIL')
        await page.screenshot(path=f'{OUT}/problem1-cancel-on-start.png')

        # ---- Problem 2: first-stage turbine blade (a ring blade, shared InstancedMesh).
        await ready(page)
        ok = await click_part(page, 'turbine.stage-1-blades.076', [-1.18, 0.0, -0.304],
                              [-1.355, 0.0, -0.304], '第一级涡轮叶片', 'turbine blade')
        if ok:
            await page.click('#isolate')
            await wait_idle(page, timeout=5)
            await isolation(page, 'turbine.stage-1-blades.076', 'turbine blade')
            await page.screenshot(path=f'{OUT}/blade-076-isolated.png')
            await rotate_around(page)
            await page.screenshot(path=f'{OUT}/blade-076-rotated.png')
            await restore(page, 'turbine.stage-1-blades.076', 'turbine blade')
            await page.screenshot(path=f'{OUT}/blade-076-back-to-engine.png')

        # ---- Problem 2: one bolt (core casing bolt ring, shared InstancedMesh).
        bolt_center = await page.evaluate("() => window.__app.engine.getPart('core-casing.bolts.001').center")
        r = math.hypot(bolt_center[1], bolt_center[2]) or 1
        cam_pos = [bolt_center[0], bolt_center[1] / r * 0.34, bolt_center[2] / r * 0.34]
        ok = await click_part(page, 'core-casing.bolts.001', cam_pos, bolt_center, '核心机机匣螺栓', 'bolt')
        if ok:
            await page.click('#isolate')
            await wait_idle(page, timeout=5)
            await isolation(page, 'core-casing.bolts.001', 'bolt')
            await page.screenshot(path=f'{OUT}/bolt-001-isolated.png')
            await rotate_around(page)
            await page.screenshot(path=f'{OUT}/bolt-001-rotated.png')
            await restore(page, 'core-casing.bolts.001', 'bolt')
            await page.screenshot(path=f'{OUT}/bolt-001-back-to-engine.png')

        # ---- Problem 2: one compressor blade (shared InstancedMesh).
        comp_center = await page.evaluate("() => window.__app.engine.getPart('compressor.stage-2.001').center")
        rc = math.hypot(comp_center[1], comp_center[2]) or 1
        cam_pos = [comp_center[0], comp_center[1] / rc * 0.95, comp_center[2] / rc * 0.95]
        ok = await click_part(page, 'compressor.stage-2.001', cam_pos, comp_center, '压气机第 2 级叶环', 'compressor blade')
        if ok:
            await page.click('#isolate')
            await wait_idle(page, timeout=5)
            await isolation(page, 'compressor.stage-2.001', 'compressor blade')
            await page.screenshot(path=f'{OUT}/compressor-blade-001-isolated.png')
            await rotate_around(page)
            await page.screenshot(path=f'{OUT}/compressor-blade-001-rotated.png')
            await restore(page, 'compressor.stage-2.001', 'compressor blade')
            await page.screenshot(path=f'{OUT}/compressor-blade-001-back-to-engine.png')

        # ---- Module-level isolation still works.
        await page.click('#part-list button[data-part="turbine"]')
        await wait_idle(page, timeout=6)
        await page.click('#isolate')
        await wait_idle(page, timeout=5)
        mod = await page.evaluate("""() => {
            const e = window.__app.engine;
            const byModule = {};
            let visible = 0;
            for (const [id, s] of e.parts) {
                if (!s.visible) continue;
                visible++;
                byModule[s.meta.module] = (byModule[s.meta.module] || 0) + 1;
            }
            return { visible, byModule, turbine: e.getPart('turbine.stage-1-blades.076').module };
        }""")
        ok = mod['visible'] == 889 and list(mod['byModule'].keys()) == ['turbine']
        results.append({'check': 'module isolate still shows the whole turbine only', 'ok': ok, **mod})
        print('MODULE ISOLATE', mod, 'OK' if ok else 'FAIL')
        await page.screenshot(path=f'{OUT}/module-isolate.png')
        await page.click('#isolate')
        await wait_idle(page, timeout=4)
        back = await page.evaluate("""() => {
            const e = window.__app.engine;
            return { visible: [...e.parts.values()].filter(s => s.visible).length, total: e.parts.size };
        }""")
        ok = back['visible'] == back['total']
        results.append({'check': 'module isolate shows everything again', 'ok': ok, **back})
        print('MODULE SHOW ALL', back, 'OK' if ok else 'FAIL')

        # ---- Three views on a fresh page.
        await ready(page)
        await page.click('#views button[data-view="assembly"]')
        await wait_idle(page, timeout=6)
        await page.screenshot(path=f'{OUT}/view-assembly.png')
        await page.click('#views button[data-view="cutaway"]')
        await wait_idle(page, timeout=6)
        await page.screenshot(path=f'{OUT}/view-cutaway.png')
        await page.click('#views button[data-view="explode"]')
        await page.wait_for_timeout(2600)
        await page.screenshot(path=f'{OUT}/view-explode.png')
        stats = await page.evaluate("() => ({ stats: window.__stats, calls: window.__app.renderer.info.render.calls })")
        print('STATS', stats)

        with open(f'{OUT}/results.json', 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        failed = [r for r in results if not r.get('ok')]
        print('RESULT', 'FAIL' if failed else 'PASS', 'checks', len(results), 'failed', len(failed))
        await browser.close()

asyncio.run(main())

# Cloud IMU Alarm Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a globally persisted server-side JY901S threshold editor to the UM980 card and calculate cloud alarms from absolute ACC X/Y and ANGLE X/Y/Z values.

**Architecture:** Keep the existing Flask/WebSocket service as the single source of truth. Add an atomic JSON settings store and two REST endpoints, evaluate every device snapshot on the server, and expose a typed cloud-alarm payload to React. Add the eighth UM980 grid card as a compact settings dialog so the left dock stays within one viewport. Mirror the relevant implementation in the portable wangye bundle.

**Tech Stack:** Python unittest, Flask request handlers, React 18, TypeScript, Tailwind CSS, Vitest, Testing Library, Vite production build.

---

### Task 1: Lock the backend settings contract with failing tests

**Files:**
- Modify: 4G/tests/test_4g_message_filter.py
- Modify: wangye/4G/tests/test_4g_message_filter.py

- [ ] **Step 1: Isolate global settings in each test fixture.**

Extend each test class setUp to reset alarm_settings and alarm_settings_updated_at_ms after clearing devices. Use a temporary directory for file tests; do not write a production alarm_settings.json during imports.

~~~python
def reset_alarm_settings(module):
    module.alarm_settings = {
        key: None for key in module.ALARM_SETTING_KEYS
    }
    module.alarm_settings_updated_at_ms = 0
~~~

- [ ] **Step 2: Add RED tests for normalization and evaluation.**

Add tests for disabled defaults, finite non-negative values, rejection of negative/string/infinite/bool values, absolute-value OR logic, clearing below threshold, stale-data clearing, and ignoring a device ALARM payload.

~~~python
def test_cloud_alarm_uses_absolute_value_and_or_logic(self):
    self.module.alarm_settings = {
        "acc_x": 0.8, "acc_y": 0.8, "angle_x": None,
        "angle_y": 30.0, "angle_z": None,
    }
    state = self.module.create_device_state("2")
    state["last_seen_ms"] = 1000
    state["imu"]["acc"] = [-0.85, 0.1, 0.0]
    state["imu"]["angle"] = [0.0, -31.0, 0.0]

    alarm = self.module.evaluate_cloud_alarm(state, now_ms=1000)

    self.assertEqual(alarm["source"], "cloud")
    self.assertEqual(alarm["metric"], "acc_x")
    self.assertEqual(len(alarm["conditions"]), 2)
    self.assertEqual(alarm["conditions"][1]["metric"], "angle_y")


def test_cloud_alarm_clears_below_threshold_and_when_data_is_stale(self):
    self.module.alarm_settings = {
        "acc_x": 0.8, "acc_y": None, "angle_x": None,
        "angle_y": None, "angle_z": None,
    }
    state = self.module.create_device_state("2")
    state["last_seen_ms"] = 1000
    state["imu"]["acc"] = [0.9, 0.0, 0.0]

    self.assertIsNotNone(self.module.evaluate_cloud_alarm(state, now_ms=1000))
    state["imu"]["acc"][0] = 0.7
    self.assertIsNone(self.module.evaluate_cloud_alarm(state, now_ms=1000))
    state["imu"]["acc"][0] = 0.9
    self.assertIsNone(
        self.module.evaluate_cloud_alarm(
            state, now_ms=1000 + self.module.DEVICE_OFFLINE_MS
        )
    )


def test_device_alarm_payload_does_not_override_cloud_alarm(self):
    self.module.alarm_settings = {
        "acc_x": 0.8, "acc_y": None, "angle_x": None,
        "angle_y": None, "angle_z": None,
    }
    payload = "ALARM: level=RED score=99"
    self.module.apply_device_message("2", payload, "2," + payload, now_ms=1000)
    self.assertIsNone(self.module.devices["2"]["alarm"])
~~~

Also add tests for normalize_alarm_settings({}) returning five null fields and for valid values such as acc_x 0.8 and angle_y 30.5.

- [ ] **Step 3: Run RED tests.**

Run:

~~~powershell
python -m unittest discover -s 4G/tests -p 'test_4g_message_filter.py'
~~~

Expected: the new tests fail because ALARM_SETTING_KEYS, normalize_alarm_settings, and evaluate_cloud_alarm do not exist yet.

- [ ] **Step 4: Duplicate the same RED behaviors in the portable backend suite.**

Keep the main and wangye backend contracts identical.

### Task 2: Implement atomic settings storage and cloud evaluation

**Files:**
- Modify: 4G/4G.py
- Modify: wangye/4G/4G.py

- [ ] **Step 1: Add settings constants and startup state.**

Add Path, the five keys, disabled defaults, an STM32_ALARM_SETTINGS_PATH override, an RLock, alarm_settings, and alarm_settings_updated_at_ms.

~~~python
ALARM_SETTING_KEYS = ("acc_x", "acc_y", "angle_x", "angle_y", "angle_z")
DEFAULT_ALARM_SETTINGS = {key: None for key in ALARM_SETTING_KEYS}
ALARM_SETTINGS_PATH = Path(
    os.environ.get(
        "STM32_ALARM_SETTINGS_PATH",
        Path(__file__).with_name("alarm_settings.json"),
    )
)
~~~

Implement normalize_alarm_settings(payload) so missing fields become None, None disables a field, booleans and strings are rejected, and numeric values must be finite and non-negative.

- [ ] **Step 2: Implement load/save helpers.**

Implement load_alarm_settings(path=ALARM_SETTINGS_PATH) and save_alarm_settings(settings, path=ALARM_SETTINGS_PATH). Missing or malformed files load disabled defaults. Saving writes UTF-8 JSON to path.with_suffix(path.suffix + '.tmp') and atomically replaces the final file with os.replace; create the parent directory when needed.

- [ ] **Step 3: Implement evaluate_cloud_alarm(state, now_ms=None).**

Map acc_x/acc_y to imu.acc indexes 0/1 and angle_x/angle_y/angle_z to imu.angle indexes 0/1/2. Skip disabled or non-finite values, compare abs(value) >= threshold, collect every matching condition, and return None when there is no match or the last_seen_ms is at least DEVICE_OFFLINE_MS old. Return source, metric, label, value, absolute_value, threshold, conditions, message, and triggered_at_ms.

- [ ] **Step 4: Recompute after IMU updates and ignore device alarm state.**

In apply_device_message, keep raw ALARM messages in messages, merge ACC/ANGLE data, then set state['alarm'] from evaluate_cloud_alarm. Remove the branch that assigns state['alarm'] from parse_alarm_update. Retain parsing only for raw-log compatibility. Remove alarm_last_seen_ms once no longer referenced.

- [ ] **Step 5: Recompute in build_data_snapshot.**

After computing data_age_ms, set each copied device alarm from evaluate_cloud_alarm(state, now_ms). This clears an alarm when no fresh packet arrives.

- [ ] **Step 6: Run both backend suites and compile checks.**

~~~powershell
python -m unittest discover -s 4G/tests -p 'test_4g_message_filter.py'
python -m unittest discover -s wangye/4G/tests -p 'test_4g_message_filter.py'
python -m py_compile 4G/4G.py
python -m py_compile wangye/4G/4G.py
~~~

Expected: all tests pass and both services compile.

### Task 3: Add settings REST endpoints and immediate WebSocket refresh

**Files:**
- Modify: 4G/4G.py
- Modify: 4G/tests/test_4g_message_filter.py
- Modify: wangye/4G/4G.py
- Modify: wangye/4G/tests/test_4g_message_filter.py

- [ ] **Step 1: Add RED endpoint tests.**

Test GET returns disabled defaults, PUT persists values and recalculates existing devices, and invalid values return HTTP 400 without partially changing settings.

~~~python
def test_put_alarm_settings_persists_and_recalculates_all_devices(self):
    self.module.apply_device_message("2", "ACC: -0.9 0 0 g", now_ms=1000)
    self.module.request = types.SimpleNamespace(
        get_json=lambda silent=True: {"acc_x": 0.8, "angle_y": 30},
    )

    body, status = self._response_parts(self.module.update_alarm_settings())

    self.assertEqual(status, 200)
    self.assertEqual(body["settings"]["acc_x"], 0.8)
    self.assertEqual(self.module.devices["2"]["alarm"]["metric"], "acc_x")
~~~

- [ ] **Step 2: Run the endpoint RED tests.**

~~~powershell
python -m unittest discover -s 4G/tests -p 'test_4g_message_filter.py'
~~~

Expected: endpoint tests fail because get_alarm_settings and update_alarm_settings do not exist.

- [ ] **Step 3: Add GET and PUT routes.**

GET /alarm-settings returns settings and updated_at_ms. PUT /alarm-settings reads request.get_json(silent=True) or {}, normalizes and saves atomically, updates the global timestamp, recalculates every current device under clients_lock, calls push_to_mini_program, and returns the latest payload. ValueError returns HTTP 400; invalid input must not mutate the previous configuration.

- [ ] **Step 4: Run both backend suites again.**

Expected: settings persistence, immediate recalculation, WebSocket broadcast invocation, and validation tests pass.

### Task 4: Add typed frontend settings and cloud-alarm normalization

**Files:**
- Create: SD/pages/stm32/alarmSettings.ts
- Create: SD/pages/stm32/alarmSettings.test.ts
- Modify: SD/pages/stm32/types.ts
- Modify: SD/pages/stm32/telemetry.ts
- Modify: SD/pages/stm32/telemetry.test.ts
- Mirror: wangye/stm32/alarmSettings.ts, wangye/stm32/types.ts, wangye/stm32/telemetry.ts

- [ ] **Step 1: Write RED tests for pure helpers.**

Test normalizeAlarmSettings, countEnabledAlarmSettings, and normalizeAlarm using a cloud payload.

~~~typescript
it('normalizes the five server fields and counts enabled values', () => {
  const settings = normalizeAlarmSettings({ acc_x: 0.8, angle_z: 30 });
  expect(settings).toEqual({
    acc_x: 0.8, acc_y: null, angle_x: null, angle_y: null, angle_z: 30,
  });
  expect(countEnabledAlarmSettings(settings)).toBe(2);
});

it('preserves cloud alarm trigger details', () => {
  const alarm = normalizeAlarm({
    level: 'RED',
    source: 'cloud',
    metric: 'acc_x',
    label: '加速度 X',
    value: -0.85,
    absolute_value: 0.85,
    threshold: 0.8,
    message: '加速度 X 达到 0.850 g，阈值 0.800 g',
    triggered_at_ms: 1000,
    conditions: [{
      metric: 'acc_x',
      label: '加速度 X',
      value: -0.85,
      absolute_value: 0.85,
      threshold: 0.8,
    }],
  });
  expect(alarm?.source).toBe('cloud');
  expect(alarm?.conditions).toHaveLength(1);
});
~~~

- [ ] **Step 2: Run RED tests.**

~~~powershell
cd SD
npm.cmd test -- --run pages/stm32/alarmSettings.test.ts pages/stm32/telemetry.test.ts
~~~

Expected: the new imports/functions are missing.

- [ ] **Step 3: Implement typed settings and normalization.**

Add AlarmSettings, AlarmMetric, AlarmCondition, and cloud fields to AlarmData. Add pure settings helpers. Make normalizeAlarm preserve cloud fields and make normalizeDevice use source.alarm only; it must not derive a new alarm from raw device ALARM text.

- [ ] **Step 4: Run focused tests and TypeScript checks.**

~~~powershell
npm.cmd test -- --run pages/stm32/alarmSettings.test.ts pages/stm32/telemetry.test.ts
npm.cmd run lint
~~~

Expected: both focused suites pass with no TypeScript errors.

### Task 5: Build and test the eighth UM980 card

**Files:**
- Create: SD/pages/stm32/AlarmSettingsCard.tsx
- Create: SD/pages/stm32/AlarmSettingsCard.test.tsx
- Modify: SD/pages/stm32/Um980Panel.tsx
- Modify: SD/pages/stm32/LeftTelemetryDock.tsx
- Modify: SD/lib/integrationRoutes.test.ts
- Mirror: wangye/stm32/AlarmSettingsCard.tsx, wangye/stm32/Um980Panel.tsx, wangye/stm32/LeftTelemetryDock.tsx

- [ ] **Step 1: Write RED Testing Library tests.**

Use // @vitest-environment jsdom. Test empty settings display 未启用, opening a button named 预警设置 opens a dialog named 云端预警设置, the five labeled inputs exist, empty input maps to null, numeric input maps to a number, and an active cloud alarm changes the card status.

~~~typescript
it('opens five-field settings without expanding the dock', async () => {
  const onSave = vi.fn().mockResolvedValue(true);
  render(
    <AlarmSettingsCard
      settings={EMPTY_ALARM_SETTINGS}
      alarm={null}
      saving={false}
      onSave={onSave}
    />,
  );

  await userEvent.click(screen.getByRole('button', { name: /预警设置/ }));
  expect(
    screen.getByRole('dialog', { name: /云端预警设置/ }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText('加速度 X')).toBeInTheDocument();
  expect(screen.getByLabelText('姿态角 Z')).toBeInTheDocument();
});
~~~

- [ ] **Step 2: Run the component RED test.**

~~~powershell
cd SD
npm.cmd test -- --run pages/stm32/AlarmSettingsCard.test.tsx
~~~

Expected: failure because AlarmSettingsCard does not yet exist.

- [ ] **Step 3: Implement the compact card and dialog.**

Keep form values as strings while editing so empty means null. Validate finite non-negative values before invoking onSave. Use a fixed high-z-index overlay and compact spacing; do not add overflow-y-auto or increase the left dock height.

- [ ] **Step 4: Add item eight to the existing four-column grid.**

Keep the seven metric cards unchanged and render AlarmSettingsCard as the eighth child. Pass alarmSettings, alarmSettingsSaving, onSaveAlarmSettings, and the selected device alarm through LeftTelemetryDock and Um980Panel. Add a source contract that the dock still contains h-screen, overflow-hidden, and no overflow-y-auto.

- [ ] **Step 5: Run UI and layout tests.**

~~~powershell
npm.cmd test -- --run pages/stm32/AlarmSettingsCard.test.tsx lib/integrationRoutes.test.ts
~~~

Expected: new UI tests and existing left-dock contracts pass.

### Task 6: Connect page-level GET/PUT state and cloud notifications

**Files:**
- Modify: SD/pages/Stm32Window.tsx
- Modify: SD/lib/integrationRoutes.test.ts
- Mirror: wangye/Stm32Window.tsx
- Mirror: wangye/stm32/NotificationPanel.tsx only if its display helper changes

- [ ] **Step 1: Add RED page contract tests.**

Assert that the page fetches dataSource + '/alarm-settings', sends PUT with Content-Type application/json, handles save failure with an error notification, passes alarmSettings and onSaveAlarmSettings to LeftTelemetryDock, and does not use localStorage for this feature.

- [ ] **Step 2: Run the page RED test.**

~~~powershell
cd SD
npm.cmd test -- --run lib/integrationRoutes.test.ts
~~~

Expected: the new assertions fail because the page has no settings state or endpoints.

- [ ] **Step 3: Implement settings loading and saving.**

Initialize from EMPTY_ALARM_SETTINGS, load once when dataSource is known, keep a saving flag, and normalize the server response. The PUT callback should send JSON and update local state only after a successful response. On failure, leave the last known settings unchanged and call addNotification.

~~~typescript
const response = await fetch(dataSource + '/alarm-settings', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(nextSettings),
});
if (!response.ok) throw new Error('save alarm settings failed');
const result = await response.json();
setAlarmSettings(normalizeAlarmSettings(result.settings));
~~~

- [ ] **Step 4: Update notification de-duplication for cloud fields.**

Use source, metric, absolute_value, threshold, and all condition metrics in the signature. Prefer alarm.message. Clear the signature when alarm becomes null so a later crossing notifies again. Do not add the removed top-left persistent overlay.

- [ ] **Step 5: Run focused page tests and lint.**

~~~powershell
npm.cmd test -- --run lib/integrationRoutes.test.ts pages/stm32/telemetry.test.ts pages/stm32/AlarmSettingsCard.test.tsx
npm.cmd run lint
~~~

Expected: all targeted tests pass and TypeScript remains clean.

### Task 7: Mirror the portable bundle and document deployment

**Files:**
- Modify: wangye/README.md
- Modify: wangye/4G/4G.py
- Modify: wangye/4G/tests/test_4g_message_filter.py
- Modify: wangye/Stm32Window.tsx
- Modify: wangye/stm32/Um980Panel.tsx
- Modify: wangye/stm32/LeftTelemetryDock.tsx
- Create: wangye/stm32/alarmSettings.ts
- Create: wangye/stm32/AlarmSettingsCard.tsx

- [ ] **Step 1: Apply the tested main-site behavior to wangye.**

Keep its relative imports and standalone entry intact. Use the same five keys, endpoint paths, cloud fields, dialog labels, and four-column layout.

- [ ] **Step 2: Document deployment and persistence.**

Update the README with alarm_settings.json, STM32_ALARM_SETTINGS_PATH, GET/PUT /alarm-settings, units, empty-field disable behavior, writable server storage, and the fact that dist alone cannot change cloud alarm logic; the backend must also be replaced and restarted.

- [ ] **Step 3: Run the portable checks.**

~~~powershell
python -m unittest discover -s wangye/4G/tests -p 'test_4g_message_filter.py'
python -m py_compile wangye/4G/4G.py
~~~

Expected: portable behavior matches the main service.

### Task 8: Verify, build, and package

**Files:**
- Generated: SD/dist/

- [ ] **Step 1: Run backend checks.**

~~~powershell
python -m unittest discover -s 4G/tests -p 'test_4g_message_filter.py'
python -m unittest discover -s wangye/4G/tests -p 'test_4g_message_filter.py'
python -m py_compile 4G/4G.py
python -m py_compile wangye/4G/4G.py
~~~

- [ ] **Step 2: Run frontend checks.**

~~~powershell
cd SD
npm.cmd test -- --run pages/stm32/alarmSettings.test.ts pages/stm32/telemetry.test.ts pages/stm32/AlarmSettingsCard.test.tsx lib/integrationRoutes.test.ts
npm.cmd run lint
~~~

- [ ] **Step 3: Build the uploadable distribution.**

~~~powershell
npm.cmd run build
~~~

Expected: Vite and static-page generation complete successfully and SD/dist contains the new STM32 bundle.

- [ ] **Step 4: Perform release checks.**

Run git diff --check, confirm the generated Stm32Window-*.js is newer than the source changes, verify git status --short, and scan staged configuration/examples for real credentials.

- [ ] **Step 5: Commit the implementation as one feature change.**

~~~powershell
git add 4G SD wangye
git add -f docs/superpowers/specs/2026-10-15-cloud-imu-alarm-settings-design.md docs/superpowers/plans/2026-10-15-cloud-imu-alarm-settings.md
git commit -m "feat: add cloud IMU alarm settings"
~~~

Push only after the user requests final GitHub synchronization.

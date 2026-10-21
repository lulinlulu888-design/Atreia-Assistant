const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const native = fs.readFileSync(path.join(__dirname, '../src-tauri/src/app.rs'), 'utf8');

test('launcher close hides without destroying tools or stopping capture', () => {
  const event = native.slice(native.indexOf('if let tauri::WindowEvent::CloseRequested'), native.indexOf('.plugin(tauri_plugin_opener'));
  const launcher = event.slice(event.indexOf('if window.label() == "launcher"'), event.indexOf('let localizing'));
  assert.match(launcher, /api.prevent_close\(\)/);
  assert.match(launcher, /window.hide\(\)/);
  assert.match(launcher, /return;/);
  assert.doesNotMatch(launcher, /destroy\(|stop\(|exit\(/);
});

test('tray is installed before setup completes and can restore a minimized launcher', () => {
  assert.match(native, /setup_launcher_tray\(app.handle\(\)\)\?/);
  assert.match(native, /default_window_icon\(\).cloned\(\)/);
  assert.match(native, /window.unminimize\(\)/);
  assert.match(native, /window.show\(\)/);
  assert.match(native, /window.set_focus\(\)/);
  assert.match(native, /button: MouseButton::Left, button_state: MouseButtonState::Up/);
  assert.match(native, /show_menu_on_left_click\(false\)/);
});

test('explicit tray exit protects localization and updates then stops capture', () => {
  const exit = native.slice(native.indexOf('"atreia-exit" =>'), native.indexOf('.on_tray_icon_event'));
  assert.match(exit, /is_busy\(\) \|\| crate::atreia_update::is_busy\(\)/);
  assert.match(exit, /CaptureControl>\(\).0.lock\(\).stop\(\)/);
  assert.match(exit, /app.exit\(0\)/);
  assert.ok(exit.indexOf('is_busy()') < exit.indexOf('app.exit(0)'));
});

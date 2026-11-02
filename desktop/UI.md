# 桌面界面与窗口

当前说明适用于 2.0.64。浅雾灰表面、内凹输入框、青绿色强调色来自共享 [neumorphic.css](src/neumorphic.css)。主界面及普通工具窗口使用新拟态材质；DPS 与雷达保留游戏浮窗的透明度、皮肤及紧凑布局，不能把所有窗口都描述成相同的实色面板。

## 默认窗口尺寸

以下为逻辑像素的客户区尺寸，不含系统标题栏；DPI/WebView 缩放会影响物理像素。

| 窗口 | 默认尺寸 | 行为 |
| --- | --- | --- |
| 主界面 | 680 × 500 | 打开功能后保留，关闭时隐藏到托盘 |
| 游戏汉化 | 600 × 470 | 独立窗口，最小 460 × 380，长信息在状态区显示 |
| DPS 浮窗 | 初始 400 × 220 | 根据内容、已有设置及缩放调整，无系统外阴影 |
| 隐藏宝箱雷达 | 210 × 240 | 固定紧凑窗口，按 WebView 实际比例调整原生尺寸 |
| 雷达设置 | 330 × 470 | 单独窗口，最小 300 × 400，不放大浮窗 |
| 统计设置 | 760 × 700 | 内容可滚动，操作区保持可用 |
| 历史记录 | 900 × 620 | 可调整尺寸 |
| 明细/单场记录 | 1080 × 680 | 可调整尺寸，保留多显示器相关逻辑 |

尺寸来源为 [tauri.conf.json](src-tauri/tauri.conf.json)、[atreia_localization.rs](src-tauri/src/atreia_localization.rs)、[atreia_radar.rs](src-tauri/src/atreia_radar.rs) 和 [app.rs](src-tauri/src/app.rs)。

雷达与 DPS 使用一致的浮窗材质和透明度设置，不增加外阴影。雷达状态文字在自己的栏位内居中；范围、标记和提示音使用雷达的本地设置。

## 界面检查

从 `desktop/` 执行：

```powershell
npm run build
node --test tests/*.test.cjs tests/*.test.mjs
cargo test --locked --manifest-path src-tauri/Cargo.toml --lib
```

维护者可通过 Vite 开发服务器使用只读界面样例：

```text
/__visual/launcher.html?state=latest
/__visual/launcher.html?state=available
/__visual/launcher.html?state=error
/__visual/index.html?view=settings
/__visual/index.html?view=history
/__visual/index.html?view=details
/__visual/index.html
```

[visual-tests/native-fixture.js](visual-tests/native-fixture.js) 由开发中间件加载，使用标记过的示例数据，不具备真实采集或安装权限，也不进入正式构建。它不能证明驱动、真实统计或游戏汉化已通过实机验收。

2.0.52 的尺寸、测试数量和预览结论保存在[历史界面记录](../documentation/archive/ui-2.0.52.md)。官网截图标注实际拍摄版本，不把旧图或合成数据冒充当前软件实测截图。

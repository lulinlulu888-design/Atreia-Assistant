# 桌面新拟态界面（2.0.52）

浅雾灰表面、柔和双向阴影、内凹输入框、青绿色强调色。主页、汉化对话框、
统计浮窗以及设置/历史/明细窗口共用 `src/neumorphic.css` 的材质和颜色。
统计仍保留用户的计量条主题、窗口不透明度和布局选项，不开启自动抓包。

默认客户区尺寸（逻辑像素，不含系统标题栏）：

| 窗口 | 尺寸 | 行为 |
| --- | --- | --- |
| 主页 | 680 × 500 | 固定布局，无主页滚动条 |
| 汉化面板 | 最大 560 宽 | 默认高度完整显示，长检测信息在状态区域滚动 |
| 统计浮窗 | 初始 400 × 220 | 按统计行数自动调整，仍可拖动和调整尺寸 |
| 设置 | 760 × 700 | 中间选项可滚动，底部返回/退出固定显示 |
| 历史 | 900 × 620 | 可调整尺寸，记录区滚动 |
| 明细/单场记录 | 1080 × 680 | 可调整尺寸，保留多显示器与已保存位置/尺寸逻辑 |

主页使用固定高度网格预留更新和状态区域，而不是仅隐藏滚动条。
长状态信息保留完整的 `title` 提示；所有功能按钮保留键盘焦点轮廓。
缩小可用视口时采用紧凑布局，系统减少动画和强制颜色设置也有对应规则。

## 验证

```powershell
cd desktop
npm run build
node --test tests/*.test.cjs tests/*.test.mjs
cargo test --locked --manifest-path src-tauri/Cargo.toml --lib
npm run tauri build -- --no-bundle --debug
```

51 项前端测试通过；152 项 Rust 测试通过、4 项依赖外部环境的测试忽略。
另通过 14 项翻译安全和 9 项国服纠正安全检查。
浏览器实际测量了 680×500、544×400、453×333 客户区：主页宽高均不超过视口，
“检查更新”和“下载并更新”同时显示时也没有越界。汉化面板在 680×500 下完整显示。
设置面板在 760×700 下底部操作区固定到客户区底部，并检查历史、明细和示例统计。
实际 Windows 预览包已打开，确认主页无滚动条、更新区/页脚完整显示、汉化面板
可打开并返回。未开启真实抓包、安装器或游戏汉化事务。

维护者可用开发服务器的只读界面模拟验证状态：

```text
/__visual/launcher.html?state=latest
/__visual/launcher.html?state=available
/__visual/launcher.html?state=error
/__visual/index.html?view=settings
/__visual/index.html?view=history
/__visual/index.html?view=details
/__visual/index.html
```

`visual-tests/native-fixture.js` 仅由 Vite 开发中间件加载，使用明确标记的示例数据，
没有真实原生权限或安装操作；测试确认它不进入桌面构建资源。
本次不修改官网样式、官网更新清单或已发布的 2.0.51 安装包。

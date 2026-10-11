# 2.0.50 构建材料说明

`Atreia-Assistant_2.0.50_build-materials.zip` 与 Git 标签 `v2.0.50` 配套。
解压 `application-source.zip` 为工作目录；下列命令均在该目录执行。

材料包的 `component/` 是本次发布采用的引擎、已生成补译资源的桥接程序及解压库；
`engine-source/` 是旧仓库 v2.4.0 的构建源码及嵌入资源，不包含用户设置或账号信息。
`localization-inputs/` 提供本次语言生成的输入快照和结果；这些游戏资源沿用单独授权，
不因和 GPL 源码放在同一压缩包中而改为 GPL。`cargo-crates/` 是 Cargo.lock 对应的
Windows 依赖原始源码包；`frontend-packages/` 包含三个前端运行时包的完整已安装内容。
应用自身的 Rust、JavaScript、HTML、数据和构建脚本均在 `application-source.zip` 中。

需要 Windows x64、Node.js/npm、Rust MSVC 工具链、Visual Studio C++ 构建工具及
.NET Framework 编译器。发布环境使用 Rust 1.93 与 Node.js 24 系列。

## 重建桌面安装包

将材料包路径赋给 `$materials`，并使用新的输出目录：

```powershell
$materials = 'C:/path/to/unpacked-build-materials'
./prepare-localization.ps1 `
  -Engine "$materials/component/Aion2-Steam-CN-v2.4.0.exe" `
  -DecoderPath "$materials/component/dependencies/oo2core_9_win64.dll" `
  -AdditionsPath "$materials/localization-inputs/corrections.json.gz" `
  -Destination ./build/rebuilt-component
Copy-Item ./build/rebuilt-component/* ./desktop/src-tauri/vendor/localization/ -Recurse -Force
Copy-Item "$materials/notices/*" ./desktop/src-tauri/vendor/notices/ -Recurse -Force
cd desktop
npm ci --ignore-scripts
npm run tauri build -- --bundles msi --ci
```

也可用 `engine-source/build.ps1` 配合其中的 `payload.dat`、`reference.gz`、`repak.exe`
重建旧引擎；`-TestBuild` 用于隔离事务测试。桥接准备步骤固定校验经审核的原始引擎
SHA-256，重编译引擎的 PE 时间戳可能不同，不能将本地重编译文件冒充原始发行文件。

## 重新生成补译

Python 需要 `opencc-python-reimplemented`（简繁转换）；独立编码审计还需要
`cryptography`、`blake3`、`lz4`。输入快照用于复现，不能用于替代未来版本的客户端原文。

```powershell
$i = "$materials/localization-inputs"
python localization/build_release_additions.py "$i/current-steam.json" `
  "$i/candidate.json" "$i/steam-reviewed-additions.json.gz" `
  "$i/missing-report.json" ./build/reviewed.json.gz
python localization/build_mainland_corrections.py "$i/current-steam.json" `
  "$i/baseline-translation.json" ./build/corrected --additions ./build/reviewed.json.gz
./test-localization-safety.ps1
python -m unittest discover -s tests
```

`baseline-translation.json` 是真实原引擎合并补译后的回读表，不是推测的翻译预览。
实际客户端还应按 `test-localization-roundtrip.ps1` 和
`localization/audit_generated_payload.py` 做隔离事务及独立解码验证。

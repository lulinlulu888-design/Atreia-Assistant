# 2.0.51 构建材料

本版材料包结构及 Windows 构建流程与 [2.0.50 构建说明](BUILD-2.0.50.md) 相同。
使用本版 `application-source.zip`、`component/`、`notices/` 和 `localization-inputs/`
进行构建。汉化引擎及补译资源沿用已经验证的组件；桌面源码更新为 `v2.0.51`。

MSI 自定义位图和平台图标均在桌面源码的 `src-tauri/icons/` 中，Tauri 配置使用
`zh-CN` 安装语言。新图标由官网 `assets/brand/atreia-mark.png` 生成，图像生成说明
见品牌素材 README。不要向已发布的版本标签或已上传安装包覆盖写入新文件。

发布完成后，维护 `docs/updates/latest.json`：记录同仓库正式 MSI 的版本、确切资源
地址、文件大小和 SHA-256。这些值应与 GitHub 正式 Release 及本地构建产物一致。
不能将未发布资源、其他仓库的下载地址或缺少校验值的链接写入更新记录。

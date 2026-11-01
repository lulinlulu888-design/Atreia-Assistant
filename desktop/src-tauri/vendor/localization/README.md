此目录可选放入本地审查过的汉化组件，不提交 EXE。

在仓库根目录执行 prepare-japanese-localization.ps1，从已完整审核的日文入口
bundle 生成离线组件。构建桌面版时使用 build-desktop.ps1 的 JapaneseBundles、
Python 参数；默认要求 Steam 与 PURPLE 两个 bundle。
生成的 helper.sha256 在编译时嵌入桌面程序，运行前逐字节核对辅助程序。
新组件不依赖原英文汉化 EXE，也不携带运行时解包库。
不能用独立解码或单元测试代替客户端实际显示验收。
不得将原引擎、语言数据自动认定为 GPL；公开打包前独立审查对应许可。

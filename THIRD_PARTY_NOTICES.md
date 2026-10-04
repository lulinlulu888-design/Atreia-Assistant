# 第三方许可与来源

亚特雷亚助手按根目录 LICENSE 中的 GPL v3 发布。当前仅作开发测试，未发布安装包。

## A2Tools DPS Meter 解析核心

- 上游：https://github.com/taengu/A2Tools-DPS-Meter
- 固定源码提交：`70aade3fef1ef8b15fe5ce3d27cfdbfc5f854b98`
- 上游许可：GNU GPL v3，保留上游版权与署名；解析器源码注释记载由 Kotlin StreamProcessor 移植。
- 用途：Rust 后端依赖其协议拆帧、压缩包解析、伤害/治疗解析与身份映射。没有把上游完整软件换名当作原创。
- `backend/resources/dot_skill_ids.json` 来自上述固定提交的 `src/data/dot_skill_ids.json`，未修改，遵循相同许可。它是上游筛选的持续伤害技能列表，不代表当前 Steam/PURPLE 技能数据已全部验证。
- 不启用上游 `desktop` 功能；本项目后端不引入其账号登录、战斗上传、更新或 Discord 功能。
- 构建通过 Cargo 拉取固定提交，发布二进制之前必须同时提供本项目及对应依赖的可构建源码与许可；仅放安装包不满足发布要求。

Python 传输和统计模块为本项目新增代码。上游核心的测试结果不代表新项目或 Steam/PURPLE 实战已经验证。

Npcap 不打包分发；用户需按其官网许可自行安装。Rust 传递依赖的许可应在二进制发布前完整盘点并包含所需通知。当前没有进行二进制发布。

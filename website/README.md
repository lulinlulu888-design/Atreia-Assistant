# 亚特雷亚助手官网

Nuxt 4 静态生成站点，正式域名 https://a2go.cc/ 。在本机或 CI 构建，EC2 仅使用 Nginx 提供静态文件，不常驻 Node 服务。

使用 Node 24.15 或以上：

```powershell
npm ci
npm run generate
python check_build.py
./deploy/publish.ps1
```

`release.json` 是官网下载版本的唯一构建数据。必须先公开正式 MSI、核对 SHA-256、上传 S3 并重新下载验证，再更新版本、大小、摘要和 URL。不能提前把按钮指向未发布的版本。

## 共用服务器

- `a2go.cc` 和 `www.a2go.cc` 指向 13.229.44.28；www HTTPS 重定向至根域名。
- 本站独立配置 `/etc/nginx/conf.d/atreia.conf`，站点目录 `/srv/atreia/www/current`。
- 每次部署生成独立 releases 目录，原子切换 current 符号链接，保留旧版本以便回滚。
- `hczs.online` 的配置、证书与目录不被本站部署脚本修改。
- 本站独立证书 `/etc/letsencrypt/live/a2go.cc/`；Certbot 定时续期，现有 deploy hook 重载 Nginx。
- 当前 IP 非弹性 IP；实例停机再启动后务必复核 DNS。未自动分配额外收费资源。

## S3 下载

独立桶 `atreia-downloads-487694861369`（新加坡），仅公开 HTTPS GetObject：

```text
releases/vVERSION/Atreia-Assistant_VERSION_x64.msi
releases/vVERSION/SHA256SUMS.txt
```

不授予公共列举或写入权限。ACL 禁用，公共 ACL 阻止开关保留；只有匹配 `deploy/s3-download-policy.json` 的正式文件路径可公开读取。不要将凭证、私钥、源数据或用户日志放入下载桶。GitHub 仍提供对应版本的源码、构建材料及备用安装包。

静态图片来自项目既有品牌与真实软件截图，标注实际截图版本，不使用模拟战斗或宝箱数据。

## 下载统计

首页的统计来自 `/stats/downloads.json`，仅累计 GitHub 非草稿、非预发布版本的正式 MSI，不包含 S3、源码、构建材料或校验文件。服务器通过 `deploy/update_download_count.py` 和同目录 systemd service/timer 每 15 分钟拉取公开 API，不需要访问令牌、不收集访客信息。完整分页成功后原子替换 `/srv/atreia/data/downloads.json`；失败时保留上次成功缓存，超过一小时的结果标注缓存，前端请求失败不显示虚假的零。

测试：`python -m unittest discover -s tests -v`。统计数据目录不在静态站点发布目录内，不随官网版本切换而丢失。现有 S3 直链未接入下载计数，不能把 GitHub 数字标成全渠道总量。

## 自动发布流程

`.github/workflows/release.yml` 在 Windows 正式发布成功后运行 S3 同步，校验 MSI，再使用 GitHub OIDC 获取 15 分钟临时凭证。角色 `AtreiaGitHubReleasePublisher` 不使用长期访问密钥；其信任和权限策略保存在 `deploy/github-*.json`，只信任本仓库 `v2.*` 标签，只能读取、写入指定桶的正式 MSI 与校验文件，不能删除、列举或修改其他桶。

流水线仅接受 `v2.NUMBER.NUMBER` 正式版本，拒绝草稿和预发布；上传后重新下载并逐字节比较。现有 v2.0.62 已手工上传并验证；新增自动同步步骤从下一个包含此工作流的版本标签生效，尚未进行真实 OIDC 流水线运行验收。官网仍需更新 `release.json`、构建验证并使用上述部署脚本发布。

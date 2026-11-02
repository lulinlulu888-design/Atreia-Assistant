# 亚特雷亚助手官网运维

正式官网：[a2go.cc](https://a2go.cc/)。使用 Nuxt 4 静态生成，在本机或 CI 构建，EC2 的 Nginx 提供静态文件，不常驻 Node 服务。软件完整发布顺序见[发布与官网同步](../documentation/RELEASING.md)。

## 构建和部署

以下命令在 `website/` 执行，要求 Node.js 24.15.0 或以上：

```powershell
npm ci
npm run generate
python -X utf8 check_build.py
./deploy/publish.ps1
```

检查和构建不会部署；最后一条通过已有 SSH 别名 `atreia-aws` 上传并切换正式站点。也可使用 `-SshHost` 指定已配置的连接。

`release.json` 是首页下载版本的构建数据。先公开正式 MSI、验证 GitHub 与 S3 回下载的大小和 SHA-256，再更新版本、地址、摘要和文案。部署脚本将同一文件复制为 `download-release.json`，供下载 API 随站点版本一起读取。

静态图片沿用项目品牌和真实软件截图，并标注拍摄版本。截图没有随版本更新时保留原版本标注，不制作虚假的统计或宝箱结果。

## 两个域名共用服务器

| 项目 | 本站配置 |
| --- | --- |
| 域名 | a2go.cc、www.a2go.cc；www HTTPS 跳转至根域名 |
| 当前 IPv4 | 13.229.44.28（配置记录；实例重启后需复核） |
| Nginx | /etc/nginx/conf.d/atreia.conf |
| 当前站点 | /srv/atreia/www/current |
| 发布目录 | /srv/atreia/www/releases/时间戳 |
| HTTPS 证书 | /etc/letsencrypt/live/a2go.cc/ |

部署创建独立目录后原子切换 `current`，旧目录保留用于回滚。hczs.online 使用自己的配置、证书和目录，本站脚本不修改它。Certbot 定时续期并通过现有 hook 重载 Nginx。当前 IP 非弹性 IP，实例停机再启动后需复核 DNS。

回滚时选择已经核验的旧发布目录，原子恢复 `current` 链接，并核对首页及 `download-release.json`；不通过清空目录或数据库来回滚静态站点。

## S3 正式下载

独立桶 `atreia-downloads-487694861369` 位于新加坡，仅公开正式安装包与校验文件的 HTTPS GetObject：

```text
releases/vVERSION/Atreia-Assistant_VERSION_x64.msi
releases/vVERSION/SHA256SUMS.txt
```

不授予公共列举或写入权限。ACL 禁用，公共 ACL 阻止开关保留；公开范围由 [s3-download-policy.json](deploy/s3-download-policy.json) 限定。凭据、私钥、源数据和用户日志不放入下载桶。对应源码、构建材料和备用安装包保留在 GitHub Release。

[release.yml](../.github/workflows/release.yml) 在 Windows 正式发布成功后，通过 GitHub OIDC 获取 15 分钟凭据并同步 S3。角色 `AtreiaGitHubReleasePublisher` 不使用长期 AWS 密钥，只信任本仓库版本标签，权限限定到该桶的正式 MSI 和校验文件，上传后回读逐字节比较。

信任与权限配置见 [github-oidc-trust.json](deploy/github-oidc-trust.json) 和 [github-s3-publish-policy.json](deploy/github-s3-publish-policy.json)。2.0.64 已完成该链路验证。已有正式版同步失败时，使用 [sync-downloads.yml](../.github/workflows/sync-downloads.yml) 的 `v2.NUMBER.NUMBER-sync-downloads` 标签重试；不覆盖正式版本标签或重建已发布包。

## 官网下载点击统计

首页和底部按钮通过同源 `/api/download` 发起下载，MongoDB 独立库 `atreia_website` 保存点击事件。`/api/downloads` 只读取统计。

- 从 2026-10-28 启用时开始，不导入历史 GitHub 下载，不包含 S3 直链。
- 统计按钮点击，不代表文件下载完成次数或独立用户数。
- 浏览器重试相同请求 ID 只计一次；刷新页面、读统计或 GET 预取不增加计数。
- 数据库不可用时继续提供下载；统计显示暂不可用，不伪造零值。
- 事件只存随机请求 ID、版本和时间，不存 IP 或用户身份。

[download_api.py](server/download_api.py) 仅监听 `127.0.0.1:8765`，由 Nginx 代理。[服务配置](deploy/atreia-download-api.service) 使用服务器内 root 可读的 `/etc/atreia-download-api.env`；连接账号只授权独立库 readWrite，凭据不提交 Git。依赖见 [requirements.txt](server/requirements.txt)。

从仓库根目录检查：

```powershell
python -X utf8 -m unittest discover -s website/tests -v
```

生产验收只读 `/api/downloads`；不点击下载按钮制造测试次数。持久化测试使用独立测试集合，不清空生产计数。

## 备用站点和版本清单

`docs/` 是 GitHub Pages 备用站，由 [pages.yml](../.github/workflows/pages.yml) 部署。a2go.cc 仍需执行上面的 SSH 部署脚本，两个发布入口不会自动互相替代。

`website/public/updates/latest.json` 与 `docs/updates/latest.json` 保存同一 GitHub 正式 MSI 信息。当前桌面更新器实际备用地址指向 GitHub Pages，不能只更新 a2go.cc 而遗漏它。需要同时修改的文件和验收步骤见[发布流程](../documentation/RELEASING.md)。

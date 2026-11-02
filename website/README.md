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

## 官网下载点击统计

首页与底部下载按钮通过同源 `/api/download` 发起下载，MongoDB 独立库 `atreia_website` 保存点击事件。统计从启用时开始，不导入 GitHub 历史，不计入 S3 直链，也不表示下载完成次数；浏览器重试同一请求 ID 只计一次。刷新页面、读取统计与 GET 预取不增加次数。数据库故障不阻止下载，统计显示暂不可用，不伪造零值。

`server/download_api.py` 仅监听 127.0.0.1:8765，由 nginx 代理。安装 `server/requirements.txt`，使用 `deploy/atreia-download-api.service`，连接串放在服务器 root 可读的 `/etc/atreia-download-api.env`，只授权独立库 readWrite，不提交凭据。发布脚本在每次静态部署中复制同版本 `download-release.json`，API 随原子目录切换读取正式安装包地址。事件只存随机请求 ID、版本和时间，不存 IP 或用户标识。

验证：`python -m unittest discover -s website/tests -v`。生产库不写入合成测试点击；持久化测试使用独立测试集合并在验证后清理。

### 正式文件路径

独立桶 `atreia-downloads-487694861369`（新加坡），仅公开 HTTPS GetObject：

```text
releases/vVERSION/Atreia-Assistant_VERSION_x64.msi
releases/vVERSION/SHA256SUMS.txt
```

不授予公共列举或写入权限。ACL 禁用，公共 ACL 阻止开关保留；只有匹配 `deploy/s3-download-policy.json` 的正式文件路径可公开读取。不要将凭证、私钥、源数据或用户日志放入下载桶。GitHub 仍提供对应版本的源码、构建材料及备用安装包。

静态图片来自项目既有品牌与真实软件截图，标注实际截图版本，不使用模拟战斗或宝箱数据。

## 自动发布

`.github/workflows/release.yml` 在 Windows 正式发布成功后运行 S3 同步，校验 MSI，再使用 GitHub OIDC 获取 15 分钟临时凭证。角色 `AtreiaGitHubReleasePublisher` 不使用长期访问密钥；其信任和权限策略保存在 `deploy/github-*.json`，只信任本仓库 `v2.*` 标签，只能读取、写入指定桶的正式 MSI 与校验文件，不能删除、列举或修改其他桶。

流水线仅接受 `v2.NUMBER.NUMBER` 正式版本，拒绝草稿和预发布；上传后重新下载并逐字节比较。2.0.63 已通过真实 OIDC 发布角色上传和回读核对。`sync-downloads.yml` 可用独立的 `v2.NUMBER.NUMBER-sync-downloads` 标签重试现有正式版的同步，不重新构建或修改正式版本标签；校验文件同时兼容 Windows CRLF 和 Unix LF。官网仍需更新 `release.json`、构建验证并使用上述部署脚本发布。

# 阿里云静态网站部署

发布当前 AI Coding 主页及现有题库、讲解、参考解和可视化。Python 判题、读取本机实现仍需在用户自己的电脑上启动本地版。此配置不开放远程代码执行服务。

## 暂无域名时的 SSH 预览

`nginx-preview.conf` 仅监听服务器的 `127.0.0.1:8080`，适合发布前检查。安装流程与下方一致，但使用此配置代替 `nginx.conf`。全新安装 Nginx 时移除软件包自带的 `sites-enabled/default` 链接，避免默认站点监听公网端口；服务器已有配置时先检查，不覆盖其他站点。

在本机终端运行并保持连接：

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8080:127.0.0.1:8080 paperleet-aliyun
```

浏览器打开 `http://127.0.0.1:8080`。站点文件实际位于云服务器，通过 SSH 隧道访问，无需开放公网 8080 端口。

中国内地服务器即使仅通过 IP 对外提供网站，也有备案要求，参见[阿里云通用网站备案说明](https://help.aliyun.com/zh/icp-filing/basic-icp-service/product-overview/icp-filing-requirements-for-a-regular-website)。公网配置与 SSH 预览配置择一启用，避免重复 `server` 配置。

## 部署前信息

- 已注册的域名。配置示例使用 `paperleet-coding.com`，上线前替换为实际域名；域名中的 `-` 是英文短横线。
- 服务器公网 IP、操作系统、地域与已有 SSH 登录方式。
- 使用中国内地服务器需完成相应 ICP 备案；香港或海外节点的要求不同，按服务器实际地域确认。
- 在域名 DNS 中将根域名的 A 记录指向服务器公网 IPv4；如果使用 IPv6，另配 AAAA 和相应网络规则。
- 阿里云安全组和系统防火墙允许网站的 TCP 80、443；SSH 保留现有受限登录配置。

阿里云文档：[网站搭建](https://www.alibabacloud.com/help/en/ecs/user-guide/build-a-website/)、[个人网站备案](https://help.aliyun.com/en/icp-filing/basic-icp-service/getting-started/quick-start-for-icp-filing-for-personal-websites)。

## 本地生成发布包

在已安装项目依赖的仓库根目录执行：

```bash
bash scripts/package-site.sh
```

产物为 `reports/deploy/paperleet-coding-site.tar.gz`，只包含构建后的公开前端文件。打包前重新导出题库，保证索引与模块文件对应。

## 上传和安装

以下以已有 SSH 别名 `paperleet-aliyun` 和 Ubuntu/Debian 为例；先替换 SSH 别名。其他系统使用对应的软件包管理器安装 Nginx。服务器已有网站时，应先检查现有虚拟主机配置，避免冲突。

本地上传：

```bash
scp reports/deploy/paperleet-coding-site.tar.gz paperleet-aliyun:/tmp/paperleet-coding-site.tar.gz
scp deploy/aliyun/nginx.conf paperleet-aliyun:/tmp/paperleet-coding.nginx.conf
ssh paperleet-aliyun
```

服务器执行，发布到新的版本目录：

```bash
sudo apt-get update
sudo apt-get install -y nginx
release_dir="/var/www/paperleet-coding/releases/$(date +%Y%m%d%H%M%S)"
sudo mkdir -p "$release_dir"
sudo tar --no-same-owner -xzf /tmp/paperleet-coding-site.tar.gz -C "$release_dir"
sudo chmod -R a+rX "$release_dir"
sudo ln -s "$release_dir" /var/www/paperleet-coding/current.next
sudo mv -Tf /var/www/paperleet-coding/current.next /var/www/paperleet-coding/current
```

编辑 `/tmp/paperleet-coding.nginx.conf` 的 `server_name` 后安装独立配置。第一次使用此文件名时执行；已有同名配置先备份并比较：

```bash
sudo install -m 644 /tmp/paperleet-coding.nginx.conf /etc/nginx/conf.d/paperleet-coding.conf
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

配置中的 SPA 回退保证 `/collections/llm-basics/` 等地址刷新正常。静态资源缺失返回 404，避免把 HTML 当作 JavaScript 或 JSON。Nginx 配置说明：[try_files](https://nginx.org/en/docs/http/ngx_http_core_module.html#try_files)。

## HTTPS 和验收

DNS 生效且 HTTP 正常后，使用阿里云证书或 ACME 客户端为实际域名签发证书，配置 Nginx 的 443 端口和 HTTP 到 HTTPS 跳转，并配置续期。证书和私钥只存服务器，不提交到 Git。

上线后验证首页、合集深链接刷新、一道题的讲解与实验展示、缺失资源的 404、HTTPS 证书和跳转。网页不会连接公网 Python 判题服务。

更新时再次上传发布包，创建新的版本目录并切换 `current` 链接。回滚时将该链接切回上一版本。

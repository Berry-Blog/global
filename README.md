# Global Home v2.1.0 使用说明

## 安装

```sh
curl -fLO https://raw.githubusercontent.com/Berry-Blog/global/main/global-home-nodes-install-v2.1.0.sh
chmod +x global-home-nodes-install-v2.1.0.sh
sh global-home-nodes-install-v2.1.0.sh
```

## 校验安装包

```sh
sh global-home-nodes-install-v2.1.0.sh --verify
sha256sum -c global-home-nodes-v2.1.0-artifacts.sha256
```

## 从现有 v2.0.1 安全升级到 v2.1.0

v2.0.1 更新器只接受固定的 11 项源码文件清单，v2.1.0 包新增 `gl` 和 `relay_export.py`，共 13 项，因此旧更新器会在写入文件前拒绝此包。请先将本桥接 PR 合并到 `main`，再从服务器 root shell 执行下面命令；不要运行完整安装器，也不需要编辑 Python 文件：

```sh
set -eu
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
base='https://raw.githubusercontent.com/Berry-Blog/global/main'
file='upgrade_bridge_2_0_1_to_2_1_0.py'
curl -fL --proto '=https' --tlsv1.2 "$base/$file" -o "$tmp/$file"
curl -fL --proto '=https' --tlsv1.2 "$base/$file.sha256" -o "$tmp/$file.sha256"
(cd "$tmp" && sha256sum -c "$file.sha256")
python3 "$tmp/$file" --check-only
python3 "$tmp/$file"
```

桥接器只接受本地版本恰为 2.0.1，并固定校验 GitHub manifest、2.1.0 ZIP SHA256、13 项文件清单、ZIP CRC、路径与符号链接安全、每个源码文件 SHA256 和版本元数据。它只备份并更新 `/opt/global-home-nodes` 管理程序文件，必要时安全创建 `/usr/local/bin/gl` 链接；不执行 `install.sh`，不读取或修改 `/etc/global-home-nodes`、Xray 或任何服务。管理代码会先在暂存目录做导入检查，替换后再次检查；检查失败时恢复原文件。备份保存在 `/root/global-home-nodes-code-backups/`。

升级完成后可检查管理程序并导出 Dogma 文件：

```sh
global-home-nodes status
gl export-relay
```

在 Global Home Xray 服务运行时，导出文件写入 `/etc/global-home-nodes/exports/dogma-relay.json`。此 JSON 只含 Dogma 导入所需的公共参数与匹配线路，不含 Reality 私钥或 SOCKS 用户名、密码。

## 常用命令

```sh
global-home-nodes status
global-home-nodes refresh
global-home-nodes update
global-home-nodes update --check-only
global-home-nodes refresh --import-json /root/my-authorized-exits.json
global-home-nodes uninstall
```

## 狗妈中转参数

在 Global SSH 中运行 `gl` 打开管理菜单。选择“导出狗妈中转 JSON”后，文件保存在：

```text
/etc/global-home-nodes/exports/dogma-relay.json
```

也可以直接运行：

```sh
gl status
gl refresh
gl update
gl uninstall
gl export-relay
```

导出的 JSON 包含 Global VLESS Reality 公共参数和通过 Xray UUID、email、路由、出站及 SOCKS5 映射校验的家宽线路，可通过 SCP 传到狗妈后从 `sb` 菜单导入。请按包含 UUID 的敏感文件妥善保管。


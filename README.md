# Global Home v2.1.1 使用说明

## 安装

```sh
curl -fLO https://raw.githubusercontent.com/Berry-Blog/global/main/global-home-nodes-install-v2.1.1.sh
chmod +x global-home-nodes-install-v2.1.1.sh
sh global-home-nodes-install-v2.1.1.sh
```

## 校验安装包

```sh
sh global-home-nodes-install-v2.1.1.sh --verify
sha256sum -c global-home-nodes-v2.1.1-artifacts.sha256
```

## 从 v2.1.0 升级到 v2.1.1

v2.1.1 修复了线路管理菜单读取 `upstream-audit.json` 时把 JSON 列表误判成对象的问题。已有 v2.1.0 用户可使用代码更新器升级；不需要重装、刷新线路或编辑配置：

```sh
global-home-nodes update --check-only
global-home-nodes update
```

更新器会校验 GitHub manifest、源码 ZIP SHA256、完整文件清单、ZIP CRC、内部 SHA256 和版本元数据。它只更新管理代码，不读取或改写节点状态，也不重启服务。

## 从 v2.0.1 安全升级到 v2.1.1

v2.0.1 更新器只接受固定的 11 项源码清单，后续版本有 13 项，因此需用独立桥接器，不要运行完整安装器或编辑 Python 文件。以 root shell 下载后校验并执行：

```sh
set -eu
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
base='https://raw.githubusercontent.com/Berry-Blog/global/main'
file='upgrade_bridge_2_0_1_to_2_1_1.py'
curl -fL --proto '=https' --tlsv1.2 "$base/$file" -o "$tmp/$file"
curl -fL --proto '=https' --tlsv1.2 "$base/$file.sha256" -o "$tmp/$file.sha256"
(cd "$tmp" && sha256sum -c "$file.sha256")
python3 "$tmp/$file" --check-only
python3 "$tmp/$file"
```

桥接器只接受本地版本 2.0.1，严格验证 2.1.1 manifest、源码 SHA256、13 项 ZIP 清单、路径与链接安全、CRC、内部文件摘要和版本元数据。它只备份并替换管理程序文件，必要时创建 `gl` 链接；不运行安装器、不修改 `/etc/global-home-nodes`、Xray 或服务。失败时会回滚管理程序文件。备份保存在 `/root/global-home-nodes-code-backups/`。

## 检查线路与导出狗妈 JSON

```sh
global-home-nodes status
gl
# 选择 1 显示线路；选择 3 导出狗妈中转 JSON
gl export-relay
```

导出文件位于 `/etc/global-home-nodes/exports/dogma-relay.json`。文件包含用于导入的线路 UUID，请妥善保管。

# Global Home v2.1.3 使用说明

## 安装

```sh
curl -fLO https://raw.githubusercontent.com/Berry-Blog/global/main/global-home-nodes-install-v2.1.3.sh
chmod +x global-home-nodes-install-v2.1.3.sh
sh global-home-nodes-install-v2.1.3.sh
```

## 校验安装包

```sh
sh global-home-nodes-install-v2.1.3.sh --verify
sha256sum -c global-home-nodes-v2.1.3-artifacts.sha256
```

## 从 v2.1.0、v2.1.1 或 v2.1.2 升级

v2.1.3 修复了数字开头的供应商线路 key 被导出器忽略的问题，并保留 UUID 与 email 一致性检查。管理程序更新只替换程序代码，不更改现有线路数据、UUID、Reality 参数、端口或服务：

```sh
global-home-nodes update --check-only
global-home-nodes update
```

升级完成后运行 `gl`，选择“导出狗妈中转 JSON”重新生成 `dogma-relay.json`。不需要重新部署线路或更新供应商线路。

## 从 v2.0.1 安全升级到 v2.1.3

v2.0.1 更新器只接受固定的 11 项源码清单，后续版本有 13 项；请使用安全桥接器，不要运行完整安装器或手动编辑 Python 文件。以 root shell 执行：

```sh
set -eu
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
base='https://raw.githubusercontent.com/Berry-Blog/global/main'
file='upgrade_bridge_2_0_1_to_2_1_3.py'
curl -fL --proto '=https' --tlsv1.2 "$base/$file" -o "$tmp/$file"
curl -fL --proto '=https' --tlsv1.2 "$base/$file.sha256" -o "$tmp/$file.sha256"
(cd "$tmp" && sha256sum -c "$file.sha256")
python3 "$tmp/$file" --check-only
python3 "$tmp/$file"
```

桥接器校验 2.1.3 发布清单、固定 ZIP SHA256、13 项文件清单、路径安全、CRC、内部文件 SHA256 和版本元数据。它只更新管理程序代码，不更改 `/etc/global-home-nodes` 或服务。

## `gl` 菜单与狗妈 JSON

```sh
gl
```

菜单包括查看家宽线路、显示 Reality 公共参数、导出狗妈 JSON、检查 UUID 与 Xray 路由、检查出站状态、查看运行状态、首次部署、读取供应商 `proxy` 最新线路并更新、从授权 JSON 更新线路、检查或安装管理程序更新，以及卸载。

已部署机器更新线路时，选择“读取供应商 proxy 最新线路并更新”；工具会在操作时读取本机供应商菜单，预检后再次要求确认才应用。这个动作由用户手动触发，不会后台监控。

导出文件只包含通过 UUID、email、路由和线路元数据一致性检查的线路；无法唯一匹配的项会显示为异常。文件位于 `/etc/global-home-nodes/exports/dogma-relay.json`。升级到 v2.1.3 后重新导出即可让数字开头的线路 key 正常显示。

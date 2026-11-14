# Global Home v2.1.2 使用说明

## 安装

```sh
curl -fLO https://raw.githubusercontent.com/Berry-Blog/global/main/global-home-nodes-install-v2.1.2.sh
chmod +x global-home-nodes-install-v2.1.2.sh
sh global-home-nodes-install-v2.1.2.sh
```

## 校验安装包

```sh
sh global-home-nodes-install-v2.1.2.sh --verify
sha256sum -c global-home-nodes-v2.1.2-artifacts.sha256
```

## 从 v2.1.0 或 v2.1.1 升级到 v2.1.2

v2.1.2 加强线路映射校验：UUID 必须属于对应 email 的同一条元数据，并拒绝重复的 Xray email。升级只替换管理程序代码，不改线路或重启服务：

```sh
global-home-nodes update --check-only
global-home-nodes update
```

## 从 v2.0.1 安全升级到 v2.1.2

v2.0.1 更新器只接受固定的 11 项源码清单，后续版本有 13 项；请使用安全桥接器，不要运行完整安装器或手动编辑 Python 文件。以 root shell 执行：

```sh
set -eu
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
base='https://raw.githubusercontent.com/Berry-Blog/global/main'
file='upgrade_bridge_2_0_1_to_2_1_2.py'
curl -fL --proto '=https' --tlsv1.2 "$base/$file" -o "$tmp/$file"
curl -fL --proto '=https' --tlsv1.2 "$base/$file.sha256" -o "$tmp/$file.sha256"
(cd "$tmp" && sha256sum -c "$file.sha256")
python3 "$tmp/$file" --check-only
python3 "$tmp/$file"
```

桥接器固定校验 2.1.2 manifest、源码 SHA256、13 项 ZIP 清单、路径、链接、CRC、内部文件摘要和版本元数据，只替换管理程序文件并保留回滚备份，不更改 `/etc/global-home-nodes` 或服务。

## 检查线路与导出狗妈 JSON

```sh
gl
```

菜单包含线路查看、Reality 公共参数、狗妈 JSON 导出、线路映射检查、单次出站检查、运行状态、首次部署、线路更新、管理程序更新检查/安装和卸载。

选择“读取供应商 proxy 最新线路并更新”会在操作时只读本机供应商 `proxy` 出口菜单，不会切换供应商当前线路。读取前需要确认授权；Global Home 完成线路预检后，还需再次确认才会应用。也可以选择从授权 JSON 文件更新线路。两种方式都由用户手动触发，不会后台监控。首次部署只适用于尚未部署的机器；已部署线路请使用线路更新选项。

导出只包含通过 UUID、email 和线路元数据一致性校验的线路；异常线路不会作为正常线路导出。文件位于 `/etc/global-home-nodes/exports/dogma-relay.json`，请妥善保管。

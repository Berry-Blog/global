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

v2.1.3 修复了数字开头的供应商线路 key 被导出器忽略的问题。管理程序更新仅替换程序代码，不更改现有线路数据、UUID、Reality 参数、端口或服务：

```sh
global-home-nodes update --check-only
global-home-nodes update
```

更新后运行 `gl`，选择“导出狗妈中转 JSON”重新生成 `dogma-relay.json`。修复会重新识别现有元数据；不需要重新部署线路或更新供应商线路。

## 从 v2.0.1 安全升级

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

桥接器固定校验 2.1.3 manifest、源码 SHA256、13 项 ZIP 清单、路径、链接、CRC、内部 SHA256 和版本元数据，只替换管理程序文件并保留回滚备份，不更改 `/etc/global-home-nodes` 或服务。

## 检查线路与导出狗妈 JSON

```sh
gl
```

菜单包含线路查看、Reality 公共参数、狗妈 JSON 导出、线路映射检查、单次出站检查、运行状态、首次部署、线路更新、管理程序更新检查/安装和卸载。已部署机器更新管理程序后，只需重新导出 JSON；不要选择首次部署来修复映射。


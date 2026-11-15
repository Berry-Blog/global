# Global Home v2.1.4 使用说明

## 安装

~~~sh
curl -fLO https://raw.githubusercontent.com/Berry-Blog/global/main/global-home-nodes-install-v2.1.4.sh
chmod +x global-home-nodes-install-v2.1.4.sh
sh global-home-nodes-install-v2.1.4.sh
~~~

## 校验安装包

~~~sh
sh global-home-nodes-install-v2.1.4.sh --verify
sha256sum -c global-home-nodes-v2.1.4-artifacts.sha256
~~~

## v2.1.4 新增：修改公网映射 IP/端口

运行 gl，选择菜单项 13。输入新公网 IP 或域名和公网 TCP 端口；本机内部 TCP 端口、供应商出口、UUID、Reality 参数和现有 Xray 服务保持不变。工具会创建新的受管配置代，更新本机 VLESS/Clash 等节点文件，并自动重新生成狗妈中转 JSON。

请先在服务商面板配置公网 TCP 端口转发，再输入 UPDATE 确认。该操作不会验证外部网络是否能连通；请将重新生成的 dogma-relay.json 同步到狗妈机，并从外部客户端测试新地址。

## 从 v2.1.0、v2.1.1、v2.1.2 或 v2.1.3 升级

管理程序更新只替换程序代码，不更改现有线路数据、UUID、Reality 参数、端口或 Xray 服务：

~~~sh
global-home-nodes update --check-only
global-home-nodes update
~~~

v2.1.3 修复了数字开头的供应商线路 key 被导出器忽略的问题，并保留 UUID 与 email 一致性检查。升级后运行 gl，选择“导出狗妈中转 JSON”重新生成 dogma-relay.json。

## 从 v2.0.1 安全升级

v2.0.1 更新器只接受固定的 11 项源码清单，不能直接升级到当前 2.1.4。使用安全桥接器直接升级到 v2.1.4，不运行完整安装器，也不改动节点数据。以 root shell 执行：

~~~sh
set -eu
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
base='https://raw.githubusercontent.com/Berry-Blog/global/main'
file='upgrade_bridge_2_0_1_to_2_1_4.py'
curl -fL --proto '=https' --tlsv1.2 "$base/$file" -o "$tmp/$file"
curl -fL --proto '=https' --tlsv1.2 "$base/$file.sha256" -o "$tmp/$file.sha256"
(cd "$tmp" && sha256sum -c "$file.sha256")
python3 "$tmp/$file" --check-only
python3 "$tmp/$file"
~~~

桥接器校验 v2.1.4 发布清单、固定 ZIP SHA256、13 项文件清单、路径安全、CRC、内部 SHA256 和版本元数据。它只更新管理程序代码，不更改 /etc/global-home-nodes 或服务。

## gl 菜单与狗妈 JSON

菜单包括查看家宽线路、显示 Reality 公共参数、导出狗妈 JSON、检查 UUID 与 Xray 路由、检查出站状态、查看运行状态、首次部署、读取供应商 proxy 最新线路并更新、从授权 JSON 更新线路、检查或安装管理程序更新、卸载，以及修改公网映射 IP/端口。

已部署机器更新供应商出口时，选择“读取供应商 proxy 最新线路并更新”或“从授权 JSON 更新线路”。修改公网映射时选择菜单项 13；工具只修改公网入口资料和订阅文件，不重新读取供应商线路。

导出文件只包含通过 UUID、email、路由和线路元数据一致性检查的线路；无法唯一匹配的项会显示为异常。狗妈 JSON 位于 /etc/global-home-nodes/exports/dogma-relay.json。

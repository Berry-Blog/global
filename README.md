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

# Global Home v2.0.1 使用说明

## 安装

```sh
curl -fLO https://raw.githubusercontent.com/Berry-Blog/global/main/global-home-nodes-install-v2.0.1.sh
chmod +x global-home-nodes-install-v2.0.1.sh
sh global-home-nodes-install-v2.0.1.sh
```

## 校验安装包

```sh
sh global-home-nodes-install-v2.0.1.sh --verify
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

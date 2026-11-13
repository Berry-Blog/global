# Global Home v2.0.0 使用说明

## 安装

```sh
curl -fLO https://raw.githubusercontent.com/Berry-Blog/global/main/global-home-nodes-install-v2.0.0.sh
chmod +x global-home-nodes-install-v2.0.0.sh
sh global-home-nodes-install-v2.0.0.sh
```

已安装旧版的机器，执行以上命令即可更新管理程序。

## 校验安装包

```sh
sh global-home-nodes-install-v2.0.0.sh --verify
```

## 常用命令

```sh
# 查看运行状态
global-home-nodes status

# 重新读取家宽出口并更新节点
global-home-nodes refresh

# 更新管理程序和版本适配器
global-home-nodes update

# 只检查是否有管理程序更新
global-home-nodes update --check-only

# 使用供应商导出的授权 JSON
global-home-nodes refresh --import-json /root/my-authorized-exits.json

# 卸载本工具
global-home-nodes uninstall
```

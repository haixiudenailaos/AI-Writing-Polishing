# VSCode风格小说润色应用

## 项目概述

基于PyQt5开发的桌面应用程序，采用VSCode风格界面，为小说创作者提供文本润色功能。

## 功能特性

- 按下 Enter 键触发AI API进行润色
- 润色结果以行形式展示，并提供接受/拒绝操作
- Tab 键快速确认当前选中行
- 原文行与润色行使用不同颜色高亮
- 提供亮色、暗色、暗青色主题切换，并保存用户偏好
- 具有加载状态和错误提示

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
python -m app.main
```

## 注意事项

- 将AI API密钥配置到环境变量 `AI_API_KEY`
- 如需更换模型，可设置 `AI_MODEL`
- UI 设计严格遵循 VSCode 风格

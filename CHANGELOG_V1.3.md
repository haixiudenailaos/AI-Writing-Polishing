# 字见润新 V1.3 更新日志

**发布日期**: 2025-11-04  
**版本号**: 1.3.0.0  
**分支**: release/v1.2 → V1.3

---

## 🎉 版本亮点

V1.3 版本专注于**用户体验提升**和**功能完善**，新增多个实用组件，优化了应用启动流程、窗口管理和文件处理能力。

---

## ✨ 新增功能

### 1. 用户体验增强

#### 启动画面
- ✅ 新增现代化启动画面 (`SplashScreen` 和 `ModernSplashScreen`)
- ✅ 带进度条的加载动画，提供实时加载状态反馈
- ✅ 渐变背景设计，提升视觉体验

#### 窗口几何管理
- ✅ 智能窗口位置和大小持久化 (`WindowGeometryManager`)
- ✅ 多屏幕支持，自动识别上次使用的显示器
- ✅ DPI自适应，确保在不同分辨率下正常显示
- ✅ 防止窗口在屏幕外丢失

#### 知识库管理增强
- ✅ 统一的知识库管理对话框 (`KnowledgeBaseManagerDialog`)
- ✅ 实时知识库状态指示器 (`KnowledgeBaseStatusIndicator`)
- ✅ 支持历史知识库、大纲、人设三种类型
- ✅ 可视化的知识库激活状态和文档数量

### 2. UI 组件升级

#### 新增 UI 组件
- ✅ `PremiumComboBox` - 高级下拉框组件，支持搜索和分组
- ✅ `PulsingLabel` - 脉冲标签动画组件，提供动态视觉反馈
- ✅ 改进的批量润色对话框 (`BatchPolishDialog`)
- ✅ 增强的文件浏览器 (`FileExplorer`)
- ✅ 优化的输出列表 (`OutputList`)

#### 设计系统
- ✅ 统一的设计系统 (`DesignSystem`)
- ✅ 主题管理器 (`ThemeManager`)
- ✅ UI 增强器 (`UIEnhancer`)
- ✅ 一致的视觉风格和交互体验

### 3. 文件处理增强

#### 格式转换器
- ✅ 多格式文档转换支持 (`FormatConverter`)
- ✅ 支持 .txt, .docx, .pdf, .md, .html 等格式互转
- ✅ 批量文件格式转换
- ✅ 格式检测和转换建议

#### 自动化管理
- ✅ 自动保存管理器 (`AutoSaveManager`)
- ✅ 自动导出管理器 (`AutoExportManager`)
- ✅ 定时自动保存，防止数据丢失
- ✅ 智能导出策略

### 4. 智能功能优化

#### 剧情预测优化
- ✅ 创意导向的提示词生成
- ✅ 温度参数优化 (普通预测: 0.85, 知识库增强: 0.8)
- ✅ 时间序权重增强 (`recency_boost_strength`)
- ✅ 混合搜索优化 (`hybrid_search_alpha`)

#### 知识库增强
- ✅ 三种知识库类型支持（历史/大纲/人设）
- ✅ 文档距离相关性计算
- ✅ 时间序权重自动调整
- ✅ 混合搜索策略（向量+关键词）

---

## 🔧 核心模块列表

### 新增核心模块
```
app/
├── format_converter.py          # 文件格式转换器
├── window_geometry.py           # 窗口几何管理器
├── auto_save_manager.py         # 自动保存管理器
└── auto_export_manager.py       # 自动导出管理器
```

### 新增 UI 组件
```
app/widgets/
├── splash_screen.py                    # 启动画面
├── knowledge_base_manager_dialog.py    # 知识库管理对话框
├── knowledge_base_status_indicator.py  # 知识库状态指示器
├── premium_combobox.py                 # 高级下拉框
├── pulsing_label.py                    # 脉冲标签
├── batch_polish_dialog.py              # 批量润色对话框
├── file_explorer.py                    # 文件浏览器
├── design_system.py                    # 设计系统
├── theme_manager.py                    # 主题管理器
├── ui_enhancer.py                      # UI增强器
└── output_list.py                      # 输出列表
```

### 优化的现有模块
```
app/
├── api_client.py        # API 调用优化（温度参数、提示词）
├── config_manager.py    # 配置管理增强（窗口状态、知识库配置）
├── knowledge_base.py    # 时间序权重增强
├── prompt_generator.py  # 提示词生成器（创意导向）
└── main.py              # 主程序集成所有新功能
```

---

## 📦 构建配置

### build_all.py 更新
- ✅ 添加所有新模块到构建检查列表
- ✅ 更新版本号为 V1.3
- ✅ 新增 V1.3 功能测试说明
- ✅ 详细的模块说明和测试指南

### 版本信息
- ✅ 更新 `version_info.txt` 为 1.3.0.0
- ✅ 更新启动画面版本显示
- ✅ 更新版权信息为 2024-2025

---

## 🧪 测试要点

### 1. 启动与窗口
- [ ] 启动画面正常显示，加载提示准确
- [ ] 窗口位置和大小正确恢复
- [ ] 多屏幕环境下窗口显示正常
- [ ] 高 DPI 显示器下界面清晰

### 2. 知识库管理
- [ ] 知识库管理对话框打开正常
- [ ] 三种知识库类型创建成功
- [ ] 状态指示器实时更新
- [ ] 知识库激活/删除功能正常

### 3. 文件处理
- [ ] 格式转换功能正常
- [ ] 批量转换成功
- [ ] 自动保存工作正常
- [ ] 自动导出功能正常

### 4. UI 交互
- [ ] 所有新增组件显示正常
- [ ] 动画效果流畅
- [ ] 主题切换正常
- [ ] 响应速度良好

### 5. 智能功能
- [ ] 剧情预测质量提升
- [ ] 知识库检索准确
- [ ] 时间序权重生效
- [ ] 温度参数调整有效

---

## 📝 配置项更新

### app_config.json 新增配置
```json
{
  "window_state": {
    "x": 100,
    "y": 100,
    "w": 1280,
    "h": 800,
    "is_maximized": false,
    "screen": "\\\\?\\DISPLAY#..."
  },
  "kb_config": {
    "recency_boost_strength": 0.3,
    "hybrid_search_alpha": 0.7
  },
  "auto_save": {
    "enabled": true,
    "interval": 300
  },
  "auto_export": {
    "enabled": false,
    "format": ".docx"
  }
}
```

---

## 🚀 升级说明

### 从 V1.2 升级到 V1.3

1. **备份配置文件**
   ```
   app_data/app_config.json
   ```

2. **运行新版本**
   - 首次启动会自动迁移配置
   - 窗口状态会自动记录

3. **配置检查**
   - 检查知识库路径是否正确
   - 验证 API 配置是否保留
   - 确认自定义设置是否生效

4. **功能验证**
   - 测试知识库管理功能
   - 验证文件格式转换
   - 确认窗口位置记忆

---

## 🐛 已知问题

目前暂无已知严重问题。

---

## 📚 文档更新

- ✅ `build_all.py` - 构建脚本更新
- ✅ `CHANGELOG_V1.3.md` - 本更新日志
- ✅ `version_info.txt` - 版本信息文件

---

## 👥 贡献者

感谢所有参与 V1.3 开发的贡献者！

---

## 📞 反馈与支持

如遇到问题或有改进建议，请通过以下方式反馈：
- 提交 Issue
- 联系开发团队

---

**字见润新团队**  
2025年11月4日


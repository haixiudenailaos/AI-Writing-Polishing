# 一键批量替换功能说明

## 功能概述

本次优化实现了**一键批量替换所有累积的润色结果**，并支持**动态行号调整机制**，确保在用户插入/删除行时，润色结果的行号能够自动正确调整。

## 核心特性

### 1. **一键替换所有润色结果**

**操作方式：** 按 `TAB` 键

**功能说明：**
- 将右侧面板中**所有累积的润色结果**一次性全部替换到左侧对应位置
- 替换顺序：**从后往前**（从大行号到小行号），避免替换过程中行号错乱
- 替换完成后，自动清空润色结果面板并隐藏

**替换策略：**
```python
# 按行号从大到小排序
sorted_results = sorted(all_results, key=lambda x: x.line_number, reverse=True)

# 依次替换
for result in sorted_results:
    replace_text_by_content(result.original_text, result.current_text)
```

**为什么从后往前替换？**
- 如果从前往后替换，每次替换会改变文档内容，导致后续行号失效
- 从后往前替换，确保每个替换操作不影响前面行的位置

### 2. **动态行号调整机制**

**触发时机：** 用户在左侧编辑器中插入或删除行

**工作原理：**

```python
# 监听文本变化
def _on_text_changed(self):
    current_line_count = editor.blockCount()
    delta = current_line_count - last_line_count  # 计算行数变化
    
    # 调整润色结果的行号
    polish_result_panel.adjust_line_numbers(current_block, delta)
```

**调整逻辑：**

```python
def adjust_line_numbers(changed_line: int, delta: int):
    """
    Args:
        changed_line: 发生变化的行号
        delta: 行数变化量（正数=插入，负数=删除）
    """
    for item in result_items:
        # 只调整变化行之后的结果
        if item.line_number > changed_line:
            item.line_number += delta
```

**示例场景：**

#### 场景1：插入新行

```
原始状态：
  L10: 第一句话 → 润色结果1
  L15: 第二句话 → 润色结果2
  L20: 第三句话 → 润色结果3

用户在 L12 插入一行 → delta = +1

调整后：
  L10: 第一句话 → 润色结果1 (不变)
  L16: 第二句话 → 润色结果2 (15+1=16)
  L21: 第三句话 → 润色结果3 (20+1=21)
```

#### 场景2：删除行

```
原始状态：
  L10: 第一句话 → 润色结果1
  L15: 第二句话 → 润色结果2
  L20: 第三句话 → 润色结果3

用户在 L12 删除一行 → delta = -1

调整后：
  L10: 第一句话 → 润色结果1 (不变)
  L14: 第二句话 → 润色结果2 (15-1=14)
  L19: 第三句话 → 润色结果3 (20-1=19)
```

### 3. **UI显示优化**

**隐藏行号信息：**
- 右侧润色结果面板不再显示行号前缀
- 行号仅用于内部跟踪和定位，对用户不可见

**显示格式：**

```
之前（显示行号）：
[1] L42: 他缓缓走向远方，心中充满了希望与期待。
[2] L45: 夜幕降临，星辰点点闪烁在天际。
[3] L48: 她轻声低语，如同春风拂过湖面。

现在（纯文本）：
他缓缓走向远方，心中充满了希望与期待。
夜幕降临，星辰点点闪烁在天际。
她轻声低语，如同春风拂过湖面。
```

**优势：**
- 界面更简洁清爽
- 用户专注于润色内容本身
- 避免行号信息造成的视觉干扰

### 4. **快捷键说明**

| 快捷键 | 功能 | 说明 |
|--------|------|------|
| `Enter` | 触发润色 | 换行并润色上一行文本 |
| `TAB` | 一键替换所有 | 批量替换右侧所有润色结果到左侧 |
| `~` | 清空拒绝 | 清空右侧所有润色结果 |

## 使用流程示例

### 典型工作流

```
步骤1：连续写作与润色
━━━━━━━━━━━━━━━━━━━━
左侧编辑器：                右侧润色面板：
第一句话<Enter>             [润色中...]
继续写第二句<Enter>         第一句话的润色结果
继续写第三句<Enter>         第一句话的润色结果
继续写第四句<Enter>         第二句话的润色结果
                            第一句话的润色结果
                            第二句话的润色结果
                            第三句话的润色结果

步骤2：批量替换
━━━━━━━━━━━━━━━━━━━━
按 TAB 键 → 所有润色结果一次性替换完成！
右侧面板自动清空并隐藏
```

## 技术实现细节

### 1. 数据结构

```python
@dataclass
class PolishResultItem:
    original_text: str      # 原始文本（用于精确定位）
    polished_text: str      # AI润色后的文本
    line_number: int        # 对应的原文行号（动态调整）
    timestamp: float        # 创建时间戳
    current_text: str       # 当前编辑后的文本
```

### 2. 核心方法

#### (1) 一键替换所有

```python
def _on_editor_tab(self):
    all_results = polish_result_panel.get_all_results()
    
    # 从后往前排序
    sorted_results = sorted(all_results, key=lambda x: x.line_number, reverse=True)
    
    # 批量替换
    for result in sorted_results:
        replace_text_by_content(result.original_text, result.current_text)
    
    # 清空面板
    polish_result_panel.hide_result()
```

#### (2) 动态行号调整

```python
def adjust_line_numbers(changed_line: int, delta: int):
    for item in result_items:
        if item.line_number > changed_line:
            item.line_number += delta
            if item.line_number < 0:
                item.line_number = 0
```

#### (3) 文本内容精确定位

```python
def _replace_text_by_content(original_text: str, new_text: str) -> bool:
    full_text = editor.toPlainText()
    match_position = full_text.find(original_text)
    
    if match_position >= 0:
        cursor = editor.textCursor()
        cursor.setPosition(match_position)
        cursor.setPosition(match_position + len(original_text), KeepAnchor)
        cursor.insertText(new_text)
        return True
    return False
```

### 3. 监听机制

```python
# 编辑器连接文本变化信号
editor.textChanged.connect(_on_text_changed)

def _on_text_changed(self):
    current_line_count = editor.blockCount()
    
    if current_line_count != last_line_count:
        delta = current_line_count - last_line_count
        current_block = editor.textCursor().blockNumber()
        
        # 调整润色结果行号
        polish_result_panel.adjust_line_numbers(current_block, delta)
    
    last_line_count = current_line_count
```

## 优势总结

### ✅ 解决的问题

1. **批量处理效率**
   - ❌ 旧方案：需要逐个按TAB替换，费时费力
   - ✅ 新方案：一键替换所有，瞬间完成

2. **行号同步问题**
   - ❌ 旧方案：用户插入/删除行后，行号错位，替换失败
   - ✅ 新方案：动态调整行号，始终保持正确映射

3. **界面简洁性**
   - ❌ 旧方案：显示行号前缀，视觉干扰
   - ✅ 新方案：纯文本显示，简洁清爽

4. **替换顺序问题**
   - ❌ 旧方案：从前往后替换，导致后续行号失效
   - ✅ 新方案：从后往前替换，确保每次替换不影响前面的行

### 🎯 用户体验提升

- **写作流畅性**：连续写作不中断，润色在后台累积
- **批量处理快速**：一键完成所有替换，无需逐个操作
- **智能行号跟踪**：自动适应文档结构变化
- **界面清爽**：专注内容，无干扰信息

## 注意事项

1. **原文修改检测**
   - 如果润色后，原文被用户手动修改，替换时会因找不到原文而失败
   - 系统会提示失败数量

2. **行号跟踪限制**
   - 动态行号调整基于行数变化检测
   - 如果用户大量复制粘贴内容，可能导致行号偏移
   - 建议完成大量编辑后，清空润色结果重新润色

3. **替换顺序保证**
   - 系统确保从后往前替换，避免行号混乱
   - 用户无需关心替换顺序

## 总结

本次优化实现了：
1. ✅ **一键批量替换**：TAB键一次性替换所有润色结果
2. ✅ **动态行号调整**：自动适应插入/删除行操作
3. ✅ **UI简化**：隐藏行号信息，纯文本显示
4. ✅ **智能排序**：从后往前替换，避免行号错乱

用户现在可以自由写作，累积润色结果，最后一键批量替换，极大提升了写作效率和体验！

# 文本精确定位与替换方案

## 问题描述

在小说润色工具中，当用户触发多次润色并在不同位置编辑时，如果仅依赖行号来定位和替换文本，会出现以下问题：

1. **行号错位**：用户在等待润色结果期间继续编辑，可能会增删行，导致保存的行号失效
2. **多次润色冲突**：连续触发多个润色请求，后续替换时可能覆盖错误的行
3. **异步处理延迟**：润色在后台执行，用户编辑可能已经改变了文档结构

## 解决方案

### 核心思路

**使用文本内容作为定位标记，而非行号**

- 保存被润色的原始文本内容
- 替换时通过文本匹配找到正确位置
- 即使行号变化，仍能精确定位

### 实现细节

#### 1. 保存原始文本标记

```python
# app/main.py - MainWindow.__init__()
self._current_polish_text: str = ""  # 记录被润色的原始文本，用于精确定位

# _on_editor_enter() 触发润色时
self._current_polish_text = current_line  # 保存原文
```

#### 2. 传递原文到结果面板

```python
# _on_context_polish_finished()
self.polish_result_panel.show_result(
    original_text,  # 原始文本
    polished_text,  # 润色结果
    self._current_polish_line  # 行号仅用于视觉对齐
)
```

#### 3. 基于内容的精确替换

```python
def _replace_text_by_content(self, original_text: str, new_text: str) -> bool:
    """
    通过匹配原始文本内容来精确替换，避免行号错位
    """
    # 1. 获取全文
    full_text = self.editor.toPlainText()
    
    # 2. 精确查找原文位置
    match_position = full_text.find(original_text)
    
    # 3. 如果精确匹配失败，尝试模糊匹配（去除空格）
    if match_position == -1:
        stripped_original = original_text.strip()
        lines = full_text.splitlines()
        
        for i, line in enumerate(lines):
            if line.strip() == stripped_original:
                # 找到匹配行，计算位置
                match_position = sum(len(lines[j]) + 1 for j in range(i))
                original_text = line  # 使用实际行文本
                break
    
    # 4. 如果仍未找到，返回失败
    if match_position == -1:
        return False
    
    # 5. 使用QTextCursor执行替换
    cursor = self.editor.textCursor()
    cursor.setPosition(match_position)
    cursor.movePosition(
        QtGui.QTextCursor.Right, 
        QtGui.QTextCursor.KeepAnchor, 
        len(original_text)
    )
    
    # 6. 验证选中的文本是否匹配
    if cursor.selectedText() != original_text:
        return False
    
    # 7. 执行替换
    cursor.insertText(new_text)
    
    return True
```

#### 4. TAB键触发替换

```python
def _on_editor_tab(self) -> None:
    if self.polish_result_panel.isVisible():
        result_text = self.polish_result_panel.get_current_text()
        original_text = self.polish_result_panel.get_original_text()
        
        # 使用内容匹配而非行号
        success = self._replace_text_by_content(original_text, result_text)
        
        if success:
            self._show_message("已替换对应文本", duration_ms=1500)
        else:
            self._show_message("未找到原文内容，可能已被修改或删除", duration_ms=2500, is_error=True)
```

### 优势

1. **抗干扰能力强**：即使用户在润色期间增删行，仍能正确定位
2. **精确匹配**：通过文本内容完全匹配，避免覆盖错误行
3. **用户友好**：失败时给出明确提示，不会静默错误替换
4. **容错机制**：提供精确匹配和模糊匹配两种方式

### 工作流程

```
1. 用户在第5行输入文字并按Enter
   ↓
2. 保存原文："这是第五行的内容"
   保存行号：4（从0开始）
   ↓
3. 后台开始润色，用户继续在第6、7、8行输入
   ↓
4. 润色完成，显示结果
   原文：自动仍然是"这是第五行的内容"
   ↓
5. 用户按TAB键替换
   ↓
6. 系统在全文中搜索"这是第五行的内容"
   ↓
7. 找到匹配位置（现在可能是第5行或其他行）
   ↓
8. 精确替换该位置的文本
   ↓
9. 完成！无论行号如何变化，都能正确替换
```

### 边界情况处理

#### 情况1：原文被修改
```
用户触发润色后又修改了那一行
→ find()找不到原文
→ 提示"未找到原文内容，可能已被修改"
→ 不执行替换，避免错误覆盖
```

#### 情况2：原文被删除
```
用户触发润色后删除了那一行
→ find()找不到原文
→ 提示"可能已被删除"
→ 不执行替换
```

#### 情况3：存在多处相同文本
```
文档中有多处相同的文本
→ find()找到第一处
→ 替换第一处
→ 建议：用户应修改其中一处使其唯一，再触发润色
```

#### 情况4：文本首尾空格不同
```
保存的原文："  内容  "
实际文本：" 内容 "（空格数不同）
→ 精确匹配失败
→ 启用模糊匹配（strip()后比较）
→ 找到匹配行，使用实际文本进行替换
```

## 代码修改清单

### 1. MainWindow类变量
- 新增：`self._current_polish_text` - 保存原始文本

### 2. 新增方法
- `_replace_text_by_content()` - 基于内容的替换方法

### 3. 修改方法
- `_on_editor_enter()` - 保存原始文本
- `_on_editor_tab()` - 使用新的替换逻辑
- `_on_context_polish_finished()` - 传递原始文本

### 4. PolishResultPanel修改
- 已有 `get_original_text()` 方法可获取原文

## 测试场景

### 测试1：正常流程
1. 在第5行输入文本
2. 按Enter触发润色
3. 不做任何修改
4. 润色完成后按TAB
5. **预期**：第5行被正确替换

### 测试2：中间插入行
1. 在第5行输入文本并按Enter触发润色
2. 在第3行插入2个新行
3. 润色完成（原第5行现在变成第7行）
4. 按TAB
5. **预期**：第7行（内容匹配的那行）被正确替换

### 测试3：原文被修改
1. 在第5行输入"原始文本"并按Enter
2. 在润色过程中将第5行改为"修改后文本"
3. 润色完成
4. 按TAB
5. **预期**：提示"未找到原文"，不执行替换

### 测试4：多次润色
1. 在第3行按Enter触发润色A
2. 在第5行按Enter触发润色B
3. 润色A完成，显示结果
4. 润色B完成，显示结果（覆盖润色A）
5. 按TAB
6. **预期**：替换第5行（最新的润色结果）

## 注意事项

1. **唯一性要求**：建议用户避免文档中出现完全相同的行
2. **及时替换**：建议用户在润色完成后尽快替换，避免原文被修改
3. **视觉提示**：可考虑在UI上高亮显示即将被替换的行
4. **撤销功能**：Qt编辑器自带的Ctrl+Z可撤销错误替换

## 未来优化方向

1. **多处匹配处理**：如果找到多处相同文本，让用户选择替换哪一处
2. **智能行追踪**：结合行号和内容的混合策略
3. **历史记录**：保存润色历史，支持重新应用
4. **差异预览**：替换前显示diff对比

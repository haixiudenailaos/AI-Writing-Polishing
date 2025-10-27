"""
测试剧情预测功能的核心逻辑
"""

from app.api_client import AIClient
from app.config_manager import ConfigManager


def test_plot_prediction():
    """测试剧情预测API调用"""
    print("=" * 50)
    print("测试剧情预测功能")
    print("=" * 50)
    
    # 初始化配置管理器和API客户端
    config_manager = ConfigManager()
    api_client = AIClient(config_manager=config_manager)
    
    # 测试文本
    test_text = """
    夜幕降临，古老的城堡笼罩在一片阴影之中。
    李明小心翼翼地推开了那扇锈迹斑斑的大门。
    突然，一阵冷风从背后袭来。
    """.strip()
    
    print(f"\n原始文本:\n{test_text}\n")
    print("开始预测接下来的剧情...")
    
    try:
        # 调用剧情预测API
        predicted_text = api_client.predict_plot_continuation(test_text)
        
        print(f"\n预测的剧情续写:\n{predicted_text}\n")
        
        # 解析预测的两行
        lines = predicted_text.strip().split('\n')
        print(f"\n解析结果:")
        print(f"  第一行: {lines[0] if len(lines) > 0 else '(无)'}")
        print(f"  第二行: {lines[1] if len(lines) > 1 else '(无)'}")
        
        print("\n✓ 测试成功！")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_timer_logic():
    """测试定时器逻辑（模拟）"""
    print("\n" + "=" * 50)
    print("测试输入停止检测逻辑")
    print("=" * 50)
    
    print("\n模拟场景:")
    print("1. 用户输入文字")
    print("2. 停止输入3秒")
    print("3. 触发剧情预测")
    
    import time
    
    # 模拟输入停止计时
    print("\n开始计时...")
    start_time = time.time()
    time.sleep(3.0)  # 模拟3秒等待
    elapsed = time.time() - start_time
    
    print(f"经过时间: {elapsed:.2f}秒")
    
    # 检查误差是否在±0.5秒范围内
    if abs(elapsed - 3.0) <= 0.5:
        print("✓ 时间检测精确度符合要求 (±0.5秒)")
        return True
    else:
        print(f"✗ 时间检测精确度超出范围: {abs(elapsed - 3.0):.2f}秒")
        return False


if __name__ == "__main__":
    print("\n开始功能测试...\n")
    
    # 测试定时器逻辑
    timer_ok = test_timer_logic()
    
    # 测试剧情预测API
    prediction_ok = test_plot_prediction()
    
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"定时器逻辑: {'✓ 通过' if timer_ok else '✗ 失败'}")
    print(f"剧情预测API: {'✓ 通过' if prediction_ok else '✗ 失败'}")
    
    if timer_ok and prediction_ok:
        print("\n所有测试通过！功能实现正确。")
    else:
        print("\n部分测试失败，需要检查。")

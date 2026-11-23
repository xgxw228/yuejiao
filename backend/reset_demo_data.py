"""把数据库恢复到 seed 之后的干净状态（回归测试后跑这个）。

实现上直接调用 seed.rebuild()，避免出现「按 id 阈值删」这类逻辑
跟种子数据的 id 范围脱节的问题。
"""

from seed import rebuild

if __name__ == "__main__":
    rebuild()
    print("清理完成")

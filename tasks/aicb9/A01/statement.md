# A01 · Trace the Execution

## 场景

你正在阅读 TinyCache，一个支持固定 TTL 和 LRU 淘汰策略的小型缓存组件。系统容量为 2，TTL 为 5 秒。读取不会刷新 TTL；元素在 `now >= expires_at` 时过期。

请阅读 `fixtures/tinycache/repository/tinycache/cache.py`，预测下列操作执行后的状态：

```python
cache.set("a", 1, now=0)
cache.set("b", 2, now=1)
cache.get("a", now=2)
cache.set("c", 3, now=3)
cache.get("b", now=4)
cache.get("a", now=5)
```

## 提交格式

复制 `starter_answer.json`，填写六个步骤的结果：

- `result`：操作返回值；`set` 的返回值为 `null`。
- `lru`：从最久未使用到最近使用的 key 顺序。
- `expired`：本步因 TTL 删除的 key。
- `evicted`：本步因容量限制淘汰的 key。

不能只提交最终缓存内容。每一步的状态变化都需要可核验。

# B03 · Test the Hidden Bug

## 场景

MiniStore 的订单分页接口在常见数据上看起来正常，但在相同时间戳、分页边界和最后一页时可能重复或遗漏记录。

接口：

```python
list_orders(rows: list[dict], limit: int, cursor: str | None = None) -> dict
```

契约：

1. 排序为 `created_at DESC, id DESC`。
2. Cursor 是排他游标：下一页不得重复上一页最后一条记录。
3. `limit` 必须是 1–50 的整数。
4. 只有确实存在下一页时才返回 `next_cursor`。
5. 从第一页持续翻页，必须完整覆盖记录且不重复。

## 任务

只编写测试，不修改业务实现。参考实现位于 `fixtures/ministore/b03/reference/ministore/pagination.py`。提交一个 pytest 文件，使用：

```python
from ministore.pagination import list_orders
```

本地开发评测器会将同一测试文件分别运行在参考实现和六个 Mutants 上。有效测试必须通过参考实现；只有断言失败才算杀死 Mutant，导入错误、收集错误和超时都不算。

## 建议重点

- 相同 `created_at`、不同 `id`。
- 两页之间的排他边界。
- 恰好一页数据、没有下一页。
- 下一页 Cursor 必须来自当前页最后一条记录。
- `limit=0`、负数和超过 50。

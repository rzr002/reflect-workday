# Reflection contract

`reflection.json` 是给页面使用的轻量回想稿，由短线索和用户陈述生成。

```json
{
  "headline": "接口兼容与测试准备是今天的主要事项",
  "note": "机器看到的是工作线索，不是完整工时。",
  "schedule": {
    "work_periods": [
      {"start": "09:00", "end": "12:00"},
      {"start": "13:30", "end": "17:30"}
    ],
    "breaks": [
      {"start": "12:00", "end": "13:30", "label": "午休"}
    ]
  },
  "highlights": [
    "确认接口兼容处理方式",
    "补齐边界测试",
    "更新交付说明"
  ],
  "blocks": [
    {
      "id": "focus-1",
      "date": "2025-03-10",
      "start": "09:10",
      "end": "10:20",
      "title": "接口兼容方案核对",
      "summary": "核对版本差异并确认兼容处理方式。",
      "source": "codex",
      "evidence": "observed",
      "event_ids": ["codex:..."]
    }
  ],
  "prompts": [
    {
      "date": "2025-03-10",
      "start": "15:00",
      "end": "16:00",
      "text": "下午这段没有数字线索：是在开会、思考，还是暂时离开了电脑？"
    }
  ]
}
```

## 编写规则

- `blocks` 控制页面主时间线；没有时页面回退展示原始短事件。
- 相邻、同项目、同目的的事件可合并；不要为了填满时间线扩大区间。
- `source` 使用 `codex`、`git`、`manual` 或 `mixed`。
- `evidence` 使用 `observed`、`recalled` 或 `unknown`。
- `manual` / `recalled` 只来自用户原话。
- `摸鱼` 只能由用户主动选择或描述，不能从空白推断。
- `schedule.work_periods` 来自用户明确回答；支持多段，不提供默认朝九晚六。
- `schedule.breaks` 记录午休等固定间隔，用于页面背景说明。
- `prompts` 必须完全落在 `work_periods` 内，优先覆盖较大的工作时段留白，一次保留一至三个；固定休息和非工作时段不提示。
- `headline` 是显示在日期主标题下方的叙事副标题；用一句日常语言概括结果，不要重复日期，也不要写抽象能力标签。
- `headline` 默认只写事项和结果，不用“忙到深夜”“奋战到凌晨”等措辞渲染工作时长；除非用户主动关心作息，否则不把时间跨度写成叙事亮点。
- `blocks` 可以真实重叠；多个 Codex 任务同时运行时保留各自区间，由页面分泳道显示，不强行改成前后相接。
- `blocks.title` 保持短而完整，把解释和结果放进 `summary`；不要把整段用户请求当标题。
- 可以轻松幽默，但不要讽刺、羞辱或替用户粉饰。
- 页面只读；用户在 Codex 对话中补充记忆后，模型将其作为 `manual` / `recalled` 写回本文件并重新渲染，不依赖浏览器本地存储或导入导出。

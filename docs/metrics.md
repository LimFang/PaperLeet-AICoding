# Star history

The English and Chinese READMEs share a daily Star History chart for
[LimFang/PaperLeet-AICoding](https://github.com/LimFang/PaperLeet-AICoding). The light and
dark SVGs retain the original hand-drawn style and bundled lettering. See the
[font source and license](../scripts/assets/metrics-lettering/README.md).

The chart groups the repository's **current stargazers** by their original star
date in UTC, then plots the cumulative count. GitHub's
[timestamped stargazers endpoint](https://docs.github.com/en/rest/activity/starring#list-stargazers)
supplies these dates. Removed stars are absent, so the curve is a reconstruction
from current stars rather than a record of every historical total. Only aggregate
dates and counts are stored in the chart snapshot.

## Automatic updates

[README star history](../.github/workflows/readme-metrics.yml) runs daily at
17:17 UTC, when its generator changes, or through **Actions → README star history
→ Run workflow**. GitHub may delay scheduled runs. It updates only
`docs/metrics/stars.json`, `stars.svg`, and `stars-dark.svg` on this repository's
`main` branch, using the built-in repository token. No additional secret or
running PaperLeet server is needed. The job is restricted to
`LimFang/PaperLeet-AICoding` on `main`. Push the workflow changes to that branch
and enable GitHub Actions in the fork before expecting scheduled updates.

The SVG footer shows the data timestamp. If GitHub is unavailable, the generator
retains the last verified snapshot and labels it as cached/stale. Without a
verified snapshot it shows a no-data state. An empty repository has an observed
zero; a single observed date is shown as a point until more dates are available.
The generator rejects another repository's cached history, including the
original PaperLeet snapshot, so upstream stars cannot be relabeled as this fork's.

## Local refresh

```bash
python3 scripts/readme_metrics.py --output-dir docs/metrics
```

The generator uses Python's standard library. Set `GITHUB_TOKEN` to an authorized
repository token if the GitHub endpoint requires authentication or a higher rate
limit. The workflow already supplies that token. Tokens and GitHub user identities
are never written into generated files. The bundled font outlines keep the SVG
self-contained, without external font requests.

## 中文说明

两份 README 展示 `LimFang/PaperLeet-AICoding` 的 Star 曲线，支持 GitHub 的浅色与深色主题。
将工作流推送到 main 并启用 Actions 后，每天北京时间 01:17（UTC 前一天 17:17）调度更新，
也可以在 Actions 中手动触发。生成器拒绝原仓库及其他仓库的缓存；首次获取失败时展示等待数据。

曲线按当前仍保留 Star 的用户的原始 Star 日期累计，以 UTC 为日期口径；
取消的 Star 不在这份统计中。图中注明数据时间，接口失败时保留上次结果并标记缓存，
不会补造增长数据。刷新只依赖 GitHub，不需要启动网站或本机判题服务。

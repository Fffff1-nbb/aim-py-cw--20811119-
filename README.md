# AIM 2627 Python Coursework —— 哨兵 Sentry 控制模块

> **全部题目、规范、评分、提交见 [题面.pdf](题面.pdf)。** 本 README 只讲怎么把环境跑起来；没在这里出现的规格细节，一律以题面为准。

## 1. 环境要求

- Python 3.8+，仅标准库（不允许第三方运行时依赖）；
- 开发工具只需 `pytest`（测试）与 `autopep8`（风格，CI 会检查）；
- VS Code 打开仓库会推荐安装 `ms-python.autopep8` 插件（`.vscode/extensions.json`），保存即格式化即可过风格检查。

## 2. 快速开始

```bash
# 1. 用 GitHub 的 Use this template 创建你自己的仓库，然后 clone
git clone https://github.com/<你的用户名>/<你的仓库>.git
cd <你的仓库>   # 直接在 main 分支上开发

# 创建虚拟环境

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. 装依赖
python -m pip install pytest autopep8

# 3. 启用 AI 会话归档钩子（课程要求，见下方第 3 节）
python -m pip install 'agent-session-commit[pre-commit]==0.1.3' -i https://pypi.org/simple
agent-session-commit install --pre-commit   # 交互选择你的 AI 助手与会话目录

# 4. 跑测试（刚到手：全部 skip，CI 是绿的）
python -m pytest

# 5. 看演示
python main.py

# 6. 打开 题面.pdf 读题，开始实现 src/main/__init__.py 里的 TODO
```

## 3. AI 会话归档（pre-commit）

本课程允许使用 AI，提交的 commit 需要携带 AI 会话归档作为透明化记录：每次 `git commit` 后，钩子会把新增会话自动 amend 进同一个提交（`.agent-sessions/bundles/`），不产生额外的归档提交。支持 Claude Code、OpenAI Codex CLI、GitHub Copilot CLI、Qoder、ZCode、Trae、Tencent CodeBuddy 等（完整名单见 [AgentLedger](https://github.com/Gentle-Lijie/AgentLedger)）。

- 配置是仓库本地的：每个 clone 运行一次 `agent-session-commit install --pre-commit`，方向键选择 agent、确认其会话目录即可；
- 不想用 TUI 可手动配置：`git config --local agent-session.agent claude`、`git config --local agent-session.source "<会话目录>"`，然后 `python -m pip install 'pre-commit>=3.2.0' && pre-commit install`；
- 归档是普通 Git 内容且会推送到公开仓库——不要在 AI 会话里粘贴令牌等敏感信息；
- 换了 agent 或目录就重跑一次安装命令；卸载：从 `.pre-commit-config.yaml` 移除该条目后重跑 `pre-commit install`。

## 4. 本地开发循环

- **写代码**：全部作业在 `src/main/__init__.py`，按题面各题规范补全每个标有 TODO 的函数；注释里标注了对应的题面主题，推荐顺序 Q1 → Q6。
- **跑测试**：`python -m pytest` —— 可见测试是规格书的一部分，未实现的函数自动 skip，实现一个、对应测试亮一个。本地全绿 ≠ 满分（见题面）。
- **看演示**：`python main.py`（等价于 `PYTHONPATH=src python -m main`），随实现进度逐段点亮，不进测试。
- **Q6 自测**：`python tools/run_seeds.py --q6`（200 张固定地图统计），单 seed 渲染 `python tools/run_seeds.py --q6 --seed <N> --render`，Bonus 模式 `python tools/run_seeds.py --bonus`。

## 5. 仓库结构（哪些能改）

| 路径 | 说明 | 能否修改 |
|---|---|---|
| `src/main/__init__.py` | 你的全部作业（TODO 所在） | ✅ |
| `README.md` | 仅末尾两个"你来写"小节 | ✅ |
| `题面.pdf` | 题面（唯一规格说明） | ❌ 勿改 |
| `src/main/legacy_patrol.py` | Q7 模块（与主体同步发布，修复其缺陷） | Q7 时 ✅ |
| `.pre-commit-config.yaml` | AI 会话归档钩子配置 | ❌ 勿改 |
| `src/tests/`、`tools/`、`.github/`、`conftest.py`、`pytest.ini`、`main.py` | 测试与基础设施 | ❌ 勿改 |

CI 只允许修改 `src/main/**`、`README.md` 与 `.agent-sessions/**`（AI 会话归档）——其余文件改了直接红；autopep8 `--diff` 非空即败。提交方式（push、问卷、commit 粒度）见题面"提交与验收"一节。

## 6. 设计说明（你来写）

整体按"感知 → 载体 → 导航 → 决策 → 任务"这条链从上往下写，一层搭一层：

- **Q1 自检**：`hp_ratio` 只干一件事——算百分比、四舍五入、再夹到 0~100；`status_report` 只负责拼字符串，档位判断和逐字符对齐都复用 `hp_ratio` 和 f-string，避免两处口径不一致。
- **Q2 日志分析**：把"一行能不能解析"拆到 `_parse_sensor_line`、`_parse_json_line` 两个小函数，解析不了就返回 `None` 跳过；主函数只管"分行类型 → 累加 → 统计"。JSON 行用 `seen_ids` 去重。
- **Q3 载体**：`current_pos` 的 setter 只收长度 2 的 tuple/list，复用 `_clamp_cell` 做转换和夹取；构造器也改成 `self.current_pos = start_pos`，让初始化跟后面的赋值走同一套校验。`move_forward` 先看电量、再扣电、再判碰撞；左右转用两张互逆映射表。
- **Q4 导航**：`next_step_toward` 只挑"相邻格不是障碍、且曼哈顿距离变近"的方向，有多个候选就优先走坐标差更大的那个轴，没有就返回当前朝向。
- **Q5 决策**：`decide` 是纯函数，按 R1~R7 的顺序判、命中就返回；输入不合契约就抛 `ValueError`，字段非法就做防御处理（敌距非 int 当 None、机型只认 `"HERO"`）。
- **Q6 巡逻**：每轮"贪心选向 → 转过去 → 走一步"，贪心卡住时切左手规则沿墙绕，能绕出来就回贪心。`report_to_json` 用 `sort_keys=True` 让输出稳定。
- **Bonus**：标准 BFS，`start == target` 返回 0，不可达返回 -1。

## 7. Q7 缺陷分析（你来写）

我先跑 `pytest` 拿到报错，再对着每个函数 docstring 里的契约一行行找，一共 6 处：

1. **`total_route_meters`**：累加的是厘米，却直接当米返回，结果大了 100 倍 → 返回时 `// 100`。
2. **`calibrate`**：`first_positive` 没有正样本时返回 `None`，再拿它做减法就 `TypeError` → 先判 `None` 返回 0。
3. **`log`**：默认参数 `history=[]` 是可变对象，多次调用会共享同一个列表 → 改成 `None` 再在函数里初始化。
4. **`summarize_events`**：`< max_id` 把 id 刚好等于 `max_id` 的事件漏了（契约是"不超过"）→ 改 `<=`。
5. **`run_legacy_sim` 的终止条件**：写反成 `stamina > 20` 就 break → 改成 `stamina <= 20` 才停。
6. **`run_legacy_sim` 缺自增**：循环体少了 `round_ += 1` → 补上，不然死循环。

其中 5、6 是一对互相遮的：只修 6，第一轮就 break；只修 5，就死循环。必须一起修。


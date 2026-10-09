# aim-py-cw-known
# -*- coding: utf-8 -*-
"""AIM 2627 Python Coursework —— 哨兵 Sentry 控制模块（学生骨架）。

你的全部作业都在本文件里：按题面（题面.pdf）各题的规范补全每个标有 TODO 的函数。
- 骨架已提供：Facing / SentryState 枚举、SentryGrid 的构造与只读属性、
  渲染函数 render_frame（demo 用，不进测试）。
- 你要实现：Q1-Q6 与 Bonus 的全部 TODO，以及 SentryGrid 的
  四个方法（current_pos 的 setter、move_forward、turn_left、turn_right）。
- 未实现的函数 raise NotImplementedError：可见测试会自动 skip，
  CI 一开始就是绿的；实现一个，对应测试亮一个。
- `python main.py`（或 PYTHONPATH=src python -m main）可看 ASCII 演示。
"""
import json
from collections import deque
from enum import Enum


# ---------------------------------------------------------------------------
# 仿真世界基础（已提供，勿改）
# ---------------------------------------------------------------------------
class Facing(Enum):
    """朝向枚举。世界坐标 (x, y)：x 向右增长，y 向上增长（数学系）。"""

    UP = (0, 1)
    DOWN = (0, -1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def delta(self):
        """该朝向的单位位移向量 (dx, dy)。"""
        return self.value[0], self.value[1]


# 左转 / 右转朝向映射（Q3 转向与 Q6 沿墙脱困共用）。
_TURN_LEFT = {Facing.UP: Facing.LEFT, Facing.LEFT: Facing.DOWN,
              Facing.DOWN: Facing.RIGHT, Facing.RIGHT: Facing.UP}
_TURN_RIGHT = {v: k for k, v in _TURN_LEFT.items()}


# ---------------------------------------------------------------------------
# Q1 机器人自检（题面 Q1·自检状态计算与报告生成）
# ---------------------------------------------------------------------------
def hp_ratio(hp, max_hp):
    """血量百分比，返回 0-100 的 int（四舍五入并夹取到 0-100）。"""
    if max_hp <= 0:
        return 0
    return max(0, min(100, round(hp * 100 / max_hp)))


def status_report(name, robot_type, hp, max_hp, battery):
    """一行自检报告字符串；档位判定与逐字符格式见题面 Q1 规范。"""
    hp_pct = hp_ratio(hp, max_hp)
    if battery >= 60:
        tier = "OK"
    elif battery >= 20:
        tier = "WARNING"
    else:
        tier = "LOW"
    return f"{name:<10}|{robot_type:^10}|HP {hp_pct:>3}%|BAT {battery:>3}%|{tier}"


# ---------------------------------------------------------------------------
# Q2 战斗日志分析（题面 Q2·多源日志解析与统计）
# ---------------------------------------------------------------------------
_ARMOR_MAP = {"F": "front", "L": "left", "R": "right"}


def _parse_sensor_line(text):
    """解析传感器行（如 "F:32,L:5,R:12"），返回 [(armor, damage), ...]；脏行返回 None。"""
    events = []
    for part in text.split(","):
        part = part.strip()
        letter, sep, val = part.partition(":")
        if not sep:
            return None
        letter = letter.strip()
        val = val.strip()
        if letter not in _ARMOR_MAP or not val.isdigit() or int(val) <= 0:
            return None
        events.append((_ARMOR_MAP[letter], int(val)))
    return events if events else None


def _parse_json_line(text):
    """解析 JSON 行，返回 (armor, damage, id)；脏行返回 None。"""
    try:
        obj = json.loads(text)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    armor = obj.get("armor")
    damage = obj.get("damage")
    if armor not in ("front", "left", "right"):
        return None
    if isinstance(damage, bool) or not isinstance(damage, int) or damage <= 0:
        return None
    return (armor, damage, obj.get("id"))


def analyze_damage_log(lines):
    """解析混合格式伤害日志，返回固定契约的统计 dict。"""
    total = 0
    by_armor = {"front": 0, "left": 0, "right": 0}
    seen_ids = set()
    n_events = 0

    for line in lines:
        if not isinstance(line, str):
            continue
        text = line.strip()
        if not text or text.startswith("#"):
            continue

        if text.startswith("{"):
            ev = _parse_json_line(text)
            if ev is None:
                continue
            armor, damage, eid = ev
            if eid is not None:
                try:
                    if eid in seen_ids:
                        continue
                    seen_ids.add(eid)
                except TypeError:
                    pass  # 不可哈希的 id：无法去重，按独立行计
            total += damage
            by_armor[armor] += damage
            n_events += 1
        else:
            events = _parse_sensor_line(text)
            if events is None:
                continue
            for armor, damage in events:
                total += damage
                by_armor[armor] += damage
                n_events += 1

    if n_events == 0:
        most_hit = None
        avg = 0.0
    else:
        most_hit = max(by_armor, key=lambda k: by_armor[k])
        avg = round(total / n_events, 2)

    return {"total": total, "by_armor": by_armor,
            "most_hit": most_hit, "avg": avg}


# ---------------------------------------------------------------------------
# Q3 SentryGrid（题面 Q3·载体物理规则）
# ---------------------------------------------------------------------------
class SentryGrid:
    """哨兵仿真载体（构造与只读属性已提供；四个 TODO 方法由你实现）。"""

    def __init__(self, width, height, obstacles, enemy_pos,
                 start_pos=(0, 0), facing=Facing.UP, fuel=100):
        self._width = int(width)
        self._height = int(height)
        if self._width <= 0 or self._height <= 0:
            raise ValueError("地图尺寸必须为正")
        # 障碍坐标存入 set，查询 O(1)——已有实现，勿改。
        self._obstacles = set()
        for ob in obstacles:
            x, y = ob
            self._obstacles.add((int(x), int(y)))
        if not isinstance(enemy_pos, (tuple, list)) or len(enemy_pos) != 2:
            raise TypeError("enemy_pos 需要长度为 2 的 tuple/list")
        self._enemy_pos = self._clamp_cell(enemy_pos)
        if self._enemy_pos in self._obstacles:
            raise ValueError("enemy_pos 不能位于障碍物上")
        if not isinstance(facing, Facing):
            facing = Facing.UP
        self._facing = facing
        self._fuel = int(fuel)
        self._collision_count = 0
        self.current_pos = start_pos
        if self._pos in self._obstacles:
            raise ValueError("start_pos 不能位于障碍物上")

    def _clamp_cell(self, cell):
        """已提供：元素转 int 并夹回地图范围（供 __init__ 使用）。"""
        x = int(cell[0])
        y = int(cell[1])
        x = max(0, min(self._width - 1, x))
        y = max(0, min(self._height - 1, y))
        return (x, y)

    # -- 只读属性（已提供，勿改） ------------------------------------------
    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def enemy_pos(self):
        return self._enemy_pos

    @property
    def facing(self):
        return self._facing

    @property
    def fuel(self):
        return self._fuel

    @property
    def collision_count(self):
        return self._collision_count

    @property
    def obstacles(self):
        """障碍集合的只读视图（内部 set 引用，不要修改它）。"""
        return self._obstacles

    @property
    def found_enemy(self):
        return self._pos == self._enemy_pos

    def is_blocked(self, x, y):
        """已提供：坐标是否为障碍或越界（O(1)）。"""
        return ((x, y) in self._obstacles
                or not (0 <= x < self._width and 0 <= y < self._height))

    # -- 你要实现的部分 ------------------------------------------------------
    @property
    def current_pos(self):
        """当前位置 (x, y) 的 tuple。"""
        return self._pos

    @current_pos.setter
    def current_pos(self, value):
        """位置 setter：仅接受长度 2 的 tuple/list，元素转 int 并夹取后存储。"""
        if not isinstance(value, (tuple, list)):
            raise TypeError("current_pos 需要长度为 2 的 tuple/list")
        if len(value) != 2:
            raise TypeError("current_pos 需要长度为 2 的 tuple/list")
        self._pos = self._clamp_cell(value)

    def move_forward(self):
        """朝当前 facing 前进一格，返回执行后的位置。

        断电（电量 <= 0）不位移；碰撞（前方障碍或越界）位置与朝向不变、
        collision_count 加 1；前进消耗 1 单位电量。
        """
        if self._fuel <= 0:
            return self._pos
        self._fuel -= 1
        nx = self._pos[0] + self._facing.delta[0]
        ny = self._pos[1] + self._facing.delta[1]
        if self.is_blocked(nx, ny):
            self._collision_count += 1
            return self._pos
        self._pos = (nx, ny)
        return self._pos

    def turn_left(self):
        """原地左转 90°，返回新的 Facing（不耗电）。"""
        self._facing = _TURN_LEFT[self._facing]
        return self._facing

    def turn_right(self):
        """原地右转 90°，返回新的 Facing（不耗电）。"""
        self._facing = _TURN_RIGHT[self._facing]
        return self._facing


# ---------------------------------------------------------------------------
# Q4 贪心导航（题面 Q4·单步贪心导航策略）
# ---------------------------------------------------------------------------
def next_step_toward(pos, target, obstacles, current_facing=Facing.UP):
    """返回下一步应朝向的 Facing。

    候选 = 相邻格非障碍且到目标的曼哈顿距离严格减小；多个候选时优先走
    绝对坐标差更大的轴；无候选时返回 current_facing（本函数不感知边界）。
    """
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]
    cur_dist = abs(dx) + abs(dy)
    obstacles = set(obstacles)

    candidates = []
    for f in Facing:
        nx = pos[0] + f.delta[0]
        ny = pos[1] + f.delta[1]
        if (nx, ny) in obstacles:
            continue
        if abs(nx - target[0]) + abs(ny - target[1]) < cur_dist:
            candidates.append(f)

    if not candidates:
        return current_facing

    if abs(dx) >= abs(dy):
        for f in candidates:
            if f.delta[0] != 0:
                return f
    else:
        for f in candidates:
            if f.delta[1] != 0:
                return f
    return candidates[0]


# ---------------------------------------------------------------------------
# Q5 哨兵决策机（题面 Q5·裁判系统决策规则表）
# ---------------------------------------------------------------------------
class SentryState(Enum):
    """哨兵状态机（已提供，勿改）。"""

    PATROL = "PATROL"
    SUSPECT = "SUSPECT"
    ENGAGE = "ENGAGE"
    RETREAT = "RETREAT"
    RETURN = "RETURN"


def decide(sensor, state, hp, heat):
    """纯函数决策，返回 (action: str, new_state: SentryState)。

    按 R1-R7 固定顺序求值，首条命中即返回；契约外输入（sensor 缺字段、
    enemy_frames 空或长度超 6、state 非 SentryState）抛 ValueError。
    heat 为接口保留参数，当前规则表不参与判定。
    """
    if not isinstance(sensor, dict):
        raise ValueError("sensor 必须是 dict")
    for key in ("enemy_frames", "enemy_dist", "robot_type", "max_hp"):
        if key not in sensor:
            raise ValueError("sensor 缺少字段：{}".format(key))
    if not isinstance(state, SentryState):
        raise ValueError("state 必须是 SentryState 成员")

    frames_raw = sensor["enemy_frames"]
    if not isinstance(frames_raw, (tuple, list)) or not 1 <= len(frames_raw) <= 6:
        raise ValueError("enemy_frames 须为长度 1-6 的 tuple/list")
    frames = [bool(f) for f in frames_raw]
    visible = frames[-1]

    # 敌距规范化：int（非 bool）保留，其余按 None 处理。
    dist = sensor["enemy_dist"]
    if isinstance(dist, bool) or not isinstance(dist, int):
        dist = None

    # 机型规范化：仅 "HERO" 视为英雄，其余按步兵处理。
    is_hero = sensor["robot_type"] == "HERO"

    hp_pct = hp_ratio(hp, sensor["max_hp"])

    def engage_action():
        if dist is not None and dist <= 3:
            return "SHOOT", SentryState.ENGAGE
        return ("MOVE_RIGHT" if is_hero else "MOVE_LEFT"), SentryState.ENGAGE

    # R1 保命优先
    if hp_pct <= 30:
        return "RETREAT", SentryState.RETREAT

    # R2 撤退保持（R1 已拦截 hp_pct <= 30，此处必已恢复安全血量）
    if state == SentryState.RETREAT:
        return "RETURN", SentryState.RETURN

    # R3 返航单帧
    if state == SentryState.RETURN:
        return "MOVE_BASE", SentryState.PATROL

    # R4 / R5 交火
    if state == SentryState.ENGAGE:
        if visible:
            return engage_action()
        # 短暂丢失（上一帧仍可见）→ 保持；持续丢失 → 转 SUSPECT
        if len(frames) >= 2 and frames[-2]:
            return "HOLD_FIRE", SentryState.ENGAGE
        return "SCAN", SentryState.SUSPECT

    # R6 / R7：PATROL / SUSPECT
    if visible:
        if len(frames) >= 2 and frames[-2]:
            return engage_action()
        return "SCAN", SentryState.SUSPECT
    if state == SentryState.PATROL:
        return "PATROL_MOVE", SentryState.PATROL
    return "SCAN", SentryState.SUSPECT


# ---------------------------------------------------------------------------
# Q6 巡逻任务（题面 Q6·巡逻契约与验收阈值）
# ---------------------------------------------------------------------------
def run_patrol(grid, max_steps=500):
    """贪心导航 + 沿墙脱困 的巡逻主循环，返回统计 dict。

    每轮：贪心选向（失速时切入左手规则沿墙脱困）→ 对齐朝向 → 前进一步。
    终止：到达 enemy_pos / 步数用尽 / 电量耗尽。
    """
    enemy = grid.enemy_pos
    steps = 0
    visited = {grid.current_pos}
    wall = False
    hand = "L"
    wall_steps = 0
    entry_dist = 0
    limit = grid.width + grid.height

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def has_candidate(pos):
        dist = manhattan(pos, enemy)
        for f in Facing:
            nx = pos[0] + f.delta[0]
            ny = pos[1] + f.delta[1]
            if not grid.is_blocked(nx, ny) and manhattan((nx, ny), enemy) < dist:
                return True
        return False

    rights = {Facing.UP: 0, Facing.RIGHT: 1,
              Facing.DOWN: 2, Facing.LEFT: 3}

    while steps < max_steps and grid.fuel > 0 and not grid.found_enemy:
        pos = grid.current_pos

        # 贪心失速 → 切入沿墙脱困
        if not wall and not has_candidate(pos):
            wall = True
            hand = "L"
            wall_steps = 0
            entry_dist = manhattan(pos, enemy)

        if wall:
            side = (_TURN_LEFT[grid.facing] if hand == "L"
                    else _TURN_RIGHT[grid.facing])
            opposite = (_TURN_RIGHT[grid.facing] if hand == "L"
                        else _TURN_LEFT[grid.facing])

            def cell(f):
                return (pos[0] + f.delta[0], pos[1] + f.delta[1])

            if not grid.is_blocked(*cell(side)):
                if hand == "L":
                    grid.turn_left()
                else:
                    grid.turn_right()
            elif grid.is_blocked(*cell(grid.facing)):
                if not grid.is_blocked(*cell(opposite)):
                    if hand == "L":
                        grid.turn_right()
                    else:
                        grid.turn_left()
                else:
                    grid.turn_right()
                    grid.turn_right()
        else:
            direction = next_step_toward(
                pos, enemy, grid.obstacles, grid.facing)
            diff = (rights[direction] - rights[grid.facing]) % 4
            if diff == 3:
                grid.turn_left()
            else:
                for _ in range(diff):
                    grid.turn_right()

        grid.move_forward()
        steps += 1
        visited.add(grid.current_pos)

        if wall:
            wall_steps += 1
            if wall_steps > limit and hand == "L":
                hand = "R"
                wall_steps = 0
            elif wall_steps > 2 * limit:
                wall = False
            elif (has_candidate(grid.current_pos)
                  and manhattan(grid.current_pos, enemy) < entry_dist + 1):
                wall = False

    found = grid.found_enemy
    return {"steps": steps,
            "collisions": grid.collision_count,
            "visited_count": len(visited),
            "found_enemy": found,
            "success": found}


def report_to_json(stats):
    """把 stats 序列化为确定性的 JSON 字符串（键排序保证稳定）。"""
    return json.dumps(stats, sort_keys=True)


# ---------------------------------------------------------------------------
# Bonus：BFS 全局最短路（题面 Bonus·BFS 语义与排行榜）
# ---------------------------------------------------------------------------
def bfs_path_length(start, target, obstacles):
    """BFS 全局最短路步数；start == target 返回 0，目标不可达返回 -1。

    obstacles 须由调用方包含地图边界，否则对不可达目标的搜索不会终止。
    """
    obstacles = set(obstacles)
    if start == target:
        return 0
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        cur, dist = queue.popleft()
        for f in Facing:
            nxt = (cur[0] + f.delta[0], cur[1] + f.delta[1])
            if nxt in obstacles or nxt in seen:
                continue
            if nxt == target:
                return dist + 1
            seen.add(nxt)
            queue.append((nxt, dist + 1))
    return -1


# ---------------------------------------------------------------------------
# 渲染（已提供，demo 专用，不进测试）
# ---------------------------------------------------------------------------
def render_frame(grid, trail=()):
    """ASCII 渲染一帧战场；trail 为走过的格子集合。返回 list[str]。"""
    trail = set(trail)
    rows = []
    for y in range(grid.height - 1, -1, -1):
        row = []
        for x in range(grid.width):
            if (x, y) == grid.current_pos:
                row.append("◉")
            elif (x, y) == grid.enemy_pos:
                row.append("▲")
            elif (x, y) in grid.obstacles:
                row.append("█")
            elif (x, y) in trail:
                row.append("·")
            else:
                row.append(".")
        rows.append("".join(row))
    return rows

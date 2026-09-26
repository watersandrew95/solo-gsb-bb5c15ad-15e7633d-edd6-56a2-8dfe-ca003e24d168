"""用量复核核心判定逻辑。

对每段相邻读数 (r1, r2)，真实增量为 delta = (r2 - r1) + k * modulus，
其中 k 为整圈回绕次数（非负整数）。约束条件：

    delta >= 0                          （非负增量）
    delta <= max_rate * elapsed_seconds （速率上限）

所有满足约束的 k 构成一个连续整数区间 [k_min, k_max]：

    k_min = 满足 diff + k*M >= 0 的最小非负整数
    k_max = 满足 diff + k*M <= max_delta 的最大整数

判定：
    k_max <  k_min  -> 无解 (no_solution)
    k_max == k_min  -> 唯一解，取该 k
    k_max >  k_min  -> 多解 (ambiguous)，不猜测圈数

速率上限使用 Fraction 精确计算，避免浮点边界误差。

账单总量对账（reconcile_total）：
    设账单总用量为 B，各段首尾读数差之和望远镜相消为首尾读数差：
        B = Σ delta_i = Σ diff_i + M * Σ k_i = (r_last - r_first) + M * K
    故总回绕次数 K = (B - (r_last - r_first)) / M 必须为非负整数
    （账单总量与模数不相容），且满足 Σ k_min <= K <= Σ k_max
    （超出可行总量）。固定 K 后，各段仍可行的圈数范围完全由整数区间
    运算给出，无需枚举组合：

        lo_i' = max(lo_i, K - Σ_j hi_j + hi_i)
        hi_i' = min(hi_i, K - Σ_j lo_j + lo_i)

    lo_i' == hi_i' 的段圈数唯一，可确定用量；其余段仅保留范围，不猜测。

分时单价账单金额区间（charge_amount_extremes）：
    账单总量对账可行、总回绕次数 K 固定后，各段圈数已收紧为
    k_i ∈ [lo_i, hi_i] 且 Σ k_i = K，段 i 用量 u_i = diff_i + k_i*M。
    各段分时单价 p_i 为非负有限十进制数（以「分子, 十进制小数位」精确
    给出），应收金额
        A = Σ p_i*u_i = Σ p_i*diff_i + M*Σ p_i*(k_i - lo_i)
    前一项与分配无关；剩余圈数 T = K - Σ lo_i 为非负整数（总量对账保证
    T <= Σ (hi_i - lo_i)）。线性目标下最优分配由贪心直接给出，不枚举
    圈数组合：最低金额把 T 个剩余圈按单价从低到高逐段填满余量
    （同价按段索引升序打破平局），最高金额按单价从高到低同样贪心。
    单价排序以分数交叉相乘比较，金额全程整数（分子）运算，不用浮点；
    金额按各自的 10 进制定标格式化为十进制字符串返回。

换表账单复核（reconcile_meter_total）：
    旧表、新表两段模数 M1、M2 可不同。两段用量分别为
        u1 = d1 + k1*M1, u2 = d2 + k2*M2
    （d 为段内首尾读数差），账单总量 B 要求 u1 + u2 = B，即
        M1*k1 + M2*k2 = N，N = B - d1 - d2
    该二元一次丢番图方程有整数解当且仅当 g = gcd(M1, M2) 整除 N
    （total_incompatible_modulus）。有解时由扩展欧几里得取特解
    (k10, k20)，全部整数解为单参数族：
        k1 = k10 + (M2/g)*t, k2 = k20 - (M1/g)*t   （t 为任意整数）
    两段各自的可行圈数区间 [lo_i, hi_i] 把 t 夹到连续整数区间
    [t_min, t_max]（四个 ceil/floor 不等式取交）；t_min > t_max 即账单
    超界（total_out_of_range）。全程仅整数区间运算，不枚举圈数组合。
    t_min == t_max 时两段圈数同时唯一；否则按等差数列端点给出各段用量
    上下界（每个可行 t 均严格满足 u1 + u2 = B）。

漏采读数推断（solve_missing_reading）：
    漏采时刻把账期切成左、右两段，容量分别为 floor(速率 × 各段秒数)。
    账单总量 B 须满足 B = diff + K*M（diff = 末读数 - 首读数，K >= 0）；
    同余且 B >= 0 时 K 自动非负。左侧用量 x 的可行闭区间为
    [max(0, B - C_R), min(C_L, B)]，候选读数 (首读数 + x) mod M 在模 M
    环上形成连续弧：跨零点拆段、覆盖全模数时返回全域。

最小统一速率上限（solve_minimum_rate）：
    不给定速率上限，反求「恰好能解释账单」的最小统一速率门槛 R*：
    各段用量 u_i = diff_i + k_i*M（k_i >= 0 整数）须满足 Σ u_i = B，
    且 u_i / s_i <= R*（s_i 为段历时秒数）。同余校验与总量对账一致；
    K = (B - Σdiff)/M 自动非负，额外圈数 T = K - Σk_min < 0 即账单低于
    可行最小总量 Σ base_i（total_out_of_range；速率无上限，故可行总量
    只有下界）。速率 R 可行当且仅当

        R >= max(base_i / s_i)
        且 Σ floor((R*s_i - base_i)/M) >= T

    左项计数恰为「不超过 R 的断点 (base_i + t*M)/s_i（t >= 1）」的个数，
    故 R* = max( max_i base_i/s_i, 第 T 小的断点值 )。第 T 小断点以精确
    二分求得：任意两个不同断点之差 >= 1/s_max²，二分（Fraction 中点、
    整数计数）至区间宽度小于该精度后，(lo, hi] 内恰剩一个断点值，取
    各段「严格大于 lo 的最小断点」的最小值即得。全程 Fraction/整数
    运算，无浮点近似，也不枚举圈数组合。固定 R* 后各段可行圈数范围
    由与总量对账相同的整数区间收紧公式给出。

双表同段交叉核验（compare_dual_meter）：
    两块表在同一时段（起止时刻分别相同）计量同一真实用量 u：
        u = d1 + k1*M1 = d2 + k2*M2   （d 为段内读数差，k 为非负整圈数）
    同余联立 u ≡ d1 (mod M1)、u ≡ d2 (mod M2)：由中国剩余定理，相容
    当且仅当 d1 ≡ d2 (mod g)，g = gcd(M1, M2)（否则 incompatible_modulus）；
    相容时全部共同用量为单一同余类 u ≡ u0 (mod L)，L = lcm(M1, M2)，
    u0 由扩展欧几里得直接构造。各表可行用量闭区间
    [d_i + lo_i*M_i, d_i + hi_i*M_i] 求交得 [lo, hi]，共同候选即该
    同余类落在交集中的项：
        u_min = u0 + L*ceil((lo - u0)/L)
        u_max = u0 + L*floor((hi - u0)/L)
    u_min > u_max 即范围无交集（range_disjoint，含区间本身不交与交集内
    无同余点两种情形），与同余不相容是不同的冲突原因。候选为等差数列
    u_min, u_min + L, ..., u_max，候选数 (u_max - u_min)/L + 1 由端点
    直接算得，全程整数区间与同余运算，不逐个枚举回绕圈数。

停水时段账单复核（solve_outage_segment）：
    若干左闭右开的停水时段先统一裁剪到读数账期 [t_first, t_last)，
    再合并重叠或相接（端点相同）的时段。对每个相邻读数区间，从
    [t_i, t_{i+1}) 中扣除落在其内的停水时段，剩余的连续供水片段
    [s, e) 各自独立取整，容量 c = floor(速率 × (e - s))，该段整数
    用量容量 C = Σ c——各片段分别 floor 后求和，不能跨停水时段合并
    取整（Σ floor(速率×s_j) <= floor(速率×Σs_j)，停水会损失取整余量）。
    与跨日子段同理，非负整数增量 delta = diff + k*M 可分配到各供水
    片段当且仅当 delta <= C，故可行圈数仍为连续整数区间
        k_min = ceil(max(0, -diff) / M)
        k_max = floor((C - diff) / M)
    k_max < k_min 即单段无解。各段均可行后，账单总用量联立直接复用
    reconcile_total 的整数区间收紧（同余冲突 / 总量超界原因也一致）。

异常采样清理（clean_readings）：
    任意两条读数 (v_i, t_i)、(v_j, t_j)（i < j）可相邻保留，当且仅当
    把它们视为一段相邻读数时物理可行（solve_segment 同一判定：存在
    k >= 0 使 diff + k*M 非负且不超速率上限）。保留序列首尾必须为索引
    0 与 n-1，删除最少 ⟺ 保留最多 ⟺ 有向无环图（边只从低索引指向高
    索引）上 0 -> n-1 的最长路径，按拓扑序一遍 DP 求首到各点最多边数
    dist、逆序一遍求各点到末点最多边数 tail；D = dist[n-1]，不可达即
    无解。最优路径不唯一时按保留索引序列字典序选定：从首读数出发，每
    步取满足 dist[q] = dist[cur]+1 且 dist[q]+tail[q] = D 的最小后继
    q（最长路上的点必有这样的最优后继），归纳得到字典序最小的完整序
    列。逐对判定与 DP 均为 O(n²)，不枚举保留子序列。

总分表漏损复核（reconcile_master_sub_loss）：
    同一模数 M 的一块总表与至少一块分表共用同一组严格递增时刻，各表
    在每段的真实用量 u_{m,i} = d_{m,i} + k_{m,i}*M（k 为非负整圈数）。
    逐表复用 solve_segment 求出每段可行圈数区间（单表单段无解即
    no_solution）。第 i 段漏损
        l_i = u_{主,i} - Σ_m u_{分,m,i} = D_i + w_i*M
    其中 D_i = d_{主,i} - Σ d_{分,i}，w_i = k_{主,i} - Σ k_{分,m,i}
    为该段总表与分表圈数之差（可正可负，不必非负）。非负漏损要求
    w_i >= ceil(-D_i / M)，与各表圈数区间的连续差值区间
    [Σk_min 差, Σk_max 差] 求交；交集为空即该段漏损无法非负
    （loss_segment_negative）。整期漏损总量 L 要求
        L = Σ l_i = Σ D_i + M * Σ w_i
    L - ΣD_i 不被 M 整除即总量同余冲突（total_incompatible_modulus）；
    固定 W = (L - ΣD_i)/M 后，各段 w_i 独立取各自连续整数区间且
    Σ w_i = W，与 reconcile_total 完全相同的整数区间收紧公式（此处
    w_i 允许负值）；Σlo <= W <= Σhi 不成立即总量超界
    （total_out_of_range）。收紧后 lo_i == hi_i 的段漏损唯一、给出
    确定值，其余段只给漏损上下界（端点均可达到，交叉端点相等），不
    枚举任何回绕组合。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from fractions import Fraction
from typing import Optional, Sequence, Tuple

STATUS_OK = "ok"
STATUS_NO_SOLUTION = "no_solution"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_CONFLICT = "conflict"

# 账单总量对账冲突原因
REASON_TOTAL_INCOMPATIBLE_MODULUS = "total_incompatible_modulus"
REASON_TOTAL_OUT_OF_RANGE = "total_out_of_range"
# 跨日分配冲突原因：不存在可行的子段整数分配
REASON_NO_FEASIBLE_ALLOCATION = "no_feasible_allocation"
# 漏采读数推断冲突原因：漏采时刻两侧容量之和小于账单总量
REASON_INSUFFICIENT_CAPACITY = "insufficient_capacity"
# 双表同段交叉核验冲突原因
# 两表读数差模 gcd(两模数) 不同余，不存在共同用量
REASON_INCOMPATIBLE_MODULUS = "incompatible_modulus"
# 同余相容但两表可行用量范围之交内没有共同候选
REASON_RANGE_DISJOINT = "range_disjoint"
# 总分表漏损复核冲突原因：某段总表用量恒小于各分表用量之和，漏损无法非负
REASON_LOSS_SEGMENT_NEGATIVE = "loss_segment_negative"


@dataclass(frozen=True)
class SegmentSolution:
    """单个相邻读数区间的判定结果。"""

    index: int
    status: str
    elapsed_seconds: int
    # 唯一解时填充
    wraps: Optional[int]
    usage: Optional[int]
    # 可行回绕次数区间 [min_wraps, max_wraps]；无解时 max_wraps < min_wraps
    min_wraps: int
    max_wraps: int
    max_allowed: Fraction  # 该区间允许的最大增量（速率上限 * 秒数）


def solve_segment(
    index: int,
    start_value: int,
    end_value: int,
    elapsed_seconds: int,
    modulus: int,
    max_rate_per_second: Fraction,
) -> SegmentSolution:
    """判定一段相邻读数的回绕次数是否唯一。"""
    diff = end_value - start_value
    max_allowed = max_rate_per_second * elapsed_seconds

    # k_min: diff + k*M >= 0 的最小非负整数 k
    if diff >= 0:
        k_min = 0
    else:
        # ceil(-diff / M)，此时 0 < -diff < M，结果恒为 1
        k_min = (-diff + modulus - 1) // modulus

    # k_max: diff + k*M <= max_allowed 的最大整数 k
    k_max = math.floor((max_allowed - diff) / modulus)

    if k_max < k_min:
        status, wraps, usage = STATUS_NO_SOLUTION, None, None
    elif k_max == k_min:
        status, wraps = STATUS_OK, k_min
        usage = diff + k_min * modulus
    else:
        status, wraps, usage = STATUS_AMBIGUOUS, None, None

    return SegmentSolution(
        index=index,
        status=status,
        elapsed_seconds=elapsed_seconds,
        wraps=wraps,
        usage=usage,
        min_wraps=k_min,
        max_wraps=k_max,
        max_allowed=max_allowed,
    )


@dataclass(frozen=True)
class NarrowedSegment:
    """账单总量约束后，单段仍可行的回绕次数整数区间。"""

    index: int
    diff: int
    min_wraps: int
    max_wraps: int

    @property
    def unique(self) -> bool:
        """圈数是否已被总量约束唯一确定。"""
        return self.min_wraps == self.max_wraps

    @property
    def wraps(self) -> Optional[int]:
        return self.min_wraps if self.unique else None

    def usage(self, modulus: int) -> Optional[int]:
        """圈数唯一时该段确定用量，否则为 None。"""
        return self.diff + self.min_wraps * modulus if self.unique else None

    def usage_bounds(self, modulus: int) -> Tuple[int, int]:
        """该区间用量的最小/最大可能值。"""
        return (
            self.diff + self.min_wraps * modulus,
            self.diff + self.max_wraps * modulus,
        )


@dataclass(frozen=True)
class ReconcileResult:
    """账单总量对账结果。"""

    status: str  # STATUS_OK 或 STATUS_CONFLICT
    total_wraps: Optional[int]  # 总量隐含的总回绕次数 K（不相容时为 None）
    narrowed: Tuple[NarrowedSegment, ...]
    conflicts: Tuple[str, ...]  # REASON_TOTAL_* 原因
    feasible_min_total: int
    feasible_max_total: int


def reconcile_total(
    diffs: Sequence[int],
    wrap_bounds: Sequence[Tuple[int, int]],
    total_usage: int,
    modulus: int,
) -> ReconcileResult:
    """以账单总用量约束整条读数序列的回绕次数总和。

    :param diffs: 各段首尾读数差 r2 - r1
    :param wrap_bounds: 各段在非负增量与速率上限下的可行圈数区间
        ``(k_min, k_max)``，调用方需保证每段均可行（k_max >= k_min）
    :param total_usage: 账单总用量（非负整数）
    :param modulus: 计数器模数
    :return: 对账结果；可行时 ``narrowed`` 给出各段收紧后的圈数区间
    """
    if len(diffs) != len(wrap_bounds):
        raise ValueError("diffs 与 wrap_bounds 数量必须一致")

    lows = [lo for lo, _ in wrap_bounds]
    highs = [hi for _, hi in wrap_bounds]
    sum_low, sum_high = sum(lows), sum(highs)
    end_minus_start = sum(diffs)  # 望远镜相消：末读数 - 首读数

    feasible_min_total = end_minus_start + modulus * sum_low
    feasible_max_total = end_minus_start + modulus * sum_high

    numerator = total_usage - end_minus_start
    conflicts = []
    # 总量必须与首尾读数差模 M 同余（等价于总回绕次数为非负整数）
    if numerator % modulus != 0:
        conflicts.append(REASON_TOTAL_INCOMPATIBLE_MODULUS)
        total_wraps: Optional[int] = None
    else:
        total_wraps = numerator // modulus
        if not (sum_low <= total_wraps <= sum_high):
            conflicts.append(REASON_TOTAL_OUT_OF_RANGE)

    if conflicts:
        return ReconcileResult(
            status=STATUS_CONFLICT,
            total_wraps=total_wraps,
            narrowed=(),
            conflicts=tuple(conflicts),
            feasible_min_total=feasible_min_total,
            feasible_max_total=feasible_max_total,
        )

    # K 固定：其余各段圈数之和为 K - k_i，由其余段的区间和反推出 k_i 的范围
    narrowed = []
    for i, (lo, hi) in enumerate(wrap_bounds):
        other_high = sum_high - hi  # 除 i 外各段最大圈数之和
        other_low = sum_low - lo  # 除 i 外各段最小圈数之和
        new_lo = max(lo, total_wraps - other_high)
        new_hi = min(hi, total_wraps - other_low)
        narrowed.append(
            NarrowedSegment(
                index=i,
                diff=diffs[i],
                min_wraps=new_lo,
                max_wraps=new_hi,
            )
        )

    return ReconcileResult(
        status=STATUS_OK,
        total_wraps=total_wraps,
        narrowed=tuple(narrowed),
        conflicts=(),
        feasible_min_total=feasible_min_total,
        feasible_max_total=feasible_max_total,
    )


# ---------------------------------------------------------------------------
# 分时单价账单金额区间（charge-range）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChargeSegmentAllocation:
    """金额极值方案中单个相邻读数段的圈数、用量与该段金额（金额分子）。"""

    index: int
    wraps: int  # 该极值方案分配给本段的回绕圈数
    usage: int  # 本段用量 diff + wraps*modulus
    amount_numerator: int  # 本段金额的十进制分子（金额 = numerator / 10**scale）
    amount_scale: int  # 本段金额的十进制小数位（由该段单价定标）


@dataclass(frozen=True)
class ChargeExtreme:
    """账单金额的一个极值（最低或最高）及其分段用量方案。"""

    total_numerator: int  # 总金额十进制分子
    total_scale: int  # 总金额十进制小数位（取各段单价小数位的最大值）
    allocations: Tuple[ChargeSegmentAllocation, ...]  # 按段索引升序


def format_decimal_string(numerator: int, scale: int) -> str:
    """把非负十进制有理数 ``numerator / 10**scale`` 格式化为十进制字符串。

    仅用于非负金额：``numerator >= 0``、``scale >= 0``。整数部分每三位
    **不**加分隔符；``scale > 0`` 时保留恰好 ``scale`` 位小数（末尾的 0
    不去除，保证该定标下的精确表示）。
    """
    if numerator < 0 or scale < 0:
        raise ValueError("format_decimal_string 仅支持非负金额且 scale >= 0")
    if scale == 0:
        return str(numerator)
    digits = str(numerator).zfill(scale + 1)
    return f"{digits[:-scale]}.{digits[-scale:]}"


def charge_amount_extremes(
    diffs: Sequence[int],
    wrap_bounds: Sequence[Tuple[int, int]],
    total_wraps: int,
    modulus: int,
    prices: Sequence[Tuple[int, int]],
) -> Tuple[ChargeExtreme, ChargeExtreme]:
    """固定总回绕次数下精确求最低/最高应收金额及各自的分段用量方案。

    调用前需已通过账单总量对账：各段圈数区间为总量约束收紧后的
    ``[lo_i, hi_i]``（``reconcile_total`` 的 ``narrowed``），满足
    ``Σ lo_i <= total_wraps <= Σ hi_i`` 且 ``Σ k_i = total_wraps``。
    第 ``i`` 段用量为 ``u_i = diff_i + k_i*modulus``，分时单价
    ``p_i = num_i / 10**scale_i``（非负有限十进制数）。

    应收金额

        A = Σ p_i*u_i = Σ p_i*diff_i + M*Σ p_i*(k_i - lo_i)

    第一项与圈数分配无关；记剩余圈数 ``T = K - Σ lo_i``（非负整数，且
    ``T <= Σ (hi_i - lo_i)``）。线性目标下最优由贪心给出，不枚举圈数
    组合：

    - 最低金额：段按单价从低到高（分数交叉相乘比较，同价按段索引升序）
      排序，依次把该段余量 ``hi_i - lo_i`` 填满直至用完 ``T`` 个圈；
    - 最高金额：段按单价从高到低排序（同价仍按段索引升序），同样贪心。

    金额一律按十进制分子做整数运算（单价交叉相乘比较，无浮点）；各段
    金额以该段单价定标格式化为十进制字符串，总金额取各段小数位最大值
    统一对齐后求和。

    :param prices: 与各段一一对应的单价 ``(分子, 小数位)``，分子须非负
    :return: ``(最低金额方案, 最高金额方案)``，方案内分段按索引升序
    """
    if not (len(diffs) == len(wrap_bounds) == len(prices)):
        raise ValueError("diffs、wrap_bounds 与 prices 数量必须一致")
    if not diffs:
        raise ValueError("至少需要一段读数区间")
    for num, scale in prices:
        if num < 0 or scale < 0:
            raise ValueError("单价分子与小数位均须非负")

    lows = [lo for lo, _ in wrap_bounds]
    highs = [hi for _, hi in wrap_bounds]
    total_scale = max(scale for _, scale in prices)
    extra = total_wraps - sum(lows)
    if extra < 0:
        raise ValueError("total_wraps 低于各段圈数下界之和（应先通过总量对账）")

    def _solve(descending_price: bool) -> ChargeExtreme:
        # 单价为 num_i/10**scale_i：以 Fraction 精确排序（交叉相乘），
        # 同价时按段索引升序打破平局，保证方案确定
        order = sorted(
            range(len(diffs)),
            key=lambda i: (
                -Fraction(prices[i][0], 10 ** prices[i][1])
                if descending_price
                else Fraction(prices[i][0], 10 ** prices[i][1]),
                i,
            ),
        )
        wraps = list(lows)
        remaining = extra
        for i in order:
            if remaining == 0:
                break
            take = min(remaining, highs[i] - lows[i])
            wraps[i] += take
            remaining -= take
        if remaining != 0:
            raise ValueError("剩余圈数超出各段余量之和（应先通过总量对账）")

        allocations = []
        total_num = 0
        for i, (num_i, scale_i) in enumerate(prices):
            usage = diffs[i] + wraps[i] * modulus
            amount_num = num_i * usage
            allocations.append(
                ChargeSegmentAllocation(
                    index=i,
                    wraps=wraps[i],
                    usage=usage,
                    amount_numerator=amount_num,
                    amount_scale=scale_i,
                )
            )
            # 统一对齐到最大小数位后累加（整数运算，无浮点）
            total_num += amount_num * 10 ** (total_scale - scale_i)
        allocations.sort(key=lambda a: a.index)
        return ChargeExtreme(
            total_numerator=total_num,
            total_scale=total_scale,
            allocations=tuple(allocations),
        )

    return _solve(descending_price=False), _solve(descending_price=True)


# ---------------------------------------------------------------------------
# 跨日用量上下界（daily-range）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DaySubsegment:
    """读数区间按 UTC 午夜切出的一个子段（完全落在单个 UTC 自然日内）。"""

    day: date
    seconds: int
    capacity: int  # floor(max_rate_per_second * seconds)


@dataclass(frozen=True)
class DailySegmentResult:
    """一个读数区间跨日切分后的可行分配结果。"""

    index: int
    feasible: bool
    # 该区间可行的回绕次数范围；无解时 max_wraps < min_wraps
    min_wraps: int
    max_wraps: int
    subsegments: Tuple[DaySubsegment, ...]
    # 每个子段的精确边际上下界（与 subsegments 一一对应）；无解时为空
    min_usages: Tuple[int, ...]
    max_usages: Tuple[int, ...]

    @property
    def total_capacity(self) -> int:
        return sum(s.capacity for s in self.subsegments)


def split_utc_days(start: datetime, end: datetime) -> Tuple[Tuple[date, int], ...]:
    """将 [start, end) 按 UTC 午夜切成 ``(UTC 日期, 该日子段秒数)`` 序列。

    端点均为秒精度、带时区的严格递增时间戳。子段在交界处首尾相接
    （零长度子段被丢弃），秒数之和恰为区间总时长。
    """
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    pieces = []
    cursor = start
    while cursor < end:
        next_midnight = datetime.combine(
            cursor.date() + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
        boundary = min(end, next_midnight)
        seconds = int((boundary - cursor).total_seconds())
        if seconds > 0:
            pieces.append((cursor.date(), seconds))
        cursor = boundary
    return tuple(pieces)


def solve_daily_segment(
    index: int,
    start_value: int,
    end_value: int,
    start: datetime,
    end: datetime,
    modulus: int,
    max_rate_per_second: Fraction,
) -> DailySegmentResult:
    """求单个读数区间跨各 UTC 日子段用量的精确边际上下界。

    区间真实增量为 ``delta = diff + k*M``（diff = r2 - r1，k >= 0 整数），
    切日子段容量为 ``c_j = floor(rate * s_j)``。需存在非负整数分配
    ``(x_1, ..., x_n)`` 满足 ``0 <= x_j <= c_j`` 且 ``Σ x_j = delta``。

    该类分配存在当且仅当 ``delta <= C``（``C = Σ c_j``）：因为所有容量为
    整数，``[0, C]`` 内任意整数总量都可逐子段填满。故可行 k 仍为连续
    整数区间 ``[k_min, k_max]``，其中

        k_min = ceil(max(0, -diff) / M)
        k_max = floor((C - diff) / M)

    对固定子段 j，给定可行 k 时其边际范围为

        max(0, delta - (C - c_j)) <= x_j <= min(c_j, delta)

    下界随 delta 单调增，故全区间最小值在 k_min 处取得；上界随 delta
    单调增，最大值在 k_max 处取得。两端点均确实可由完整分配达到
    （箱型可行域与固定总量超平面之交的逐分量极值）。
    """
    diff = end_value - start_value

    subsegments = tuple(
        DaySubsegment(
            day=day,
            seconds=seconds,
            # Fraction 精确取整，避免浮点边界误差
            capacity=math.floor(max_rate_per_second * seconds),
        )
        for day, seconds in split_utc_days(start, end)
    )
    total_capacity = sum(s.capacity for s in subsegments)

    k_min = 0 if diff >= 0 else (-diff + modulus - 1) // modulus
    k_max = (total_capacity - diff) // modulus

    if k_max < k_min:
        return DailySegmentResult(
            index=index,
            feasible=False,
            min_wraps=k_min,
            max_wraps=k_max,
            subsegments=subsegments,
            min_usages=(),
            max_usages=(),
        )

    delta_min = diff + k_min * modulus
    delta_max = diff + k_max * modulus

    min_usages, max_usages = [], []
    for s in subsegments:
        other_capacity = total_capacity - s.capacity
        # x_j >= delta - 其余子段容量之和；delta 取最小时下界最小
        low = max(0, delta_min - other_capacity)
        # x_j <= delta（且不超本段子容量）；delta 取最大时上界最大
        high = min(s.capacity, delta_max)
        min_usages.append(low)
        max_usages.append(high)

    return DailySegmentResult(
        index=index,
        feasible=True,
        min_wraps=k_min,
        max_wraps=k_max,
        subsegments=subsegments,
        min_usages=tuple(min_usages),
        max_usages=tuple(max_usages),
    )


# ---------------------------------------------------------------------------
# 停水时段账单复核（outage-reconcile）：裁剪/合并停水时段，逐段供水片段取整
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WaterSupplyFragment:
    """读数区间扣除停水时段后剩余的一个连续供水片段 [start, end)。"""

    start: datetime
    end: datetime
    seconds: int
    capacity: int  # floor(max_rate_per_second * seconds)


@dataclass(frozen=True)
class OutageSegmentResult:
    """单个读数区间扣除停水时段后的可行回绕次数判定。"""

    index: int
    feasible: bool
    # 该区间可行的回绕次数范围；无解时 max_wraps < min_wraps
    min_wraps: int
    max_wraps: int
    fragments: Tuple[WaterSupplyFragment, ...]
    elapsed_seconds: int  # 区间总时长（含停水）
    outage_seconds: int  # 落在该区间内的停水秒数
    supply_seconds: int  # 扣除停水后的供水秒数

    @property
    def total_capacity(self) -> int:
        """各供水片段分别 floor(速率×秒数) 后的容量之和。"""
        return sum(f.capacity for f in self.fragments)


def clip_merge_intervals(
    intervals: Sequence[Tuple[datetime, datetime]],
    period_start: datetime,
    period_end: datetime,
) -> Tuple[Tuple[datetime, datetime], ...]:
    """把左闭右开时段裁剪到 ``[period_start, period_end)`` 并合并重叠/相接时段。

    相接（前一段右端点 == 后一段左端点）也合并为一个连续区间；完全落在
    账期外或裁剪后为空（零时长）的时段被丢弃。合并以 UTC 归一化后的
    时刻比较，输入时间戳由调用方保证为秒精度带时区。
    """
    period_start = period_start.astimezone(timezone.utc)
    period_end = period_end.astimezone(timezone.utc)

    clipped = []
    for raw_start, raw_end in intervals:
        s = max(raw_start.astimezone(timezone.utc), period_start)
        e = min(raw_end.astimezone(timezone.utc), period_end)
        if s < e:  # 左闭右开：等长为空，丢弃
            clipped.append((s, e))
    clipped.sort()

    merged: list = []
    for s, e in clipped:
        if merged and s <= merged[-1][1]:  # 重叠或相接（端点相同）即合并
            if e > merged[-1][1]:
                merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return tuple(merged)


def solve_outage_segment(
    index: int,
    start_value: int,
    end_value: int,
    start: datetime,
    end: datetime,
    modulus: int,
    max_rate_per_second: Fraction,
    merged_outages: Sequence[Tuple[datetime, datetime]],
) -> OutageSegmentResult:
    """求单个读数区间扣除停水时段后的供水片段与可行回绕次数区间。

    区间 ``[start, end)`` 与已裁剪合并到账期的停水时段（左闭右开、互不
    重叠、按起点升序）逐个求交，从区间中扣除交集，得到若干连续供水片段；
    每片段独立按 ``floor(速率 × 秒数)`` 取整，容量之和 ``C`` 即该段整数
    用量容量（不跨停水时段合并取整）。非负整数增量
    ``delta = diff + k*M`` 能分配到各供水片段当且仅当 ``delta <= C``，
    故可行圈数为 ``[k_min, k_max]``（与跨日子段同一论证），``k_max <
    k_min`` 即单段无解。
    """
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    fragments: list = []
    cursor = start_utc
    outage_seconds = 0
    for o_start, o_end in merged_outages:
        # 与本区间无交集的停水跳过（区间已升序；o_end == cursor 为相接，
        # 交集为空，不应重复扣减）
        if o_end <= cursor:
            continue
        if o_start >= end_utc:
            break
        cut_start = max(o_start, cursor)
        cut_end = min(o_end, end_utc)
        if cut_start < cut_end:
            outage_seconds += int((cut_end - cut_start).total_seconds())
            if cursor < cut_start:
                fragments.append(
                    _make_fragment(cursor, cut_start, max_rate_per_second)
                )
            cursor = cut_end
    if cursor < end_utc:
        fragments.append(_make_fragment(cursor, end_utc, max_rate_per_second))

    elapsed = int((end_utc - start_utc).total_seconds())
    supply_seconds = elapsed - outage_seconds
    total_capacity = sum(f.capacity for f in fragments)

    diff = end_value - start_value
    k_min = 0 if diff >= 0 else (-diff + modulus - 1) // modulus
    k_max = (total_capacity - diff) // modulus

    return OutageSegmentResult(
        index=index,
        feasible=k_max >= k_min,
        min_wraps=k_min,
        max_wraps=k_max,
        fragments=tuple(fragments),
        elapsed_seconds=elapsed,
        outage_seconds=outage_seconds,
        supply_seconds=supply_seconds,
    )


def _make_fragment(
    start: datetime, end: datetime, max_rate_per_second: Fraction
) -> WaterSupplyFragment:
    """构造一个供水片段，秒数与 ``floor(速率×秒数)`` 容量一并算好。"""
    seconds = int((end - start).total_seconds())
    return WaterSupplyFragment(
        start=start,
        end=end,
        seconds=seconds,
        capacity=math.floor(max_rate_per_second * seconds),
    )


# ---------------------------------------------------------------------------
# 换表账单复核（meter-change）：跨两表、模数可不同
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeterSegmentNarrowed:
    """换表账单总量约束后，一段（旧表或新表）仍可行的圈数区间。"""

    meter: str  # "old" 或 "new"
    diff: int
    modulus: int
    min_wraps: int
    max_wraps: int
    wraps_step: int  # 可行圈数序列的公差（恒正）

    @property
    def unique(self) -> bool:
        """该段圈数是否已被账单总量唯一确定。"""
        return self.min_wraps == self.max_wraps

    @property
    def wraps(self) -> Optional[int]:
        return self.min_wraps if self.unique else None

    def usage_bounds(self) -> Tuple[int, int]:
        """该段用量的最小/最大可能值（端点均可达到）。"""
        return (
            self.diff + self.min_wraps * self.modulus,
            self.diff + self.max_wraps * self.modulus,
        )


@dataclass(frozen=True)
class MeterReconcileResult:
    """跨两表账单总量对账结果。"""

    status: str  # STATUS_OK 或 STATUS_CONFLICT
    conflicts: Tuple[str, ...]  # REASON_TOTAL_* 原因
    gcd: int  # gcd(旧表模数, 新表模数)
    old_segment: Optional[MeterSegmentNarrowed]
    new_segment: Optional[MeterSegmentNarrowed]
    feasible_min_total: int
    feasible_max_total: int


def _extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
    """扩展欧几里得算法：返回 ``(g, x, y)`` 使 ``a*x + b*y = g = gcd(a, b)``。"""
    if b == 0:
        return a, 1, 0
    g, x1, y1 = _extended_gcd(b, a % b)
    return g, y1, x1 - (a // b) * y1


def _ceil_div(a: int, b: int) -> int:
    """b > 0 时的精确 ceil(a / b)，a 可为负（不依赖浮点）。"""
    return -((-a) // b)


def reconcile_meter_total(
    old_diff: int,
    old_bounds: Tuple[int, int],
    old_modulus: int,
    new_diff: int,
    new_bounds: Tuple[int, int],
    new_modulus: int,
    total_usage: int,
) -> MeterReconcileResult:
    """以跨两表的账单总用量精确联立两段回绕次数，模数可不同，不枚举圈数组合。

    旧表段用量 ``u1 = d1 + k1*M1``，新表段用量 ``u2 = d2 + k2*M2``
    （``d`` 为段内读数差，``k`` 为非负整圈数）。账单要求：

        u1 + u2 = B
        => M1*k1 + M2*k2 = N，其中 N = B - d1 - d2

    该线性丢番图方程：

    1. 有整数解当且仅当 ``g = gcd(M1, M2)`` 整除 ``N``；否则账单与两表
       模数不相容（``total_incompatible_modulus``）；
    2. 有整数解时，由扩展欧几里得给出一组特解 ``(k10, k20)``，全部解为
       单参数整数族 ``k1 = k10 + p*t``、``k2 = k20 - q*t``
       （``p = M2/g``，``q = M1/g``）。两段各自的圈数区间
       ``[lo, hi]`` 把 ``t`` 夹到一个连续整数区间 ``[t_min, t_max]``：

           t >= ceil((lo1 - k10) / p)，t <= floor((hi1 - k10) / p)
           t >= ceil((k20 - hi2) / q)，t <= floor((k20 - lo2) / q)

       ``t_min > t_max`` 即账单总量超界（``total_out_of_range``）。
    3. ``t_min == t_max`` 时两段圈数同时唯一；否则各段可行圈数仍为
       等差数列（公差分别为 ``p``、``q``），据端点给出精确用量上下界，
       不猜测。注意每一个可行 ``t`` 都严格满足 ``u1 + u2 == B``。

    :param old_bounds/new_bounds: 各段在非负增量与速率上限下的可行圈数
        区间 ``(k_min, k_max)``，调用方需保证每段均可行
    """
    lo1, hi1 = old_bounds
    lo2, hi2 = new_bounds

    feasible_min_total = (
        old_diff + lo1 * old_modulus + new_diff + lo2 * new_modulus
    )
    feasible_max_total = (
        old_diff + hi1 * old_modulus + new_diff + hi2 * new_modulus
    )

    g, c1, c2 = _extended_gcd(old_modulus, new_modulus)
    numerator = total_usage - old_diff - new_diff

    if numerator % g != 0:
        return MeterReconcileResult(
            status=STATUS_CONFLICT,
            conflicts=(REASON_TOTAL_INCOMPATIBLE_MODULUS,),
            gcd=g,
            old_segment=None,
            new_segment=None,
            feasible_min_total=feasible_min_total,
            feasible_max_total=feasible_max_total,
        )

    # 特解：M1*k10 + M2*k20 = numerator
    n = numerator // g
    k10 = n * c1
    k20 = n * c2
    p = new_modulus // g  # k1 随 t 的步长
    q = old_modulus // g  # k2 随 t 的步长（方向相反）

    # k1 = k10 + p*t ∈ [lo1, hi1]
    t_lo = _ceil_div(lo1 - k10, p)
    t_hi = (hi1 - k10) // p
    # k2 = k20 - q*t ∈ [lo2, hi2]
    t_lo = max(t_lo, _ceil_div(k20 - hi2, q))
    t_hi = min(t_hi, (k20 - lo2) // q)

    if t_lo > t_hi:
        return MeterReconcileResult(
            status=STATUS_CONFLICT,
            conflicts=(REASON_TOTAL_OUT_OF_RANGE,),
            gcd=g,
            old_segment=None,
            new_segment=None,
            feasible_min_total=feasible_min_total,
            feasible_max_total=feasible_max_total,
        )

    k1_min = k10 + p * t_lo
    k1_max = k10 + p * t_hi
    k2_min = k20 - q * t_hi  # k2 随 t 递减：最小在 t_hi
    k2_max = k20 - q * t_lo

    return MeterReconcileResult(
        status=STATUS_OK,
        conflicts=(),
        gcd=g,
        old_segment=MeterSegmentNarrowed(
            meter="old",
            diff=old_diff,
            modulus=old_modulus,
            min_wraps=k1_min,
            max_wraps=k1_max,
            wraps_step=p,
        ),
        new_segment=MeterSegmentNarrowed(
            meter="new",
            diff=new_diff,
            modulus=new_modulus,
            min_wraps=k2_min,
            max_wraps=k2_max,
            wraps_step=q,
        ),
        feasible_min_total=feasible_min_total,
        feasible_max_total=feasible_max_total,
    )


# ---------------------------------------------------------------------------
# 漏采读数推断（missing-reading）：账单总量 + 漏采时刻两侧容量约束候选读数
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissingReadingResult:
    """漏采读数推断结果。"""

    status: str  # STATUS_OK 或 STATUS_CONFLICT
    conflicts: Tuple[str, ...]  # REASON_TOTAL_INCOMPATIBLE_MODULUS / REASON_INSUFFICIENT_CAPACITY
    diff: int  # 末读数 - 首读数
    total_wraps: Optional[int]  # 账单隐含的总回绕次数 K；不相容时为 None
    left_capacity: int  # floor(速率 × 漏采时刻左侧秒数)
    right_capacity: int  # floor(速率 × 漏采时刻右侧秒数)
    # 左侧可行用量闭区间 [left_usage_min, left_usage_max]；冲突时为 None
    left_usage_min: Optional[int]
    left_usage_max: Optional[int]
    # 候选读数闭区间（精确、不重叠，按左侧用量递增的环序）；冲突时为空
    intervals: Tuple[Tuple[int, int], ...]
    candidate_count: int  # 候选读数个数（去重后的剩余类数）；冲突时为 0

    @property
    def unique(self) -> bool:
        """候选读数是否唯一。"""
        return self.candidate_count == 1


def solve_missing_reading(
    start_value: int,
    end_value: int,
    left_seconds: int,
    right_seconds: int,
    modulus: int,
    max_rate_per_second: Fraction,
    total_usage: int,
) -> MissingReadingResult:
    """由账单总量与漏采时刻两侧容量推断漏采读数的候选闭区间。

    漏采时刻把账期切成左（``left_seconds`` 秒）、右（``right_seconds``
    秒）两段，整数容量分别为 ``C_L = floor(速率 × 左秒数)``、
    ``C_R = floor(速率 × 右秒数)``。账单总量 ``B`` 须满足
    ``B = diff + K*M``（``diff = 末读数 - 首读数``，``K >= 0`` 为总回绕
    次数）：

    1. ``B - diff`` 不被 ``M`` 整除即账单与模数不相容
       （``total_incompatible_modulus``）；同余且 ``B >= 0`` 时
       ``K = (B - diff) / M`` 自动满足非负性（``K >= K_min``），无需
       另行校验；
    2. 左侧用量 ``x`` 与右侧用量 ``B - x`` 须分别落在 ``[0, C_L]``、
       ``[0, C_R]`` 内，故左侧可行用量闭区间为

           [max(0, B - C_R), min(C_L, B)]

       为空（即 ``B > C_L + C_R``）时两侧容量不足
       （``insufficient_capacity``）。容量均为整数，区间内每个整数
       ``x`` 都可由某个左右侧分配达到。

    候选漏采读数为 ``(首读数 + x) mod M``。``x`` 取遍上述连续整数区间
    时，候选在模 ``M`` 环上形成连续弧：弧上点数不少于 ``M`` 时覆盖全部
    剩余类，返回全域 ``[0, M-1]``；否则自 ``(首读数 + x_min) mod M`` 起
    展开，跨越零点时拆为 ``[a, M-1]`` 与 ``[0, b]`` 两段，保证各闭区间
    精确、互不重叠且均落在 ``[0, M-1]`` 内。
    """
    diff = end_value - start_value
    left_capacity = math.floor(max_rate_per_second * left_seconds)
    right_capacity = math.floor(max_rate_per_second * right_seconds)

    def _conflict(reason: str, total_wraps: Optional[int]) -> MissingReadingResult:
        return MissingReadingResult(
            status=STATUS_CONFLICT,
            conflicts=(reason,),
            diff=diff,
            total_wraps=total_wraps,
            left_capacity=left_capacity,
            right_capacity=right_capacity,
            left_usage_min=None,
            left_usage_max=None,
            intervals=(),
            candidate_count=0,
        )

    # 账单总量与首尾读数差必须模 M 同余（等价于总回绕次数为整数）
    if (total_usage - diff) % modulus != 0:
        return _conflict(REASON_TOTAL_INCOMPATIBLE_MODULUS, None)

    total_wraps = (total_usage - diff) // modulus
    # 两侧容量之和容纳不下账单总量：无可行的左右侧整数分配
    if total_usage > left_capacity + right_capacity:
        return _conflict(REASON_INSUFFICIENT_CAPACITY, total_wraps)

    x_lo = max(0, total_usage - right_capacity)
    x_hi = min(left_capacity, total_usage)
    count = x_hi - x_lo + 1
    if count >= modulus:
        # 候选点不少于模数：覆盖全部剩余类，返回全域
        intervals = ((0, modulus - 1),)
        count = modulus
    else:
        first = (start_value + x_lo) % modulus
        arc = x_hi - x_lo  # 弧长（步数），候选数 = arc + 1 < modulus
        if first + arc <= modulus - 1:
            intervals = ((first, first + arc),)
        else:
            # 跨零点拆段：[first, M-1] 与 [0, 弧末端]
            intervals = ((first, modulus - 1), (0, (first + arc) % modulus))

    return MissingReadingResult(
        status=STATUS_OK,
        conflicts=(),
        diff=diff,
        total_wraps=total_wraps,
        left_capacity=left_capacity,
        right_capacity=right_capacity,
        left_usage_min=x_lo,
        left_usage_max=x_hi,
        intervals=intervals,
        candidate_count=count,
    )


# ---------------------------------------------------------------------------
# 最小统一速率上限（minimum-rate）：账单总量约束下反求最小统一速率门槛
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MinimumRateSegment:
    """最小统一速率门槛与账单总量约束后，单段仍可行的回绕次数整数区间。"""

    index: int
    diff: int
    elapsed_seconds: int
    base_wraps: int  # 非负增量要求的最小圈数 k_min
    min_wraps: int
    max_wraps: int

    @property
    def unique(self) -> bool:
        """圈数是否已被门槛与总量唯一确定。"""
        return self.min_wraps == self.max_wraps

    @property
    def wraps(self) -> Optional[int]:
        return self.min_wraps if self.unique else None

    def usage(self, modulus: int) -> Optional[int]:
        """圈数唯一时该段确定用量，否则为 None。"""
        return self.diff + self.min_wraps * modulus if self.unique else None

    def usage_bounds(self, modulus: int) -> Tuple[int, int]:
        """该区间用量的最小/最大可能值。"""
        return (
            self.diff + self.min_wraps * modulus,
            self.diff + self.max_wraps * modulus,
        )


@dataclass(frozen=True)
class MinimumRateResult:
    """最小统一速率上限求解结果。"""

    status: str  # STATUS_OK 或 STATUS_CONFLICT
    conflicts: Tuple[str, ...]  # REASON_TOTAL_* 原因
    total_wraps: Optional[int]  # 账单隐含的总回绕次数 K（不相容时为 None）
    extra_wraps: Optional[int]  # 待分配的额外圈数 T = K - Σk_min（冲突时为 None）
    min_rate: Optional[Fraction]  # 最小统一速率上限 R*（冲突时为 None）
    segments: Tuple[MinimumRateSegment, ...]
    # 可行账单总量下界 Σ base_i；速率不设上限，故可行总量无上界
    feasible_min_total: int


def _kth_smallest_breakpoint(
    bases: Sequence[int],
    elapsed_seconds: Sequence[int],
    modulus: int,
    kth: int,
) -> Fraction:
    """多重集合 ``{ (base_i + t*M)/s_i : t >= 1 }`` 中第 ``kth`` 小的值（精确）。

    计数函数 ``C(R) = Σ_i max(0, floor((R*s_i - base_i)/M))`` 统计不超过
    ``R`` 的断点个数，关于 ``R`` 单调不减；所求即满足 ``C(R) >= kth`` 的
    最小 ``R``。对 ``R`` 做精确二分（Fraction 中点、整数计数，无浮点）：

    任意两个不同断点 ``x/s_i``、``y/s_j`` 之差
    ``|x*s_j - y*s_i| / (s_i*s_j) >= 1/s_max²``，故当二分区间宽度小于
    ``1/s_max²`` 时，``(lo, hi]`` 内至多剩一个断点值；而计数不变式保证
    至少有一个。取各段「严格大于 lo 的最小断点」的最小值即为所求。
    迭代次数为 ``O(log(值域 × s_max²))``，与断点总数无关。
    """
    s_max = max(elapsed_seconds)

    def count(rate: Fraction) -> int:
        return sum(
            max(0, math.floor((rate * s - b) / modulus))
            for b, s in zip(bases, elapsed_seconds)
        )

    # 不变式：count(lo) < kth <= count(hi)
    lo = Fraction(0)  # base_i >= 0 时 t>=1 的断点均大于 0，故 count(0) = 0
    # hi 使每段至少容纳 kth 个断点：hi*s_i >= max(base) + kth*M
    hi = Fraction(max(bases) + kth * modulus, min(elapsed_seconds))
    precision = Fraction(1, s_max * s_max)
    while hi - lo >= precision:
        mid = (lo + hi) / 2
        if count(mid) >= kth:
            hi = mid
        else:
            lo = mid

    # (lo, hi] 内恰有一个断点值：各段严格大于 lo 的最小断点（t >= 1）
    return min(
        Fraction(
            b + max(1, math.floor((lo * s - b) / modulus) + 1) * modulus,
            s,
        )
        for b, s in zip(bases, elapsed_seconds)
    )


def solve_minimum_rate(
    diffs: Sequence[int],
    elapsed_seconds: Sequence[int],
    total_usage: int,
    modulus: int,
) -> MinimumRateResult:
    """求最小统一速率上限 R* 及该门槛下各段可行圈数范围，不枚举圈数组合。

    段 ``i`` 用量 ``u_i = diff_i + k_i*M``（``k_i >= 0`` 整数），约束为
    ``Σ u_i = total_usage`` 且 ``u_i / s_i <= R*`` 对所有段成立，求最小
    的 ``R*``：

    1. 账单总量须与首尾读数差模 M 同余（``total_incompatible_modulus``）；
       同余且 ``B >= 0`` 时总回绕次数 ``K = (B - Σdiff)/M`` 自动非负。
    2. 记 ``base_i = diff_i + k_min_i*M`` 为满足非负增量的最小段用量，
       待分配额外圈数 ``T = K - Σk_min``。``T < 0`` 即账单低于可行最小
       总量 ``Σ base_i``（``total_out_of_range``；速率无上限，故可行
       总量只有下界 ``[Σ base_i, +∞)``）。
    3. 速率 ``R`` 可行当且仅当 ``R >= max(base_i/s_i)`` 且
       ``Σ floor((R*s_i - base_i)/M) >= T``——后者即「不超过 R 的断点
       ``(base_i + t*M)/s_i``（t >= 1）不少于 T 个」，故

           R* = max( max_i base_i/s_i, 第 T 小的断点值 )

       第 T 小断点由 :func:`_kth_smallest_breakpoint` 精确二分求得；
       ``T = 0`` 时无圈可分，``R* = max base_i/s_i``，各段圈数即 ``k_min``。
    4. 固定 ``R*`` 后各段额外圈数上限 ``cap_i = floor((R* s_i - base_i)/M)``，
       在 ``t_i ∈ [0, cap_i]``、``Σ t_i = T`` 下由整数区间运算收紧：

           lo_i = max(0, T - Σ_{j≠i} cap_j)，hi_i = min(cap_i, T)

       平移回 ``k_i = k_min_i + t_i`` 即各段可行圈数范围；``lo == hi``
       的段唯一确定用量，其余只给范围，不猜测。

    :param diffs: 各段首尾读数差 r2 - r1
    :param elapsed_seconds: 各段历时秒数（正整数）
    :param total_usage: 账单总用量（非负整数）
    :param modulus: 计数器模数
    """
    if len(diffs) != len(elapsed_seconds):
        raise ValueError("diffs 与 elapsed_seconds 数量必须一致")
    if not diffs:
        raise ValueError("至少需要一段读数区间")

    n = len(diffs)
    # k_min_i：diff + k*M >= 0 的最小非负整数 k（-M < diff < M，故为 0 或 1）
    k_mins = [0 if d >= 0 else (-d + modulus - 1) // modulus for d in diffs]
    bases = [d + k * modulus for d, k in zip(diffs, k_mins)]
    feasible_min_total = sum(bases)
    end_minus_start = sum(diffs)  # 望远镜相消：末读数 - 首读数

    def _conflict(reason: str, total_wraps: Optional[int]) -> MinimumRateResult:
        return MinimumRateResult(
            status=STATUS_CONFLICT,
            conflicts=(reason,),
            total_wraps=total_wraps,
            extra_wraps=None,
            min_rate=None,
            segments=(),
            feasible_min_total=feasible_min_total,
        )

    # 1) 账单总量必须与首尾读数差模 M 同余（等价于总回绕次数为整数）
    if (total_usage - end_minus_start) % modulus != 0:
        return _conflict(REASON_TOTAL_INCOMPATIBLE_MODULUS, None)

    total_wraps = (total_usage - end_minus_start) // modulus
    # 2) 待分配额外圈数 T；为负即账单低于可行最小总量
    extra = total_wraps - sum(k_mins)
    if extra < 0:
        return _conflict(REASON_TOTAL_OUT_OF_RANGE, total_wraps)

    # 3) 最小统一速率上限 R* = max( max_i base_i/s_i, 第 T 小断点 )
    rate_base = max(Fraction(b, s) for b, s in zip(bases, elapsed_seconds))
    if extra == 0:
        min_rate = rate_base
    else:
        min_rate = max(
            rate_base,
            _kth_smallest_breakpoint(bases, elapsed_seconds, modulus, extra),
        )

    # 4) 门槛下各段可行圈数范围（整数区间运算，不枚举组合）
    caps = [
        math.floor((min_rate * s - b) / modulus)
        for b, s in zip(bases, elapsed_seconds)
    ]
    sum_caps = sum(caps)
    segments = []
    for i in range(n):
        lo_t = max(0, extra - (sum_caps - caps[i]))
        hi_t = min(caps[i], extra)
        segments.append(
            MinimumRateSegment(
                index=i,
                diff=diffs[i],
                elapsed_seconds=elapsed_seconds[i],
                base_wraps=k_mins[i],
                min_wraps=k_mins[i] + lo_t,
                max_wraps=k_mins[i] + hi_t,
            )
        )

    return MinimumRateResult(
        status=STATUS_OK,
        conflicts=(),
        total_wraps=total_wraps,
        extra_wraps=extra,
        min_rate=min_rate,
        segments=tuple(segments),
        feasible_min_total=feasible_min_total,
    )


# ---------------------------------------------------------------------------
# 双表同段交叉核验（dual-meter compare）：两块表同时计量同一用量
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DualMeterCompareResult:
    """双表同段交叉核验结果。"""

    status: str  # STATUS_OK 或 STATUS_CONFLICT
    conflicts: Tuple[str, ...]  # REASON_INCOMPATIBLE_MODULUS / REASON_RANGE_DISJOINT
    gcd: int  # gcd(表 A 模数, 表 B 模数)
    step: int  # lcm(表 A 模数, 表 B 模数)：相邻共同候选用量之差
    # 共同同余类 u ≡ residue (mod step) 的最小非负代表；同余不相容时为 None
    residue: Optional[int]
    # 不小于区间交下界的最小共同候选（同余相容时必存在；
    # 范围无交集时它已超出区间交上界）；同余不相容时为 None
    nearest_candidate: Optional[int]
    # 共同用量候选闭区间 [min_usage, max_usage]；冲突时为 None
    min_usage: Optional[int]
    max_usage: Optional[int]
    candidate_count: int  # 共同用量候选数；冲突时为 0
    # 各表在非负增量与速率上限下的独立可行用量范围
    a_usage_min: int
    a_usage_max: int
    b_usage_min: int
    b_usage_max: int
    # 两表可行范围的区间交 [intersect_min, intersect_max]（上界 < 下界即为空）
    intersect_min: int
    intersect_max: int

    @property
    def unique(self) -> bool:
        """共同用量是否唯一。"""
        return self.candidate_count == 1


def compare_dual_meter(
    a_diff: int,
    a_bounds: Tuple[int, int],
    a_modulus: int,
    b_diff: int,
    b_bounds: Tuple[int, int],
    b_modulus: int,
) -> DualMeterCompareResult:
    """联立两块同段计量的水表求共同用量候选范围，不逐个枚举回绕圈数。

    两块表在同一时段计量同一真实用量 ``u``：

        u = d_a + k_a*M_a = d_b + k_b*M_b   （k_a, k_b 为非负整数圈数）

    1. 同余联立：``u ≡ d_a (mod M_a)`` 且 ``u ≡ d_b (mod M_b)``。由中国
       剩余定理，有解当且仅当 ``d_a ≡ d_b (mod g)``，``g = gcd(M_a, M_b)``；
       否则两表读数差同余不相容（``incompatible_modulus``）。相容时全部
       解为单一同余类 ``u ≡ u0 (mod L)``，``L = lcm(M_a, M_b)``：由扩展
       欧几里得 ``c1*M_a + c2*M_b = g`` 知 ``(M_a/g)*c1 ≡ 1 (mod M_b/g)``，
       取 ``t0 = ((d_b - d_a)/g * c1) mod (M_b/g)``，则 ``u0 = d_a + M_a*t0``。
    2. 范围求交：各表可行用量为闭区间
       ``U_i = [d_i + lo_i*M_i, d_i + hi_i*M_i]``（``[lo_i, hi_i]`` 为非负
       增量与速率上限夹出的圈数区间，调用方保证各自可行）。共同候选即
       同余类与 ``U_a ∩ U_b`` 之交：记 ``lo = max(U_a_lo, U_b_lo)``、
       ``hi = min(U_a_hi, U_b_hi)``，则

           u_min = u0 + L*ceil((lo - u0)/L)
           u_max = u0 + L*floor((hi - u0)/L)

       ``u_min > u_max`` 即范围无交集（``range_disjoint``），涵盖区间
       本身不交（``lo > hi``）与交集内无同余点两种情形，与同余不相容是
       不同的冲突原因。
    3. 候选为等差数列 ``u_min, u_min + L, ..., u_max``，候选数
       ``(u_max - u_min)/L + 1`` 由端点直接算得；候选数为 1 时共同用量
       唯一。每个候选 ``u`` 唯一对应两表圈数 ``(u - d_i)/M_i``，全程整数
       区间与同余运算，候选数再大也不逐个枚举回绕圈数。

    :param a_bounds/b_bounds: 各表在非负增量与速率上限下的可行圈数区间
        ``(k_min, k_max)``，调用方需保证每表均可行（k_max >= k_min）
    """
    a_lo, a_hi = a_bounds
    b_lo, b_hi = b_bounds

    a_usage_min = a_diff + a_lo * a_modulus
    a_usage_max = a_diff + a_hi * a_modulus
    b_usage_min = b_diff + b_lo * b_modulus
    b_usage_max = b_diff + b_hi * b_modulus
    intersect_min = max(a_usage_min, b_usage_min)
    intersect_max = min(a_usage_max, b_usage_max)

    g, c1, _ = _extended_gcd(a_modulus, b_modulus)
    step = a_modulus // g * b_modulus  # lcm(M_a, M_b)

    def _conflict(
        reason: str,
        residue: Optional[int],
        nearest_candidate: Optional[int],
    ) -> DualMeterCompareResult:
        return DualMeterCompareResult(
            status=STATUS_CONFLICT,
            conflicts=(reason,),
            gcd=g,
            step=step,
            residue=residue,
            nearest_candidate=nearest_candidate,
            min_usage=None,
            max_usage=None,
            candidate_count=0,
            a_usage_min=a_usage_min,
            a_usage_max=a_usage_max,
            b_usage_min=b_usage_min,
            b_usage_max=b_usage_max,
            intersect_min=intersect_min,
            intersect_max=intersect_max,
        )

    # 1) 同余相容性：d_a ≡ d_b (mod g)，否则不存在任何共同用量
    if (a_diff - b_diff) % g != 0:
        return _conflict(REASON_INCOMPATIBLE_MODULUS, None, None)

    # 共同同余类 u ≡ u0 (mod L)：u0 = d_a + M_a*t0，
    # t0 为 (M_a/g)*t ≡ (d_b - d_a)/g (mod M_b/g) 的解
    t0 = ((b_diff - a_diff) // g * c1) % (b_modulus // g)
    u0 = a_diff + a_modulus * t0
    residue = u0 % step

    # 2) 同余类与两表可行范围之交（ceil/floor 各一次，不枚举圈数）
    u_min = u0 + step * _ceil_div(intersect_min - u0, step)
    u_max = u0 + step * ((intersect_max - u0) // step)
    if u_min > u_max:
        return _conflict(REASON_RANGE_DISJOINT, residue, u_min)

    return DualMeterCompareResult(
        status=STATUS_OK,
        conflicts=(),
        gcd=g,
        step=step,
        residue=residue,
        nearest_candidate=u_min,
        min_usage=u_min,
        max_usage=u_max,
        candidate_count=(u_max - u_min) // step + 1,
        a_usage_min=a_usage_min,
        a_usage_max=a_usage_max,
        b_usage_min=b_usage_min,
        b_usage_max=b_usage_max,
        intersect_min=intersect_min,
        intersect_max=intersect_max,
    )


# ---------------------------------------------------------------------------
# 异常采样清理（clean-readings）：删除最少内部读数使保留序列物理可行
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CleanReadingsResult:
    """异常采样清理结果。"""

    status: str  # STATUS_OK 或 STATUS_NO_SOLUTION
    # 保留读数索引（升序，含首索引 0 与末索引 n-1）；无解时为空
    kept_indices: Tuple[int, ...]
    # 删除的内部读数索引（升序）；无解时为空
    removed_indices: Tuple[int, ...]


def clean_readings(
    values: Sequence[int],
    timestamps: Sequence[datetime],
    modulus: int,
    max_rate_per_second: Fraction,
) -> CleanReadingsResult:
    """删除最少内部读数，使保留序列（首尾必须保留）两两相邻物理可行。

    任意两条读数 ``(v_i, t_i)``、``(v_j, t_j)``（``i < j``）可相邻保留，
    当且仅当把它们视为一段相邻读数时物理可行：存在非负整数回绕次数
    ``k``，使增量 ``(v_j - v_i) + k*M`` 非负且不超过
    ``max_rate_per_second × (t_j − t_i)`` 秒——与 :func:`solve_segment`
    完全相同的判定（复用同一 Fraction 精确速率运算）。

    读数索引构成有向无环图（边只从低索引指向高索引），保留序列即一条
    ``0 → n-1`` 路径；删除最少 ⟺ 保留最多 ⟺ 路径边数最多，故求 DAG 上的
    **最长路径**（按拓扑序一遍 DP 即可，不枚举子序列）。最优路径不唯一
    时按保留索引序列字典序选定：设 ``dist[i]`` 为首读数到 ``i`` 的最多边
    数、``tail[i]`` 为 ``i`` 到末读数的最多边数、``D = dist[n-1]``，从首读
    数出发每步在「边可行、``dist[q] = dist[cur] + 1`` 且
    ``dist[q] + tail[q] = D``」的候选中取最小索引。当前位置在某条最优路
    径上时这样的后继必存在（最长路径必有最优后继），归纳即得字典序最小
    的完整保留序列。首末不可连通（``0 → n-1`` 无路径）时返回无解。逐对
    判定与两遍 DP 均为 ``O(n²)``，与可行回绕次数区间大小无关。
    """
    n = len(values)
    if n != len(timestamps):
        raise ValueError("values 与 timestamps 数量必须一致")
    if n < 2:
        raise ValueError("至少需要 2 条读数")

    # 1) 逐对判定物理可行性（复用 solve_segment 的精确速率运算）：
    #    nxt[i] 为可直接跟在 i 之后的索引列表（按 j 升序构造）
    nxt: list = [[] for _ in range(n)]
    for i in range(n - 1):
        vi, ti = values[i], timestamps[i]
        for j in range(i + 1, n):
            elapsed = int((timestamps[j] - ti).total_seconds())
            sol = solve_segment(
                0, vi, values[j], elapsed, modulus, max_rate_per_second
            )
            if sol.status != STATUS_NO_SOLUTION:
                nxt[i].append(j)

    # 2) DAG 最长路：dist[i] 为 0 -> i 的最多边数（不可达为 None）
    dist: list = [None] * n
    dist[0] = 0
    for i in range(n):
        if dist[i] is None:
            continue
        for j in nxt[i]:
            if dist[j] is None or dist[i] + 1 > dist[j]:
                dist[j] = dist[i] + 1

    # 3) tail[i] 为 i -> n-1 的最多边数（不可达为 None）
    tail: list = [None] * n
    tail[n - 1] = 0
    for i in range(n - 2, -1, -1):
        best = None
        for j in nxt[i]:
            if tail[j] is not None and (best is None or tail[j] + 1 > best):
                best = tail[j] + 1
        tail[i] = best

    # 4) 首末无法连通：明确无解（首尾仍必须保留，但没有任何合法保留序列）
    if dist[n - 1] is None:
        return CleanReadingsResult(
            status=STATUS_NO_SOLUTION, kept_indices=(), removed_indices=()
        )

    # 5) 字典序最小的最优保留序列：nxt[cur] 已升序，首个满足最优性条件的
    #    候选即该位置可取的最小索引
    total = dist[n - 1]
    kept = [0]
    cur = 0
    while cur != n - 1:
        step = dist[cur] + 1
        for q in nxt[cur]:
            if (
                dist[q] == step
                and tail[q] is not None
                and dist[q] + tail[q] == total
            ):
                kept.append(q)
                cur = q
                break
        else:  # 数学上不可达：最长路上的点必有最优后继
            raise RuntimeError("最优保留序列重构失败")

    kept_set = set(kept)
    removed = tuple(i for i in range(1, n - 1) if i not in kept_set)
    return CleanReadingsResult(
        status=STATUS_OK,
        kept_indices=tuple(kept),
        removed_indices=removed,
    )


# ---------------------------------------------------------------------------
# 总分表漏损复核（master-sub loss）：总表用量减去各分表用量之和，逐段非负漏损
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LossMeterSegment:
    """某块表（总表或某块分表）在某段上的读数差与可行回绕次数整数区间。"""

    diff: int
    min_wraps: int
    max_wraps: int  # 小于 min_wraps 表示该表单段无解（不满足非负增量或超速）

    @property
    def feasible(self) -> bool:
        return self.max_wraps >= self.min_wraps

    def usage_bounds(self, modulus: int) -> Tuple[int, int]:
        """该表该段用量的最小/最大可能值。"""
        return (
            self.diff + self.min_wraps * modulus,
            self.diff + self.max_wraps * modulus,
        )


@dataclass(frozen=True)
class LossSegment:
    """整期漏损总量联立后，单段漏损与总表/分表圈数差的收紧结果。"""

    index: int
    diff: int  # D_i = 总表读数差 - Σ 分表读数差
    min_wraps: int  # 非负漏损与总量联立后 w_i = k_主 - Σk_分 的下界（可负）
    max_wraps: int  # w_i 的上界（可负）

    @property
    def unique(self) -> bool:
        """该段漏损（圈数差）是否已被总量唯一确定。"""
        return self.min_wraps == self.max_wraps

    @property
    def wraps(self) -> Optional[int]:
        return self.min_wraps if self.unique else None

    def loss(self, modulus: int) -> Optional[int]:
        """圈数差唯一时该段确定漏损，否则为 None。"""
        return self.diff + self.min_wraps * modulus if self.unique else None

    def loss_bounds(self, modulus: int) -> Tuple[int, int]:
        """该段漏损的最小/最大可能值（端点均可达到，均非负）。"""
        return (
            self.diff + self.min_wraps * modulus,
            self.diff + self.max_wraps * modulus,
        )


@dataclass(frozen=True)
class NegativeLossSegment:
    """某段总表用量恒小于各分表用量之和（漏损无法非负）的冲突明细。"""

    index: int
    diff: int  # D_i
    # 各表圈数区间连续差值给出的 w_i 范围（尚未施加非负漏损约束，可含负值）
    min_wraps: int
    max_wraps: int
    required_min_wraps: int  # 非负漏损要求的 w_i 下界 ceil(-D_i / M)


@dataclass(frozen=True)
class MasterSubLossResult:
    """总分表漏损复核结果。"""

    status: str  # STATUS_OK 或 STATUS_CONFLICT
    conflicts: Tuple[str, ...]
    # 各表各段的独立判定结果：meters[0] 为总表，其余为分表（与输入同序）；
    # 段顺序即相邻时刻段顺序。存在单表无解冲突时其余结构仍照常给出
    meters: Tuple[Tuple[LossMeterSegment, ...], ...]
    # 总量联立收紧后的各段漏损；冲突时为空
    segments: Tuple[LossSegment, ...]
    total_wraps: Optional[int]  # 整期圈数差总和 W = (L - ΣD_i)/M；同余冲突时为 None
    feasible_min_total: int  # 各段漏损下界之和（整期可行漏损下界）
    feasible_max_total: int  # 各段漏损上界之和（整期可行漏损上界）


def reconcile_master_sub_loss(
    meter_segments: Sequence[Sequence[LossMeterSegment]],
    total_loss: int,
    modulus: int,
) -> MasterSubLossResult:
    """以整期漏损总量联立总分表读数，精确收紧各段漏损范围，不枚举回绕组合。

    总表 ``meter_segments[0]`` 与若干分表 ``meter_segments[1:]`` 共用同一
    模数 ``modulus``，且各表段数相同（每段对应同一对相邻时刻）。表 ``m``
    在段 ``i`` 的真实用量为 ``u_{m,i} = d_{m,i} + k_{m,i}*M``，调用方需
    先以 :func:`solve_segment` 求出各表各段可行圈数区间；``max_wraps <
    min_wraps`` 表示该表单段本身无解。

    判定顺序（四类冲突原因可区分）：

    1. **单表无解**（``no_solution``）：任一表的任一段不满足非负增量/
       速率上限，直接冲突，不做后续联立。
    2. **单段漏损无法非负**（``loss_segment_negative``）：段漏损
       ``l_i = u_主,i - Σ_m u_分,i = D_i + w_i*M``，其中
       ``D_i = d_主,i - Σ d_分,i``、``w_i = k_主,i - Σ k_分,m,i``。
       各表圈数独立取其连续整数区间，故 ``w_i`` 的可行范围为连续整数
       区间 ``[lo_i^0, hi_i^0]``（总表取 + 区间、分表取 − 区间）；非负
       漏损要求 ``w_i >= ceil(-D_i/M)``，与该区间无交即该段总表用量在
       任何回绕组合下都小于分表用量之和。
    3. **总量同余冲突**（``total_incompatible_modulus``）：整期漏损
       ``L = Σ l_i = Σ D_i + M·W``（``W = Σ w_i``，为各表整期圈数差，
       可正可负），故 ``L - ΣD_i`` 必须被 ``M`` 整除。
    4. **总量超界**（``total_out_of_range``）：固定
       ``W = (L - ΣD_i)/M`` 后要求 ``Σ lo_i^0 <= W <= Σ hi_i^0``；
       否则没有任何回绕组合的整期漏损等于 L。

    可行时各段 ``w_i`` 在 ``w_i ∈ [lo_i^0, hi_i^0]``、``Σ w_i = W`` 下
    由与 :func:`reconcile_total` 相同的整数区间公式收紧（区间允许负值，
    公式不变）：

        lo_i' = max(lo_i^0, W - Σ_{j≠i} hi_j^0)
        hi_i' = min(hi_i^0, W - Σ_{j≠i} lo_j^0)

    ``lo_i' == hi_i'`` 的段漏损唯一，给出确定值；其余段只给漏损上下界。
    各段圈数差相互独立（各表圈数独立取值即可实现任意 ``w_i`` 组合），
    故端点均可达到且交叉端点相等：段下界之和与段上界之和在总量约束下
    此消彼长，均等于 L。

    :param total_loss: 给定的整期漏损总量（非负整数）
    """
    if not meter_segments:
        raise ValueError("至少需要总表一块表")
    if len(meter_segments) < 2:
        raise ValueError("至少需要一块分表")
    seg_count = len(meter_segments[0])
    if seg_count < 1:
        raise ValueError("至少需要一段读数区间")
    if any(len(segs) != seg_count for segs in meter_segments):
        raise ValueError("总表与各分表的段数必须一致（共用同一组时刻）")

    meters = tuple(tuple(segs) for segs in meter_segments)

    def _result(
        conflicts: Sequence[str],
        segments: Sequence[LossSegment] = (),
        total_wraps: Optional[int] = None,
        feasible_min_total: int = 0,
        feasible_max_total: int = 0,
    ) -> MasterSubLossResult:
        return MasterSubLossResult(
            status=STATUS_CONFLICT if conflicts else STATUS_OK,
            conflicts=tuple(conflicts),
            meters=meters,
            segments=tuple(segments),
            total_wraps=total_wraps,
            feasible_min_total=feasible_min_total,
            feasible_max_total=feasible_max_total,
        )

    # 1) 单表单段无解（不满足非负增量/速率上限）：直接冲突
    if any(not seg.feasible for segs in meters for seg in segs):
        return _result([STATUS_NO_SOLUTION])

    # 2) 各段圈数差 w_i = k_主 - Σ k_分 的连续差值区间，并施加非负漏损约束
    base_lows: list = []
    base_highs: list = []
    negative: list = []
    for i in range(seg_count):
        master_seg = meters[0][i]
        d_i = master_seg.diff - sum(segs[i].diff for segs in meters[1:])
        raw_lo = master_seg.min_wraps - sum(
            segs[i].max_wraps for segs in meters[1:]
        )
        raw_hi = master_seg.max_wraps - sum(
            segs[i].min_wraps for segs in meters[1:]
        )
        required = _ceil_div(-d_i, modulus)  # D_i + w*M >= 0 的最小整数 w
        lo, hi = max(raw_lo, required), raw_hi
        if hi < required:
            negative.append(
                NegativeLossSegment(
                    index=i,
                    diff=d_i,
                    min_wraps=raw_lo,
                    max_wraps=raw_hi,
                    required_min_wraps=required,
                )
            )
        base_lows.append(lo)
        base_highs.append(hi)

    if negative:
        return _result([REASON_LOSS_SEGMENT_NEGATIVE])

    diffs = [
        meters[0][i].diff - sum(segs[i].diff for segs in meters[1:])
        for i in range(seg_count)
    ]
    feasible_min_total = sum(
        d + lo * modulus for d, lo in zip(diffs, base_lows)
    )
    feasible_max_total = sum(
        d + hi * modulus for d, hi in zip(diffs, base_highs)
    )

    # 3) 整期漏损总量的模 M 同余校验（W 可为负：分表圈数总和超过总表并不矛盾）
    numerator = total_loss - sum(diffs)
    if numerator % modulus != 0:
        return _result(
            [REASON_TOTAL_INCOMPATIBLE_MODULUS],
            feasible_min_total=feasible_min_total,
            feasible_max_total=feasible_max_total,
        )

    total_wraps = numerator // modulus
    sum_low, sum_high = sum(base_lows), sum(base_highs)
    if not (sum_low <= total_wraps <= sum_high):
        return _result(
            [REASON_TOTAL_OUT_OF_RANGE],
            total_wraps=total_wraps,
            feasible_min_total=feasible_min_total,
            feasible_max_total=feasible_max_total,
        )

    # 4) W 固定：与 reconcile_total 相同的整数区间收紧（允许负圈数差）
    narrowed = []
    for i in range(seg_count):
        lo, hi = base_lows[i], base_highs[i]
        new_lo = max(lo, total_wraps - (sum_high - hi))
        new_hi = min(hi, total_wraps - (sum_low - lo))
        narrowed.append(
            LossSegment(
                index=i,
                diff=diffs[i],
                min_wraps=new_lo,
                max_wraps=new_hi,
            )
        )

    return _result(
        [],
        segments=narrowed,
        total_wraps=total_wraps,
        feasible_min_total=feasible_min_total,
        feasible_max_total=feasible_max_total,
    )

# 累计水表读数用量复核 API

基于 FastAPI 的用量复核服务：输入一组带秒精度 UTC 时间戳的累计水表读数、计数器模数与每秒最大计数增量，对每段相邻读数判定满足**非负增量**与**速率上限**的整圈回绕次数是否唯一。唯一时返回分段用量与总用量；无解或多解时返回出错区间与原因，**不猜测圈数**。

此外提供**账单总量对账**接口：在同一组非负增量与速率上限约束下，额外接收账单总用量，以整数区间运算收紧各段仍可行的回绕次数范围；只有圈数被唯一确定的段才给出用量，其余段仅返回范围，冲突时给出明确原因。

还提供**每日用量上下界**接口：将每个相邻读数区间按 UTC 午夜切成子段（每段容量为 `floor(速率 × 秒数)`），在区间总增量 `读数差 + k×模数` 可分配为各子段非负整数用量的前提下，给出覆盖时段内**每个 UTC 自然日**的最小/最大可行整数用量。

并提供**换表账单复核**接口：接收旧表与新表各自的起止读数、模数与每秒最大速率（两表模数可不同），以及跨两表的账单总用量；要求旧表终读与新表初读为同一换表刻。两段先分别求满足非负增量与速率上限的回绕整数区间，再以扩展欧几里得对线性丢番图方程 `M旧·k旧 + M新·k新 = 账单 − 两段读数差` 求整数通解、用两段区间夹出参数范围（**不枚举圈数组合**），返回两段可行用量上下界及唯一性；单段无解、账单与模数不相容或联立超界时给出可区分的原因。

另提供**漏采读数推断**接口：输入同一水表的起止读数与时间、两者之间的一个漏采时刻、模数、每秒速率上限与该账期账单总用量。先校验账单总量与首尾读数差的模数同余（同余且账单非负时，隐含总回绕次数自动非负），再按漏采时刻两侧各自的 `floor(速率 × 秒数)` 整数容量求**左侧可行用量闭区间**；将首读数加左侧用量后取模，在 `[0, 模数−1]` 内返回精确、不重叠的候选读数闭区间（跨零点拆段、覆盖全模数时返回全域）、候选个数与是否唯一。账单不相容或两侧容量不足时返回可区分的冲突原因，**不猜测读数**。

另提供**最小统一速率上限**接口：输入同一水表的模数、严格递增的秒精度读数序列与账单总用量（**无需给定速率上限**，读数校验与其他接口一致）。先按首尾读数差与模数校验账单同余，不相容时返回明确冲突；相容时，在各段非负整数用量且总和等于账单的约束下，求使「各段用量 ÷ 各段历时」均不超过它的**最小统一速率上限**，以约分后的分子/分母精确返回（`Fraction` 精确二分 + 整数区间运算，**不用浮点近似，也不枚举全部圈数组合**），并给出该门槛下每段可行的圈数范围与是否唯一；范围不唯一时**不虚构单段用量**。

另提供**双表同段交叉核验**接口：输入两块同时计量同一用量的水表各自的模数、首末秒精度读数与每秒速率上限（两表模数可不同），要求两表**起止时刻分别相同**。各表用量须非负且不超速；按两表读数差的模数同余联立共同用量（中国剩余定理），并与两表可行用量范围求交，返回共同用量的**最小值、最大值、候选数与唯一性**（等差数列端点直接算得，**不逐个枚举回绕圈数**）；同余不相容与范围无交集给出可区分的冲突原因。

另提供**停水时段账单复核**接口：输入现有读数序列、模数、每秒速率上限、账单总用量及若干**左闭右开**的停水时段。停水时段先统一裁剪到读数账期，再合并重叠或相接（端点相同）的时段；每对相邻读数扣除停水后，把剩余的连续供水片段**分别**按 `floor(速率 × 秒数)` 取整并求和作为该段整数用量容量（**不能跨停水时段合并取整**），以此容量限制非负回绕圈数，再用账单总用量联立收紧各段可行圈数。返回各段供水秒数、供水片段明细、用量上下界与唯一性；**单段无解、账单同余冲突与总量超界**分别给出可区分的冲突原因。

并提供**分时单价账单金额区间**接口：按相邻读数段给出一一对应的**非负十进制分时单价**（数量须等于段数），复用读数、模数、速率与账单总用量校验。先用各段回绕可行整数区间与账单总量约束判冲突（**单段无解、账单总量同余不相容、总量超界**原因可区分）；可行时账单隐含的固定总圈数把各段圈数收紧为整数区间，将先取最小圈数后的剩余圈数按单价**从低到高**与**从高到低**贪心分配（**不枚举圈数组合、不使用浮点数**），精确算出**最低与最高应收金额**及各自的分段用量方案，金额一律以**十进制字符串**返回。

还提供**异常采样清理**接口：输入模数、按时序的读数序列与非负每秒速率上限，把**任意两条**读数按时间差、非负增量与回绕模数判定可否相邻保留（复用逐段复核的同一精确速率运算）。**首尾读数必须保留**，在此前提下求**删除最少内部读数**的完整序列（有向无环图最长路径，`O(n²)`，**不枚举保留子序列**）；多组最优解按**保留索引序列字典序**选定，返回保留索引、删除索引与删除数；首末读数在该速率与模数约束下无法连通时返回明确的 `no_solution` 状态。

另提供**总分表漏损复核**接口：输入**同一模数**的一块总表与**至少一块分表**（各表可有各自每秒速率上限），各表共用同一组严格递增的秒精度时间点并给出对应读数，以及给定的**整期漏损总量**。逐表复用现有读数与速率校验，求每段非负用量的可行回绕圈数区间；每段漏损定义为**总表用量减去各分表用量之和，且不得为负**。利用同模数下总表/分表圈数区间的**连续差值区间**求每段可行漏损范围，再由整期漏损总量联立收紧各段范围（整数区间运算，**不枚举回绕组合**）；仅在唯一时给出确定漏损，其余段只给非负漏损上下界。**单表无解、单段漏损无法非负、总量同余冲突与总量超界**分别给出可区分的冲突原因。

## 快速启动（Docker，一键）

```bash
docker compose up --build
```

依赖在镜像构建时自动安装，无需本地环境。启动后（默认监听宿主机 **8000** 端口）：

- API 地址：`http://localhost:8000`
- 用量复核：`POST http://localhost:8000/v1/usage/verify`
- 账单总量对账：`POST http://localhost:8000/v1/usage/reconcile`
- 停水时段账单复核：`POST http://localhost:8000/v1/usage/outage-reconcile`
- 每日用量上下界：`POST http://localhost:8000/v1/usage/daily-range`
- 换表账单复核：`POST http://localhost:8000/v1/usage/meter-change/reconcile`
- 漏采读数推断：`POST http://localhost:8000/v1/usage/missing-reading`
- 最小统一速率上限：`POST http://localhost:8000/v1/usage/minimum-rate`
- 双表同段交叉核验：`POST http://localhost:8000/v1/usage/dual-meter/compare`
- 总分表漏损复核：`POST http://localhost:8000/v1/usage/master-sub/loss-reconcile`
- 分时单价账单金额区间：`POST http://localhost:8000/v1/billing/charge-range`
- 异常采样清理：`POST http://localhost:8000/v1/usage/clean-readings`
- 交互式文档（Swagger UI）：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

例如本机用 curl 调用停水时段账单复核（端口 `8000`）：

```bash
curl -s http://localhost:8000/v1/usage/outage-reconcile \
  -H 'Content-Type: application/json' \
  -d '{"modulus":1000,"max_rate_per_second":30,"total_usage":1100,
       "readings":[{"timestamp":"2026-09-24T00:00:00Z","value":0},
                   {"timestamp":"2026-09-24T00:00:30Z","value":500},
                   {"timestamp":"2026-09-24T00:01:00Z","value":100}],
       "outages":[{"start":"2026-09-24T00:00:10Z","end":"2026-09-24T00:00:20Z"},
                  {"start":"2026-09-24T00:00:40Z","end":"2026-09-24T00:00:50Z"}]}'
```

### 配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| 宿主机端口 | `8000` | 在 `docker-compose.yml` 的 `ports` 中修改，如 `"8080:8000"` |
| 容器内端口 | `8000` | 由 `Dockerfile` 的 `CMD` 指定，一般无需修改 |

上述所有接口（含 `/docs` 与 `/health`）均通过这同一个端口对外提供；无其他必需配置（无数据库、无外部依赖）。

## 本地运行（可选）

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

运行测试：

```bash
pip install -r requirements-dev.txt
pytest
```

## API 说明

### `POST /v1/usage/verify`

**请求体**

```json
{
  "modulus": 1000,
  "max_rate_per_second": 20,
  "readings": [
    { "timestamp": "2026-09-24T00:00:00Z", "value": 900 },
    { "timestamp": "2026-09-24T00:00:10Z", "value": 100 }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `modulus` | 整数 | `>= 1`，计数器模数（回绕周期） |
| `max_rate_per_second` | 数值 | `>= 0`，每秒最大计数增量，支持小数（按精确分数计算，无浮点误差） |
| `readings` | 数组 | 至少 2 条；`timestamp` 为秒精度且带时区（建议 UTC，其他时区会换算为 UTC），全序列**严格递增**；`value` 为整数且 `0 <= value < modulus` |

**响应（全部区间唯一，`200`）**

```json
{
  "status": "ok",
  "modulus": 1000,
  "segments": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:00:10Z",
      "start_reading": 900,
      "end_reading": 100,
      "elapsed_seconds": 10,
      "wraps": 1,
      "usage": 200
    }
  ],
  "errors": [],
  "total_usage": 200
}
```

**响应（存在出错区间，`200`）**

```json
{
  "status": "error",
  "modulus": 1000,
  "segments": [],
  "errors": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:16:40Z",
      "start_reading": 100,
      "end_reading": 200,
      "elapsed_seconds": 1000,
      "reason": "ambiguous",
      "detail": "多解：回绕次数 k 在 [0, 9] 内均满足非负增量与速率上限约束，无法唯一确定用量，不做猜测",
      "min_wraps": 0,
      "max_wraps": 9
    }
  ],
  "total_usage": null
}
```

- `reason = "no_solution"`：没有任何回绕次数同时满足两条约束（通常是增量超过速率上限）。
- `reason = "ambiguous"`：存在多个可行回绕次数，无法唯一确定用量。
- 存在出错区间时，`segments` 仍返回其余唯一判定的区间，但 `total_usage` 为 `null`。

**请求校验失败（`422`）**：时间戳未严格递增、缺时区、含亚秒、读数越界、参数非法等，返回 FastAPI 标准错误明细。

### `POST /v1/usage/reconcile`

账单总量对账。请求体在复核接口字段基础上增加 `total_usage`（非负整数账单总用量），读数、模数、速率等校验与 `/v1/usage/verify` 完全一致。

**请求体**

```json
{
  "modulus": 1000,
  "max_rate_per_second": 10,
  "total_usage": 5000,
  "readings": [
    { "timestamp": "2026-09-24T00:00:00Z", "value": 100 },
    { "timestamp": "2026-09-24T00:16:40Z", "value": 200 },
    { "timestamp": "2026-09-24T00:33:20Z", "value": 100 }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `total_usage` | 整数 | `>= 0`，账单总用量（非负整数） |
| 其余字段 | — | 与 `/v1/usage/verify` 相同 |

**响应（账单可行，`200`，`status = "ok"`）**

```json
{
  "status": "ok",
  "modulus": 1000,
  "total_usage": 5000,
  "total_wraps": 5,
  "segments": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:16:40Z",
      "start_reading": 100,
      "end_reading": 200,
      "elapsed_seconds": 1000,
      "min_wraps": 0,
      "max_wraps": 4,
      "wraps": null,
      "usage": null,
      "min_usage": 100,
      "max_usage": 4100
    },
    {
      "index": 1,
      "start_timestamp": "2026-09-24T00:16:40Z",
      "end_timestamp": "2026-09-24T00:33:20Z",
      "start_reading": 200,
      "end_reading": 100,
      "elapsed_seconds": 1000,
      "min_wraps": 1,
      "max_wraps": 5,
      "wraps": null,
      "usage": null,
      "min_usage": 900,
      "max_usage": 4900
    }
  ],
  "conflicts": []
}
```

当某段收紧后圈数唯一（`min_wraps == max_wraps`），`wraps` 与 `usage` 给出确定值，`min_usage` / `max_usage` 为 `null`；仍有多解的段反之，**只给范围不猜测**。所有段确定用量之和恒等于 `total_usage`。

**响应（冲突，`200`，`status = "conflict"`）**

分段原本无解时：

```json
{
  "status": "conflict",
  "modulus": 1000,
  "total_usage": 300,
  "total_wraps": null,
  "segments": [],
  "conflicts": [
    {
      "kind": "segment",
      "index": 1,
      "start_timestamp": "2026-09-24T00:00:10Z",
      "end_timestamp": "2026-09-24T00:00:11Z",
      "start_reading": 300,
      "end_reading": 900,
      "elapsed_seconds": 1,
      "reason": "no_solution",
      "detail": "无解：最可能增量 600 已超出该区间 1s 内允许的最大增量 20（k 需同时满足 k>=0 与 k<=-1，区间为空）",
      "min_wraps": 0,
      "max_wraps": -1
    }
  ]
}
```

账单总量不相容或超界时（`kind = "total"`）：

```json
{
  "kind": "total",
  "reason": "total_incompatible_modulus",
  "detail": "账单总量与模数不相容：总量 B 必须满足 B ≡ 0 (mod 1000)（首尾读数差为 0），收到 5500（余数 500），总回绕次数不是整数",
  "feasible_min_total": 1000,
  "feasible_max_total": 19000,
  "expected_remainder": 0,
  "total_wraps": null
}
```

冲突原因：

- `kind = "segment"`，`reason = "no_solution"`：某段在非负增量/速率上限下原本无解（复用复核接口的逐段判定）。
- `kind = "total"`，`reason = "total_incompatible_modulus"`：账单总量与首尾读数差模 `modulus` 不同余，总回绕次数不是整数；`expected_remainder` 给出应有的余数。
- `kind = "total"`，`reason = "total_out_of_range"`：总回绕次数超出各段可行圈数之和 `[Σk_min, Σk_max]`，即可行账单总量不在 `[feasible_min_total, feasible_max_total]` 内。

存在分段无解冲突时不再进行总量推断；总量冲突时 `segments` 为空。`total_usage` 为负数或非整数等请求校验错误返回 `422`。

### `POST /v1/usage/outage-reconcile`

停水时段账单复核。请求体在账单对账接口字段基础上增加 `outages`（若干**左闭右开**的停水时段）；读数、模数、速率、`total_usage` 的校验与 `/v1/usage/reconcile` 完全一致。停水时段允许重叠、相接或部分/全部落在账期之外：服务端先把每个时段裁剪到读数账期 `[首读数时刻, 末读数时刻)`，再合并重叠或相接（端点相同）的时段，裁剪后为空的时段被丢弃。

**请求体**

```json
{
  "modulus": 1000,
  "max_rate_per_second": 30,
  "total_usage": 1100,
  "readings": [
    { "timestamp": "2026-09-24T00:00:00Z", "value": 0 },
    { "timestamp": "2026-09-24T00:00:30Z", "value": 500 },
    { "timestamp": "2026-09-24T00:01:00Z", "value": 100 }
  ],
  "outages": [
    { "start": "2026-09-24T00:00:10Z", "end": "2026-09-24T00:00:20Z" },
    { "start": "2026-09-24T00:00:40Z", "end": "2026-09-24T00:00:50Z" }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `total_usage` | 整数 | `>= 0`，账单总用量（非负整数） |
| `outages` | 数组 | 可空（缺省为 `[]`，等价于 `/v1/usage/reconcile`）；每项为左闭右开停水时段，`start` / `end` 为秒精度带时区时间戳且 `start < end`；允许账期外、重叠、相接，服务端裁剪合并 |
| 其余字段 | — | 与 `/v1/usage/verify` 相同 |

**响应（可行且两段均唯一，`200`，`status = "ok"`）**

```json
{
  "status": "ok",
  "modulus": 1000,
  "total_usage": 1100,
  "total_wraps": 1,
  "outages": [
    { "start_timestamp": "2026-09-24T00:00:10Z", "end_timestamp": "2026-09-24T00:00:20Z", "seconds": 10 },
    { "start_timestamp": "2026-09-24T00:00:40Z", "end_timestamp": "2026-09-24T00:00:50Z", "seconds": 10 }
  ],
  "segments": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:00:30Z",
      "start_reading": 0,
      "end_reading": 500,
      "elapsed_seconds": 30,
      "outage_seconds": 10,
      "supply_seconds": 20,
      "total_capacity": 600,
      "water_fragments": [
        { "start_timestamp": "2026-09-24T00:00:00Z", "end_timestamp": "2026-09-24T00:00:10Z", "seconds": 10, "capacity": 300 },
        { "start_timestamp": "2026-09-24T00:00:20Z", "end_timestamp": "2026-09-24T00:00:30Z", "seconds": 10, "capacity": 300 }
      ],
      "min_wraps": 0,
      "max_wraps": 0,
      "wraps": 0,
      "usage": 500,
      "min_usage": null,
      "max_usage": null,
      "unique": true
    },
    {
      "index": 1,
      "start_timestamp": "2026-09-24T00:00:30Z",
      "end_timestamp": "2026-09-24T00:01:00Z",
      "start_reading": 500,
      "end_reading": 100,
      "elapsed_seconds": 30,
      "outage_seconds": 10,
      "supply_seconds": 20,
      "total_capacity": 600,
      "water_fragments": [
        { "start_timestamp": "2026-09-24T00:00:30Z", "end_timestamp": "2026-09-24T00:00:40Z", "seconds": 10, "capacity": 300 },
        { "start_timestamp": "2026-09-24T00:00:50Z", "end_timestamp": "2026-09-24T00:01:00Z", "seconds": 10, "capacity": 300 }
      ],
      "min_wraps": 1,
      "max_wraps": 1,
      "wraps": 1,
      "usage": 600,
      "min_usage": null,
      "max_usage": null,
      "unique": true
    }
  ],
  "conflicts": []
}
```

- `outages`：裁剪到读数账期并合并重叠/相接时段后的停水时段，按开始时刻升序；`seconds` 为裁剪后的秒数。
- `elapsed_seconds` / `outage_seconds` / `supply_seconds`：区间总时长（含停水）/ 落在区间内的停水秒数 / 扣除停水后的供水秒数；恒有 `supply_seconds = elapsed_seconds - outage_seconds`。
- `water_fragments`：扣除停水后剩余的**连续供水片段**（左闭右开、按时间升序），每项给出秒数与该片段独立取整的容量 `floor(速率 × 秒数)`。
- `total_capacity`：**各供水片段分别取整后求和**的整数用量容量。注意它可能小于 `floor(速率 × supply_seconds)`——停水把连续供水切断后，各片段的取整余量不能跨停水时段合并。
- 圈数唯一（`min_wraps == max_wraps`，即 `unique = true`）时给出 `wraps` / `usage`，`min_usage` / `max_usage` 为 `null`；仍有多解时反之，**只给范围不猜测**，且所有可行组合的各段用量之和恒等于 `total_usage`（交叉端点相等：段下界之和与段上界之和的此消彼长由账单固定）。

**仍有多解（`unique = false`）的情形**：同上读数、速率提高到 `200`、账单 `2100` 时，容量各为 `4000`，账单联立后段 0 圈数 `k ∈ {0,1}`（用量 `[500, 1500]`）、段 1 圈数 `k ∈ {1,2}`（用量 `[600, 1600]`），可行组合为 `(500, 1600)` 与 `(1500, 600)`，均严格满足和为账单。

**响应（冲突，`200`，`status = "conflict"`）**

单段扣除停水后无解（`kind = "segment"`，`reason = "no_solution"`）：速率改为 `10`（容量 `200`）、账单 `1200` 时，两段连满足非负增量的最小用量（500、600）都无法容纳：

```json
{
  "status": "conflict",
  "modulus": 1000,
  "total_usage": 1200,
  "total_wraps": null,
  "outages": [ "……同上……" ],
  "segments": [],
  "conflicts": [
    {
      "kind": "segment",
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:00:30Z",
      "start_reading": 0,
      "end_reading": 500,
      "elapsed_seconds": 30,
      "outage_seconds": 10,
      "supply_seconds": 20,
      "reason": "no_solution",
      "detail": "无解：扣除停水后该区间供水 20s，2 个连续供水片段分别 floor(速率×秒数) 的容量之和仅为 200，而满足非负增量的最小总增量已为 500（读数差 500 + 0×1000）；回绕次数需同时满足 k>=0 与 k<=-1，区间为空（各片段分别取整，不能跨停水时段合并取整）",
      "min_wraps": 0,
      "max_wraps": -1,
      "total_capacity": 200,
      "water_fragments": [ "……两个容量 100 的片段……" ]
    }
  ]
}
```

账单与模数不相容（`kind = "total"`，`reason = "total_incompatible_modulus"`）：停水只改变各段容量、不改变模 `M` 同余关系，账单余数与首尾读数差不符时冲突，`expected_remainder` 给出应有余数（`total_wraps` 为 `null`）。

账单同余但超出停水后的可行总量（`kind = "total"`，`reason = "total_out_of_range"`）：`feasible_min_total` / `feasible_max_total` 为**扣除停水后**各段最小/最大可行用量之和（各段容量之和随停水收缩，故上界可能远小于无停水时）；此时同余成立，`total_wraps` 给出账单隐含的 `K`。

```json
{
  "kind": "total",
  "reason": "total_out_of_range",
  "detail": "账单总量超出停水后的可行范围：扣除停水后各段回绕次数均为非负整数且不超过各自供水片段容量之和时，总用量只能在 [1100, 7100]（模数 1000）之内，收到 8100",
  "feasible_min_total": 1100,
  "feasible_max_total": 7100,
  "expected_remainder": null,
  "total_wraps": 8
}
```

冲突优先级：存在单段无解时列出全部无解段（`kind = "segment"`）且不再进行账单联立；各段均可行后才校验账单同余与可行总量。三类原因——**单段无解、账单同余冲突、总量超界**——分别由 `kind` / `reason` 区分。冲突时 `segments` 为空，但 `outages` 与分段冲突中的 `water_fragments` 仍照常返回以便排查。`outages` 缺省或为空数组时，本接口与 `/v1/usage/reconcile` 结果一致（单段即一个覆盖全区间的供水片段）。请求校验错误（停水时段 `start >= end`、缺时区、含亚秒，以及读数越界、时间不递增、负速率、账单为负等）返回 `422`。

### `POST /v1/usage/daily-range`

按 UTC 自然日给出每日最小/最大可行整数用量。请求体与 `/v1/usage/verify` 完全相同（读数、模数、最大每秒速率的校验一致，无额外字段）。

**请求体**

```json
{
  "modulus": 1000,
  "max_rate_per_second": 100,
  "readings": [
    { "timestamp": "2026-09-24T23:59:55Z", "value": 800 },
    { "timestamp": "2026-09-25T00:00:05Z", "value": 50 }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| 字段同 `/v1/usage/verify` | — | `modulus` / `max_rate_per_second` / `readings` 的类型与校验完全复用 |

**响应（可行，`200`，`status = "ok"`）**

```json
{
  "status": "ok",
  "modulus": 1000,
  "days": [
    { "date": "2026-09-24", "min_usage": 0, "max_usage": 250, "segment_count": 1 },
    { "date": "2026-09-25", "min_usage": 0, "max_usage": 250, "segment_count": 1 }
  ],
  "boundary_note": "每个 UTC 自然日的 min_usage/max_usage 均可由某个可行的回绕次数及子段整数分配分别达到；不同日期（以及同一读数区间内各子段）的上界不保证存在同一个分配同时成立，请勿将各日上界相加后作为整体上界使用",
  "conflicts": []
}
```

上例中读数区间跨 UTC 午夜，切成各 5 秒的两个子段（容量各为 `floor(100 × 5) = 500`）；区间增量为 `(50 - 800) + 1×1000 = 250`，可在 `(250,0)` 到 `(0,250)` 间任意整数分配，故每日界为 `[0, 250]`。

- `days`：覆盖时段（首读数到末读数之间）实际被覆盖到的每个 UTC 自然日一行，按日期排序。
- `min_usage` / `max_usage`：当日所有读数区间落在该日的子段用量下界/上界之和，均为非负整数。
- `segment_count`：当日覆盖的读数区间子段数（一个读数区间在一个自然日内至多贡献一个子段）。
- `boundary_note`：**边界独立性说明**——每日的下界和上界都可分别由某个可行 `k` 及子段分配达到；但不同日期的上界（下界亦然）不保证由同一个分配同时满足。例如两个容量 5 的子段承担总量 8，每日界为 `[3, 5]`，可行分配只有 `(3,5)`、`(4,4)`、`(5,3)`，两日不可能同时取 5。

**响应（存在区间无可行分配，`200`，`status = "conflict"`）**

相邻读数跨日时，各子段容量**分别**取整为 `floor(速率 × 秒数)`，其和可能小于整段直接计算的容量。若连满足非负增量的最小总增量都无法容纳，则该区间不存在可行分配；此时返回区间索引与冲突原因，**不返回日用量**：

```json
{
  "status": "conflict",
  "modulus": 1000,
  "days": [],
  "boundary_note": "……",
  "conflicts": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T23:59:55Z",
      "end_timestamp": "2026-09-25T00:00:05Z",
      "start_reading": 950,
      "end_reading": 100,
      "elapsed_seconds": 10,
      "reason": "no_feasible_allocation",
      "detail": "无可行分配：该区间按 UTC 午夜切成 2 段，各子段容量 floor(速率×秒数) 之和为 10，而满足非负增量的最小总增量已为 150（读数差 -850 + 1×1000）；回绕次数需同时满足 k>=1 与 k<=0，区间为空，无法把整数增量分配到各日子段",
      "min_wraps": 1,
      "max_wraps": 0,
      "total_capacity": 10
    }
  ]
}
```

- `reason = "no_feasible_allocation"`：该区间不存在可行的回绕次数 `k >= 0`，使总增量 `读数差 + k×modulus` 不超过各日子段容量之和（且为非负整数）。
- `total_capacity`：该区间各 UTC 日子段容量之和；`min_wraps` 为非负增量要求的最小圈数，`max_wraps` 为子段容量允许的最大圈数（小于 `min_wraps` 即无解）。
- 多个区间同时冲突时一并列出；只要存在冲突，`days` 即为空。请求校验错误（缺时区、亚秒、不递增、读数越界等）仍返回 `422`。

### `POST /v1/usage/meter-change/reconcile`

换表账单复核。输入旧表、新表两段各自的起止读数（各带秒精度带时区时间戳）、各自模数与每秒最大速率（**两表模数可以不同**），以及跨两表的账单总用量。**旧表终读与新表初读必须为同一时刻**（换表刻；两块表在该刻的读数本身可以不同），两段内部时间戳均须严格递增；读数、时间戳、模数、速率的校验规则与其他接口完全一致（复用 `Reading` 校验）。

**请求体**

```json
{
  "total_usage": 4750,
  "old_meter": {
    "modulus": 1000,
    "max_rate_per_second": 10,
    "start": { "timestamp": "2026-09-24T00:00:00Z", "value": 900 },
    "end":   { "timestamp": "2026-09-24T00:16:40Z", "value": 50 }
  },
  "new_meter": {
    "modulus": 1500,
    "max_rate_per_second": 10,
    "start": { "timestamp": "2026-09-24T00:16:40Z", "value": 1200 },
    "end":   { "timestamp": "2026-09-24T00:33:20Z", "value": 300 }
  }
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `total_usage` | 整数 | `>= 0`，跨两表的账单总用量 |
| `old_meter` / `new_meter` | 对象 | `modulus >= 1`；`max_rate_per_second >= 0`（支持小数，精确分数计算）；`start` / `end` 为秒精度带时区读数，段内严格递增，`0 <= value < modulus` |
| 换表刻 | — | `old_meter.end.timestamp` 与 `new_meter.start.timestamp` 必须为同一时刻（允许不同时区表达，换算 UTC 后比较） |

**响应（可行且仍有多解，`200`，`status = "ok"`，`unique = false`）**

```json
{
  "status": "ok",
  "total_usage": 4750,
  "unique": false,
  "segments": [
    {
      "meter": "old",
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:16:40Z",
      "start_reading": 900,
      "end_reading": 50,
      "elapsed_seconds": 1000,
      "modulus": 1000,
      "min_wraps": 2,
      "max_wraps": 5,
      "wraps_step": 3,
      "wraps": null,
      "usage": null,
      "min_usage": 1150,
      "max_usage": 4150
    },
    {
      "meter": "new",
      "start_timestamp": "2026-09-24T00:16:40Z",
      "end_timestamp": "2026-09-24T00:33:20Z",
      "start_reading": 1200,
      "end_reading": 300,
      "elapsed_seconds": 1000,
      "modulus": 1500,
      "min_wraps": 1,
      "max_wraps": 3,
      "wraps_step": 2,
      "wraps": null,
      "usage": null,
      "min_usage": 600,
      "max_usage": 3600
    }
  ],
  "conflicts": []
}
```

- `segments` 固定为旧表（`meter = "old"`）、新表（`meter = "new"`）两段。
- `min_wraps` / `max_wraps` 为账单总量联立后该段仍可行的回绕次数范围；可行圈数按固定步长 `wraps_step` 取值（模数归约后的对侧模数 `M对 / gcd`），**所有可行组合严格满足两段用量之和等于 `total_usage`**，故交叉端点亦相等：旧表下界 + 新表上界 = 旧表上界 + 新表下界 = 账单总量。
- `unique`：两段圈数是否**同时**被账单唯一确定。唯一时两段 `min_wraps == max_wraps`，`wraps` / `usage` 给出确定值，`min_usage` / `max_usage` 为 `null`；任一段仍有多解时 `unique = false`，多解段只给范围不猜测（与既有对账接口风格一致）。
- 上例中 `gcd(1000, 1500) = 500`，账单 4750 对应旧表圈数 `k旧 ∈ {2, 5}`、新表圈数 `k新 ∈ {3, 1}`（此消彼长），用量组合为 `(4150, 600)` 与 `(1150, 3600)`。

**两段同时唯一的响应（`unique = true`）**：账单取 `2250` 时

```json
{
  "status": "ok",
  "total_usage": 2250,
  "unique": true,
  "segments": [
    {
      "meter": "old",
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:16:40Z",
      "start_reading": 900,
      "end_reading": 50,
      "elapsed_seconds": 1000,
      "modulus": 1000,
      "min_wraps": 1,
      "max_wraps": 1,
      "wraps_step": 3,
      "wraps": 1,
      "usage": 150,
      "min_usage": null,
      "max_usage": null
    },
    {
      "meter": "new",
      "start_timestamp": "2026-09-24T00:16:40Z",
      "end_timestamp": "2026-09-24T00:33:20Z",
      "start_reading": 1200,
      "end_reading": 300,
      "elapsed_seconds": 1000,
      "modulus": 1500,
      "min_wraps": 2,
      "max_wraps": 2,
      "wraps_step": 2,
      "wraps": 2,
      "usage": 2100,
      "min_usage": null,
      "max_usage": null
    }
  ],
  "conflicts": []
}
```

**响应（冲突，`200`，`status = "conflict"`）**

- `kind = "segment"`，`reason = "no_solution"`：旧表或新表段在非负增量 / 速率上限下原本无解（复用复核接口的逐段判定），`meter` 指明是哪块表；两段都无解时一并列出。存在分段冲突时不再做总量联立，`segments` 为空。
- `kind = "total"`，`reason = "total_incompatible_modulus"`：账单总量不满足丢番图方程的整除条件，即 `total_usage − d旧 − d新` 不被 `g = gcd(M旧, M新)` 整除，不存在整数圈数组合；响应给出 `modulus_gcd`、`expected_remainder`（账单应满足的模 `g` 余数）及 `feasible_min_total` / `feasible_max_total`（不联立账单时两段独立可行用量之和的上下界）。
- `kind = "total"`，`reason = "total_out_of_range"`：方程有整数解但没有一对圈数同时落在两段的可行区间内；`detail` 会区分「总量超出可行盒 `[feasible_min_total, feasible_max_total]`」与「总量在盒内但模 gcd 相容的整数组合落空」两种子情形。

```json
{
  "status": "conflict",
  "total_usage": 4751,
  "unique": false,
  "segments": [],
  "conflicts": [
    {
      "kind": "total",
      "reason": "total_incompatible_modulus",
      "detail": "账单总量与两表模数不相容：总量 B 必须满足 B ≡ d_old + d_new (mod gcd)，其中 gcd(1000, 1500) = 500；收到 4751，除以 500 不整除，两段回绕次数无法同时取整数",
      "old_modulus": 1000,
      "new_modulus": 1500,
      "modulus_gcd": 500,
      "feasible_min_total": 750,
      "feasible_max_total": 18750,
      "expected_remainder": 250
    }
  ]
}
```

请求校验错误（换表刻不同刻、段内时间不递增、缺时区、含亚秒、读数超出该表模数、负速率、账单为负等）返回 `422`。

### `POST /v1/usage/missing-reading`

漏采读数推断。输入同一水表的起止读数（各带秒精度带时区时间戳）、两者之间的一个**漏采时刻**、模数、每秒速率上限与该账期账单总用量。读数、时间戳、模数、速率的校验规则与其他接口完全一致（复用 `Reading` 校验）；`missing_timestamp` 使用同一时间戳校验，且必须**严格介于**起止时刻之间。

**请求体**

```json
{
  "modulus": 1000,
  "max_rate_per_second": 10,
  "total_usage": 300,
  "start": { "timestamp": "2026-09-24T00:00:00Z", "value": 900 },
  "end":   { "timestamp": "2026-09-24T00:01:40Z", "value": 200 },
  "missing_timestamp": "2026-09-24T00:00:40Z"
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `modulus` | 整数 | `>= 1`，计数器模数（回绕周期） |
| `max_rate_per_second` | 数值 | `>= 0`，每秒最大计数增量，支持小数（按精确分数计算） |
| `total_usage` | 整数 | `>= 0`，该账期账单总用量 |
| `start` / `end` | 对象 | 秒精度带时区读数，`0 <= value < modulus`，`end` 晚于 `start` |
| `missing_timestamp` | 字符串 | 秒精度且带时区，严格介于 `start` 与 `end` 时刻之间 |

**响应（可行，`200`，`status = "ok"`）**

```json
{
  "status": "ok",
  "modulus": 1000,
  "total_usage": 300,
  "total_wraps": 1,
  "start_timestamp": "2026-09-24T00:00:00Z",
  "end_timestamp": "2026-09-24T00:01:40Z",
  "missing_timestamp": "2026-09-24T00:00:40Z",
  "start_reading": 900,
  "end_reading": 200,
  "left_seconds": 40,
  "right_seconds": 60,
  "left_capacity": 400,
  "right_capacity": 600,
  "left_usage_min": 0,
  "left_usage_max": 300,
  "candidate_intervals": [
    { "min_reading": 900, "max_reading": 999 },
    { "min_reading": 0, "max_reading": 200 }
  ],
  "candidate_count": 301,
  "unique": false,
  "conflicts": []
}
```

上例中漏采时刻把账期切成左 40s、右 60s 两段，容量分别为 `floor(10×40)=400`、`floor(10×60)=600`；账单 300 与首尾读数差 `-700` 模 1000 同余（隐含总回绕次数 `K=1`）。左侧可行用量为 `[max(0, 300−600), min(400, 300)] = [0, 300]`，候选读数 `(900 + x) mod 1000` 在模数环上形成跨零点的连续弧，拆为 `[900, 999]` 与 `[0, 200]` 两个不重叠闭区间，共 301 个候选。

- `left_usage_min` / `left_usage_max`：左侧（首读数 → 漏采时刻）可行用量闭区间，区间内每个整数都可达到。
- `candidate_intervals`：候选漏采读数的精确、不重叠闭区间，端点含在内且均在 `[0, modulus-1]` 内，按左侧用量递增的环序给出；候选弧跨零点时拆为两段，候选数不少于模数时返回全域 `[0, modulus-1]`（单个区间）。
- `candidate_count`：候选读数个数（去重后的剩余类数，不超过模数）；`unique` 当且仅当候选数为 1。
- `total_wraps`：账单总量隐含的总回绕次数 `K = (total_usage − (end_reading − start_reading)) / modulus`。

**候选唯一（`unique = true`）**：取速率为 `1`、起止读数 `100 → 200`（读数差 100）、账单 `100` 时，两侧容量为 40/60，左侧用量被夹到恰为 40，候选唯一：

```json
{
  "status": "ok",
  "total_wraps": 0,
  "left_usage_min": 40,
  "left_usage_max": 40,
  "candidate_intervals": [ { "min_reading": 140, "max_reading": 140 } ],
  "candidate_count": 1,
  "unique": true
}
```

**响应（冲突，`200`，`status = "conflict"`）**

账单总量与首尾读数差模 `modulus` 不同余（`total_incompatible_modulus`）：

```json
{
  "status": "conflict",
  "total_wraps": null,
  "candidate_intervals": [],
  "candidate_count": 0,
  "unique": false,
  "conflicts": [
    {
      "reason": "total_incompatible_modulus",
      "detail": "账单总量与首尾读数不相容：总量 B 必须满足 B ≡ 300 (mod 1000)（末读数 − 首读数 = -700），收到 301（余数 301），总回绕次数不是整数",
      "expected_remainder": 300,
      "left_capacity": 400,
      "right_capacity": 600,
      "feasible_max_total": 1000
    }
  ]
}
```

账单同余但超出两侧容量之和（`insufficient_capacity`）：

```json
{
  "status": "conflict",
  "conflicts": [
    {
      "reason": "insufficient_capacity",
      "detail": "两侧容量不足：账单总量 1100 超出漏采时刻两侧容量之和 40 + 60 = 100（左侧 40s、右侧 60s 各自的 floor(速率×秒数)），不存在可行的左右侧非负整数用量分配",
      "expected_remainder": null,
      "left_capacity": 40,
      "right_capacity": 60,
      "feasible_max_total": 100
    }
  ]
}
```

- 两种冲突原因可区分：`total_incompatible_modulus` 为账单与模数不相容（`expected_remainder` 给出应有的余数，`total_wraps` 为 `null`）；`insufficient_capacity` 为两侧容量不足（`feasible_max_total` 给出可行账单上界，此时同余成立、`total_wraps` 已知）。
- 冲突时 `candidate_intervals` 为空、`candidate_count` 为 0、`left_usage_min` / `left_usage_max` 为 `null`，**不猜测读数**。
- 请求校验错误（漏采时刻不介于起止之间、缺时区、含亚秒、读数越界、负速率、账单为负或非整数等）返回 `422`。

### `POST /v1/usage/minimum-rate`

最小统一速率上限。输入同一水表的模数、严格递增的秒精度读数序列与账单总用量（**无需给定 `max_rate_per_second`**——本接口正是反求这个速率门槛）；读数、时间戳、模数的校验与 `/v1/usage/verify` 完全一致（复用同一校验逻辑）。先按首尾读数差与模数校验账单同余；相容时，在各段非负整数用量且总和等于账单的约束下，求使所有段「用量 ÷ 历时」均不超过它的最小统一速率上限，以约分后的分子/分母精确返回，并给出该门槛下每段可行的圈数范围与是否唯一。

**请求体**

```json
{
  "modulus": 1000,
  "total_usage": 5000,
  "readings": [
    { "timestamp": "2026-09-24T00:00:00Z", "value": 100 },
    { "timestamp": "2026-09-24T00:16:40Z", "value": 200 },
    { "timestamp": "2026-09-24T00:33:20Z", "value": 100 }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `modulus` | 整数 | `>= 1`，计数器模数（回绕周期） |
| `total_usage` | 整数 | `>= 0`，账单总用量（非负整数） |
| `readings` | 数组 | 至少 2 条；校验规则与 `/v1/usage/verify` 相同（秒精度带时区、严格递增、`0 <= value < modulus`） |

**响应（可行且各段唯一，`200`，`status = "ok"`）**

```json
{
  "status": "ok",
  "modulus": 1000,
  "total_usage": 5000,
  "total_wraps": 5,
  "min_rate_per_second": { "numerator": 29, "denominator": 10 },
  "unique": true,
  "segments": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:16:40Z",
      "start_reading": 100,
      "end_reading": 200,
      "elapsed_seconds": 1000,
      "min_wraps": 2,
      "max_wraps": 2,
      "wraps": 2,
      "usage": 2100,
      "min_usage": null,
      "max_usage": null
    },
    {
      "index": 1,
      "start_timestamp": "2026-09-24T00:16:40Z",
      "end_timestamp": "2026-09-24T00:33:20Z",
      "start_reading": 200,
      "end_reading": 100,
      "elapsed_seconds": 1000,
      "min_wraps": 3,
      "max_wraps": 3,
      "wraps": 3,
      "usage": 2900,
      "min_usage": null,
      "max_usage": null
    }
  ],
  "conflicts": []
}
```

上例中两段读数差为 `+100`、`-100`（最小非负用量 100、900），账单 5000 隐含总回绕次数 `K=5`、待分配额外圈数 `T=4`；最小统一速率上限为 `29/10`（即 2.9/秒，**约分后的精确分数**，不是浮点近似）。该门槛下两段圈数被唯一确定为 2、3，用量 2100、2900（之和恰为账单），各段速率 2.1、2.9，峰值即 `29/10`——任何更低的统一速率都无法让两段非负整数用量之和等于 5000。

**响应（可行但仍有范围，`unique = false`）**：同样的读数全为平读数（`100 → 100 → 100`，历时 1000s、500s）、账单 2000 时

```json
{
  "status": "ok",
  "modulus": 1000,
  "total_usage": 2000,
  "total_wraps": 2,
  "min_rate_per_second": { "numerator": 2, "denominator": 1 },
  "unique": false,
  "segments": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:16:40Z",
      "start_reading": 100,
      "end_reading": 100,
      "elapsed_seconds": 1000,
      "min_wraps": 1,
      "max_wraps": 2,
      "wraps": null,
      "usage": null,
      "min_usage": 1000,
      "max_usage": 2000
    },
    {
      "index": 1,
      "start_timestamp": "2026-09-24T00:16:40Z",
      "end_timestamp": "2026-09-24T00:25:00Z",
      "start_reading": 100,
      "end_reading": 100,
      "elapsed_seconds": 500,
      "min_wraps": 0,
      "max_wraps": 1,
      "wraps": null,
      "usage": null,
      "min_usage": 0,
      "max_usage": 1000
    }
  ],
  "conflicts": []
}
```

- `min_rate_per_second`：最小统一速率上限，以**约分后**的 `numerator` / `denominator` 精确返回（`Fraction` 计算，无浮点误差）。
- `total_wraps`：账单隐含的总回绕次数 `K = (total_usage − (末读数 − 首读数)) / modulus`。
- `segments`：该门槛与账单总量约束后每段仍可行的圈数范围。`min_wraps == max_wraps` 的段圈数唯一，`wraps` / `usage` 给出确定值、`min_usage` / `max_usage` 为 `null`；仍有多解的段反之，**只给范围不虚构单段用量**。所有可行组合的两段用量之和恒等于 `total_usage`（上例可行组合为 `(k0, k2) ∈ {(1,1), (2,0)}`，即用量 `(1000,1000)` 或 `(2000,0)`）。
- `unique`：各段圈数是否全部被唯一确定。

**响应（冲突，`200`，`status = "conflict"`）**

账单总量与首尾读数差模 `modulus` 不同余（`total_incompatible_modulus`）：

```json
{
  "status": "conflict",
  "modulus": 1000,
  "total_usage": 5500,
  "total_wraps": null,
  "min_rate_per_second": null,
  "unique": false,
  "segments": [],
  "conflicts": [
    {
      "kind": "total",
      "reason": "total_incompatible_modulus",
      "detail": "账单总量与模数不相容：总量 B 必须满足 B ≡ 0 (mod 1000)（首尾读数差为 0），收到 5500（余数 500），总回绕次数不是整数",
      "feasible_min_total": 1000,
      "feasible_max_total": null,
      "expected_remainder": 0,
      "total_wraps": null
    }
  ]
}
```

账单同余但低于可行最小总量（`total_out_of_range`）：读数 `900 → 100 → 900 → 100`（各 10s）时，各段最小非负用量之和已为 1200，账单 200 无法解释：

```json
{
  "status": "conflict",
  "modulus": 1000,
  "total_usage": 200,
  "total_wraps": 1,
  "min_rate_per_second": null,
  "unique": false,
  "segments": [],
  "conflicts": [
    {
      "kind": "total",
      "reason": "total_out_of_range",
      "detail": "账单总量低于可行最小总量：各段取满足非负增量的最小圈数时，总用量已为 1200（模数 1000），收到 200；速率上限不设约束时可行总量没有上界，但不能低于该最小值",
      "feasible_min_total": 1200,
      "feasible_max_total": null,
      "expected_remainder": null,
      "total_wraps": 1
    }
  ]
}
```

- `total_incompatible_modulus`：账单与模数不相容，`expected_remainder` 给出应有的模 M 余数，`total_wraps` 为 `null`。
- `total_out_of_range`：账单同余但低于可行最小总量 `feasible_min_total`（各段取满足非负增量的最小圈数时的总量）；由于速率不设上限，可行总量为 `[feasible_min_total, +∞)`，故 `feasible_max_total` 恒为 `null`。
- 冲突时 `min_rate_per_second` 为 `null`、`segments` 为空。请求校验错误（读数越界、时间不递增、缺时区、亚秒、读数不足 2 条、账单为负或非整数、模数 < 1 等）返回 `422`。

### `POST /v1/usage/dual-meter/compare`

双表同段交叉核验。输入两块同时计量同一用量的水表各自的模数、每秒速率上限与首末秒精度读数（**两表模数可以不同**），**两表的起止时刻必须分别相同**（允许不同时区表达，换算 UTC 后比较）；读数、时间戳、模数、速率的校验规则与其他接口完全一致（复用 `Reading` / `MeterBlock` 校验）。各表用量须非负且不超速；接口按两表读数差的模数同余联立共同用量（中国剩余定理），并与两表可行用量范围求交，返回共同用量的最小值、最大值、候选数与唯一性，**不逐个枚举回绕圈数**。

**请求体**

```json
{
  "meter_a": {
    "modulus": 1000,
    "max_rate_per_second": 10,
    "start": { "timestamp": "2026-09-24T00:00:00Z", "value": 900 },
    "end":   { "timestamp": "2026-09-24T00:16:40Z", "value": 100 }
  },
  "meter_b": {
    "modulus": 1500,
    "max_rate_per_second": 10,
    "start": { "timestamp": "2026-09-24T00:00:00Z", "value": 1200 },
    "end":   { "timestamp": "2026-09-24T00:16:40Z", "value": 400 }
  }
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `meter_a` / `meter_b` | 对象 | `modulus >= 1`；`max_rate_per_second >= 0`（支持小数，精确分数计算）；`start` / `end` 为秒精度带时区读数，段内严格递增，`0 <= value < modulus` |
| 共同时段 | — | `meter_a.start.timestamp` 与 `meter_b.start.timestamp` 必须为同一时刻，`meter_a.end.timestamp` 与 `meter_b.end.timestamp` 必须为同一时刻 |

**响应（可行且有 3 个候选，`200`，`status = "ok"`）**

```json
{
  "status": "ok",
  "start_timestamp": "2026-09-24T00:00:00Z",
  "end_timestamp": "2026-09-24T00:16:40Z",
  "elapsed_seconds": 1000,
  "modulus_gcd": 500,
  "usage_step": 3000,
  "min_usage": 2200,
  "max_usage": 8200,
  "candidate_count": 3,
  "unique": false,
  "meters": [
    {
      "meter": "a",
      "modulus": 1000,
      "start_reading": 900,
      "end_reading": 100,
      "min_wraps": 1,
      "max_wraps": 10,
      "min_usage": 200,
      "max_usage": 9200
    },
    {
      "meter": "b",
      "modulus": 1500,
      "start_reading": 1200,
      "end_reading": 400,
      "min_wraps": 1,
      "max_wraps": 7,
      "min_usage": 700,
      "max_usage": 9700
    }
  ],
  "conflicts": []
}
```

上例中两表读数差均为 `-800`，模 `gcd(1000, 1500) = 500` 同余；共同用量须满足 `u ≡ 2200 (mod 3000)`（`3000 = lcm(1000, 1500)`），两表可行范围之交为 `[700, 9200]`，故共同候选为 `2200、5200、8200` 三项——每个候选唯一对应两表各自圈数（如 `u = 2200` 对应表 A 3 圈、表 B 2 圈），候选数再多也不逐个枚举。

- `min_usage` / `max_usage`：共同用量候选闭区间端点（均可达到）。
- `usage_step`：相邻候选之差 `lcm(M_a, M_b)`；全部候选为 `min_usage + i × usage_step`（`i = 0 .. candidate_count - 1`）。
- `candidate_count`：候选个数；`unique` 当且仅当候选数为 1（此时 `min_usage == max_usage`）。
- `meters`：两表各自在非负增量与速率上限下的可行圈数/用量范围（联立前的独立范围），按表 A、表 B 顺序。

**候选唯一（`unique = true`）**：上例中表 B 速率改为 `5` 时，表 B 可行用量收窄为 `[700, 3700]`，交集内仅剩候选 `2200`：`min_usage = max_usage = 2200`、`candidate_count = 1`。

**响应（冲突，`200`，`status = "conflict"`）**

两表读数差模 `gcd` 不同余（`incompatible_modulus`）：表 B 末读数改为 `500`（读数差 `-700`）时

```json
{
  "status": "conflict",
  "modulus_gcd": 500,
  "usage_step": 3000,
  "min_usage": null,
  "max_usage": null,
  "candidate_count": 0,
  "unique": false,
  "meters": [],
  "conflicts": [
    {
      "kind": "common",
      "reason": "incompatible_modulus",
      "detail": "两表读数差同余不相容：共同用量须同时满足 u ≡ -800 (mod 1000) 且 u ≡ -700 (mod 1500)，即两读数差模 gcd(1000, 1500) = 500 同余；但二者模 500 的余数分别为 200、300，不存在任何共同用量，两表不可能一致",
      "modulus_gcd": 500,
      "usage_step": 3000,
      "expected_remainder": 200,
      "a_usage_min": 200,
      "a_usage_max": 9200,
      "b_usage_min": 800,
      "b_usage_max": 9800,
      "intersect_min": 800,
      "intersect_max": 9200
    }
  ]
}
```

同余相容但范围无交集（`range_disjoint`）：表 A 速率改为 `1` 时其可行用量仅为 `[200, 200]`，与表 B 的 `[700, 9700]` 不相交

```json
{
  "kind": "common",
  "reason": "range_disjoint",
  "detail": "两表可行用量范围无交集：表 A 可行用量 [200, 200]（模数 1000），表 B 可行用量 [700, 9700]（模数 1500），区间交集为空，不存在共同用量，两表不可能一致",
  "expected_remainder": null
}
```

若区间相交但交集中没有同余点（如表 B 速率改为 `2`，可行用量仅 `[700, 700]`，而最近候选为 `2200`），`reason` 仍为 `range_disjoint`，`detail` 会说明「不小于交集下界的最小候选已超出交集上界」，与区间本身不交的情形可区分。

- `kind = "segment"`，`reason = "no_solution"`：某表段在非负增量 / 速率上限下原本无解（复用逐段判定），`meter` 指明是哪块表；两表都无解时一并列出。存在分段冲突时不再联立，`meters` 为空。
- `kind = "common"`，`reason = "incompatible_modulus"`：两表读数差模 `gcd(M_a, M_b)` 不同余，不存在任何共同用量；`expected_remainder` 给出两表读数差应共有的模 gcd 余数（以表 A 为准）。
- `kind = "common"`，`reason = "range_disjoint"`：同余相容但两表可行用量范围之交内没有共同候选（区间不交或交集内无同余点），与 `incompatible_modulus` 是可区分的不同原因。

请求校验错误（两表起止时刻不分别相同、段内时间不递增、缺时区、含亚秒、读数超出该表模数、负速率、模数 < 1 等）返回 `422`。

### `POST /v1/billing/charge-range`

分时单价账单金额区间。请求体在账单对账接口字段基础上增加 `unit_prices`：按**相邻读数段一一对应**的非负十进制分时单价，数量必须等于段数（`readings` 数 − 1），第 `i` 项对应第 `i` 对相邻读数。读数、时间戳、模数、速率与 `total_usage` 的校验与 `/v1/usage/reconcile` 完全一致（复用同一校验）；单价可以 JSON 数字或字符串给出，服务端一律按 `Decimal` 精确解析，**不用浮点**。

接口先逐段求满足非负增量与速率上限的回绕整数区间（复用读数/模数/速率判定），某段无解即以分段冲突返回、不做总量推断；各段均可行后以账单总用量做整数区间对账（与 `/v1/usage/reconcile` 同一 `reconcile_total` 逻辑），账单与模数不同余（**总量同余不相容**）或总回绕次数超出各段区间和（**总量超界**）分别给出可区分原因。

**请求体**

```json
{
  "modulus": 1000,
  "max_rate_per_second": 10,
  "total_usage": 5000,
  "unit_prices": ["2.50", "1.25"],
  "readings": [
    { "timestamp": "2026-09-24T00:00:00Z", "value": 100 },
    { "timestamp": "2026-09-24T00:16:40Z", "value": 200 },
    { "timestamp": "2026-09-24T00:33:20Z", "value": 100 }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `unit_prices` | 数组 | 非负有限十进制单价的数组（推荐用字符串避免 JSON 数字歧义，如 `"2.50"`；数字形式同样按精确十进制解析）；**数量必须恰为段数（读数数 − 1）**，拒绝负数、`NaN`、`Infinity` |
| 其余字段 | — | 与 `/v1/usage/reconcile` 相同（`modulus` / `max_rate_per_second` / `total_usage` / `readings`） |

**响应（可行，`200`，`status = "ok"`）**

```json
{
  "status": "ok",
  "modulus": 1000,
  "total_usage": 5000,
  "total_wraps": 5,
  "segments": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:16:40Z",
      "start_reading": 100,
      "end_reading": 200,
      "elapsed_seconds": 1000,
      "min_wraps": 0,
      "max_wraps": 4,
      "wraps": null,
      "usage": null,
      "min_usage": 100,
      "max_usage": 4100,
      "unit_price": "2.50"
    },
    {
      "index": 1,
      "start_timestamp": "2026-09-24T00:16:40Z",
      "end_timestamp": "2026-09-24T00:33:20Z",
      "start_reading": 200,
      "end_reading": 100,
      "elapsed_seconds": 1000,
      "min_wraps": 1,
      "max_wraps": 5,
      "wraps": null,
      "usage": null,
      "min_usage": 900,
      "max_usage": 4900,
      "unit_price": "1.25"
    }
  ],
  "minimum": {
    "total_amount": "6375.00",
    "allocations": [
      { "index": 0, "wraps": 0, "usage": 100, "amount": "250.00" },
      { "index": 1, "wraps": 5, "usage": 4900, "amount": "6125.00" }
    ]
  },
  "maximum": {
    "total_amount": "11375.00",
    "allocations": [
      { "index": 0, "wraps": 4, "usage": 4100, "amount": "10250.00" },
      { "index": 1, "wraps": 1, "usage": 900, "amount": "1125.00" }
    ]
  },
  "conflicts": []
}
```

上例账单 5000 隐含总圈数 `K = 5`；收紧后段 0 圈数 `[0,4]`、段 1 圈数 `[1,5]`，各段先取最小圈数后剩余 `T = 4` 个圈待分配。段 1 单价 `1.25` 更低，**最低金额**把 4 个剩余圈全部给段 1（用量 `4900`）：`100×2.50 + 4900×1.25 = 6375.00`；**最高金额**把 4 个圈全部给段 0（用量 `4100`）：`4100×2.50 + 900×1.25 = 11375.00`。

- `segments`：账单总量约束后各段的圈数/用量范围与该段分时单价（字段同 `/v1/usage/reconcile`，另加规范化十进制字符串 `unit_price`）。
- `minimum` / `maximum`：最低/最高应收金额方案。`total_amount` 为十进制字符串（非负、精确值）；`allocations` 按段索引升序给出该方案下每段的 `wraps` / `usage` / `amount`。两个方案的各段用量之和都**恒等于 `total_usage`**、圈数之和恒等于 `total_wraps`。
- 每段金额按**该段单价的小数位**定标（如单价 `0.1` 的段金额写作 `"10.0"`）；`total_amount` 取各段单价最大小数位对齐后精确求和（如 `"59.00"`），不会出现浮点尾数。

**极值的贪心计算（不枚举组合、不用浮点）**

段 `i` 用量 `u_i = diff_i + k_i·M`，金额 `A = Σ p_i·u_i = Σ p_i·diff_i + M·Σ p_i·(k_i − lo_i)`。第一项与圈数分配无关；剩余圈数 `T = K − Σ lo_i` 是线性目标：

- 最低金额：段按单价**从低到高**排序（单价以分数交叉相乘比较大小，无浮点），依次把该段余量 `hi_i − lo_i` 填满，直到 `T` 个圈用完；
- 最高金额：段按单价**从高到低**排序，同样贪心；
- 单价相同的段按段索引升序填充，保证方案确定（同价段间任意分配金额相同）。

各段单价小数位不同时，金额一律按十进制分子做整数运算（如 `2.50 → 250/100`），最后格式化为十进制字符串。

**响应（冲突，`200`，`status = "conflict"`）**

冲突结构与 `/v1/usage/reconcile` 完全一致（`conflicts` 复用同一模型），三类原因可区分：

- `kind = "segment"`，`reason = "no_solution"`：某段在非负增量/速率上限下原本无解（复用逐段判定）；存在分段冲突时不做总量与金额推断，`segments` 为空、`minimum` / `maximum` 为 `null`、`total_wraps` 为 `null`。
- `kind = "total"`，`reason = "total_incompatible_modulus"`：账单总量与首尾读数差模 `modulus` 不同余（**总量同余不相容**），总回绕次数不是整数；`expected_remainder` 给出应有余数，`total_wraps` 为 `null`。
- `kind = "total"`，`reason = "total_out_of_range"`：同余成立但总回绕次数超出 `[Σk_min, Σk_max]`（**总量超界**），即账单不在 `[feasible_min_total, feasible_max_total]` 内；`total_wraps` 给出账单隐含的 `K`。

总量冲突时 `segments` 为空、`minimum` / `maximum` 为 `null`。请求校验错误（单价数量与段数不符、单价为负/`NaN`/`Infinity`，以及读数越界、时间不递增、缺时区、含亚秒、负速率、账单为负或非整数等）返回 `422`。

### `POST /v1/usage/clean-readings`

异常采样清理。请求体字段与 `/v1/usage/verify` **完全相同**（`modulus` / `max_rate_per_second` / `readings`，读数、模数、速率的校验也完全一致，复用同一校验）。接口把**任意两条**读数 `(r_i, t_i)`、`(r_j, t_j)`（`i < j`）视为候选相邻读数，按与逐段复核相同的规则判定物理可行性：存在非负整数回绕次数 `k` 使增量

```
(r_j − r_i) + k × modulus >= 0  且  <= max_rate_per_second × (t_j − t_i)
```

**首尾读数必须保留**；在此前提下求**删除最少内部读数**的完整序列。多组最优解（删除数相同的不同保留序列）按**保留索引序列字典序**选定。首末读数在该速率与模数约束下无法连通（不存在任何合法保留序列）时返回明确的无解状态。

**请求体**

```json
{
  "modulus": 1000,
  "max_rate_per_second": 10,
  "readings": [
    { "timestamp": "2026-09-24T00:00:00Z", "value": 0 },
    { "timestamp": "2026-09-24T00:00:10Z", "value": 100 },
    { "timestamp": "2026-09-24T00:00:20Z", "value": 50 },
    { "timestamp": "2026-09-24T00:00:30Z", "value": 150 }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| 字段同 `/v1/usage/verify` | — | `modulus` / `max_rate_per_second` / `readings` 的类型与校验完全复用（至少 2 条、秒精度带时区、严格递增、`0 <= value < modulus`、速率非负） |

**响应（可行，`200`，`status = "ok"`）**

上例中读数 1→2 为 `100 → 50`（回绕后增量 950，超出 10s 容量 100）不可相邻保留；但 `0 → 1 → 3` 与 `0 → 2 → 3` 都是只需删除 1 条的完整序列，两组最优解按保留索引序列字典序选定 `[0, 1, 3]`：

```json
{
  "status": "ok",
  "modulus": 1000,
  "reading_count": 4,
  "kept_indices": [0, 1, 3],
  "removed_indices": [2],
  "removed_count": 1,
  "detail": null
}
```

- `kept_indices`：保留读数的索引（升序），**必含首索引 `0` 与末索引**；相邻两项对应的读数对均物理可行。
- `removed_indices`：删除的内部读数索引（升序，不含首尾）；无内部读数可删时为 `[]`。
- `removed_count`：删除的内部读数条数，恒满足 `removed_count + len(kept_indices) = reading_count`。
- 全部相邻读数本来就物理可行时保留全部读数，`removed_count = 0`。
- 字典序规则：保留序列等长时逐位比较，**尽早保留较小的索引**；例如 `[0, 1, 3]` 与 `[0, 2, 3]` 同为最优时选 `[0, 1, 3]`。

**响应（首尾无法连通，`200`，`status = "no_solution"`）**

即使允许删除任意内部读数组合，首读数到末读数之间仍无两两物理可行的路径时（如读数 `0 → 500 → 900`、各间隔 10s、速率 10/s，三对候选相邻关系均超速，首读数无法到达末读数）：

```json
{
  "status": "no_solution",
  "modulus": 1000,
  "reading_count": 3,
  "kept_indices": [],
  "removed_indices": [],
  "removed_count": null,
  "detail": "无解：在每秒速率上限与模数 1000 的回绕约束下，首读数（索引 0）与末读数（索引 2）之间不存在任何两两相邻物理可行的保留序列（首尾必须保留），删除任意内部读数组合都无法连通首尾"
}
```

- 无解时 `kept_indices` / `removed_indices` 为空、`removed_count` 为 `null`，`detail` 给出明确说明，**不编造删除方案**。
- 请求校验错误（读数越界、时间不递增、缺时区、含亚秒、读数不足 2 条、负速率、模数 < 1 等）返回 `422`，与 `/v1/usage/verify` 完全一致。

### `POST /v1/usage/master-sub/loss-reconcile`

总分表漏损复核。输入**同一模数**的一块总表（`master`）与**至少一块分表**（`sub_meters`），各表共用**同一组**秒精度、带时区且严格递增的时间点（读数条数相同、同位置时刻换算 UTC 后必须一致），并给出各表对应的读数与各自的每秒速率上限（速率可各表不同），以及给定的整期漏损总量 `total_loss`。读数、时间戳、模数、速率的校验规则与其他接口完全一致（复用 `Reading` 同一时间戳校验）。

**请求体**

```json
{
  "modulus": 1000,
  "total_loss": 600,
  "master": {
    "name": "总表",
    "max_rate_per_second": 100,
    "readings": [
      { "timestamp": "2026-09-24T00:00:00Z", "value": 0 },
      { "timestamp": "2026-09-24T00:00:10Z", "value": 600 },
      { "timestamp": "2026-09-24T00:00:20Z", "value": 200 }
    ]
  },
  "sub_meters": [
    {
      "name": "分表A",
      "max_rate_per_second": 100,
      "readings": [
        { "timestamp": "2026-09-24T00:00:00Z", "value": 0 },
        { "timestamp": "2026-09-24T00:00:10Z", "value": 500 },
        { "timestamp": "2026-09-24T00:00:20Z", "value": 600 }
      ]
    }
  ]
}
```

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `modulus` | 整数 | `>= 1`，总表与各分表**共用同一**计数器模数 |
| `total_loss` | 整数 | `>= 0`，给定的整期漏损总量 |
| `master` / `sub_meters[].max_rate_per_second` | 数值 | `>= 0`，该表每秒速率上限（支持小数，精确分数计算）；各表可不同 |
| `master` / `sub_meters[].name` | 字符串 | 可选，仅用于结果标识；缺省为 `null` |
| `master` / `sub_meters[].readings` | 数组 | 至少 2 条；各表**读数条数相同**，同位置时刻换算 UTC 后必须**完全一致**；表内时刻严格递增，`0 <= value < modulus` |
| `sub_meters` | 数组 | **至少一块**分表 |

**响应（各段漏损唯一，`200`，`status = "ok"`）**

上例总表两段用量均为 `600`（第二段 `600 → 200` 回绕 1 圈：`-400 + 1000`），分表两段用量为 `500`、`100`，故段漏损为 `100`、`500`，整期恰为 `600`：

```json
{
  "status": "ok",
  "modulus": 1000,
  "total_loss": 600,
  "total_wraps": 1,
  "meters": [
    {
      "role": "master",
      "index": null,
      "name": "总表",
      "max_rate_per_second": "100",
      "segments": [
        { "index": 0, "start_timestamp": "2026-09-24T00:00:00Z", "end_timestamp": "2026-09-24T00:00:10Z",
          "start_reading": 0, "end_reading": 600, "elapsed_seconds": 10,
          "min_wraps": 0, "max_wraps": 0, "min_usage": 600, "max_usage": 600 },
        { "index": 1, "start_timestamp": "2026-09-24T00:00:10Z", "end_timestamp": "2026-09-24T00:00:20Z",
          "start_reading": 600, "end_reading": 200, "elapsed_seconds": 10,
          "min_wraps": 1, "max_wraps": 1, "min_usage": 600, "max_usage": 600 }
      ]
    },
    {
      "role": "sub",
      "index": 0,
      "name": "分表A",
      "max_rate_per_second": "100",
      "segments": [
        { "index": 0, "start_reading": 0, "end_reading": 500, "elapsed_seconds": 10,
          "min_wraps": 0, "max_wraps": 0, "min_usage": 500, "max_usage": 500 },
        { "index": 1, "start_reading": 500, "end_reading": 600, "elapsed_seconds": 10,
          "min_wraps": 0, "max_wraps": 0, "min_usage": 100, "max_usage": 100 }
      ]
    }
  ],
  "segments": [
    {
      "index": 0,
      "start_timestamp": "2026-09-24T00:00:00Z",
      "end_timestamp": "2026-09-24T00:00:10Z",
      "elapsed_seconds": 10,
      "min_loss": 100,
      "max_loss": 100,
      "unique": true,
      "loss": 100,
      "master_usage_min": 600,
      "master_usage_max": 600,
      "sub_usage_min": 500,
      "sub_usage_max": 500
    },
    {
      "index": 1,
      "start_timestamp": "2026-09-24T00:00:10Z",
      "end_timestamp": "2026-09-24T00:00:20Z",
      "elapsed_seconds": 10,
      "min_loss": 500,
      "max_loss": 500,
      "unique": true,
      "loss": 500,
      "master_usage_min": 600,
      "master_usage_max": 600,
      "sub_usage_min": 100,
      "sub_usage_max": 100
    }
  ],
  "unique": true,
  "conflicts": []
}
```

- `meters`：总表（`role = "master"`，`index = null`）与各分表（`role = "sub"`，`index` 为其在 `sub_meters` 中的下标，按下标升序）各自在**联立总量前**的独立可行圈数/用量范围（字段同其他接口的分段范围）。
- `segments`：整期漏损总量联立后各段漏损。`unique = true`（`min_loss == max_loss`）时 `loss` 给出确定漏损、`min_loss` / `max_loss` 与其相等；仍有多解时 `loss` 为 `null`，只给非负漏损上下界，**不猜测**。
- `master_usage_min/max`、`sub_usage_min/max`：该段总表用量与各分表用量之和的独立可行范围（联立前）；漏损界是在「总表取大、分表取小」等组合下的精确可达界。
- `total_wraps`：整期总表与分表圈数差总和 `W = (total_loss − ΣD_i) / modulus`（`D_i` 为该段总表读数差减各分表读数差之和；`W` 可正可负，为负表示整期分表累计圈数更多但各段漏损仍可非负）。
- 所有可行组合的各段漏损之和恒等于 `total_loss`，故**交叉端点相等**：某段漏损下界 + 其余段漏损上界 = 整期总量。

**仍有多解（`unique = false`）的情形**：总表读数 `100 → 200 → 100`、分表 `0 → 500 → 0`（各段均 1000s、速率均为 10），整期漏损 `2000` 时两段漏损分别为 `[600, 1600]`、`[400, 1400]`（可行组合 `(600, 1400)` 与 `(1600, 400)`，和恒为 `2000`）；整期漏损取可行端点 `1000` 或 `18000` 时两段全部唯一。

**响应（冲突，`200`，`status = "conflict"`）**

四类冲突原因可区分（按校验先后）：

1. **单表无解**（`kind = "meter_segment"`，`reason = "no_solution"`）：某块表的某段在非负增量 / 该表速率上限下原本无解（复用逐段判定）；`role` 为 `master` / `sub`，分表另给 `meter_index`，多块分表可定位。存在该冲突时不再进行漏损联立，`segments` 为空；`meters` 仍照常返回以便排查。

   ```json
   {
     "kind": "meter_segment",
     "role": "master",
     "index": 0,
     "meter_index": null,
     "name": "总表",
     "reason": "no_solution",
     "detail": "总表第 0 段无解：无解：最可能增量 600 已超出该区间 10s 内允许的最大增量 10（k 需同时满足 k>=0 与 k<=-1，区间为空）",
     "min_wraps": 0,
     "max_wraps": -1
   }
   ```

2. **单段漏损无法非负**（`kind = "loss_segment"`，`reason = "loss_segment_negative"`）：该段总表在任何回绕组合下的最小用量仍小于各分表用量之和的最小值。响应给出该段读数差 `D_i`（`diff = master_reading_diff − sub_reading_diff_sum`）、圈数差 `w_i = k_主 − Σk_分` 的连续可行区间 `[min_wraps, max_wraps]` 与非负漏损要求的下界 `required_min_wraps = ceil(−D_i / M)`（后者大于上界即无解）。

   ```json
   {
     "kind": "loss_segment",
     "index": 0,
     "reason": "loss_segment_negative",
     "master_reading_diff": 100,
     "sub_reading_diff_sum": 500,
     "diff": -400,
     "min_wraps": 0,
     "max_wraps": 0,
     "required_min_wraps": 1
   }
   ```

3. **总量同余冲突**（`kind = "total"`，`reason = "total_incompatible_modulus"`）：整期漏损 `L` 必须满足 `L ≡ ΣD_i (mod modulus)`；`expected_remainder` 给出应有余数，`total_wraps` 为 `null`。

4. **总量超界**（`kind = "total"`，`reason = "total_out_of_range"`）：同余成立但 `W` 超出各段非负圈数差区间之和；`feasible_min_total` / `feasible_max_total` 给出整期可行漏损的上下界（各段非负漏损下界/上界之和），`total_wraps` 给出该总量隐含的 `W`。

   ```json
   {
     "kind": "total",
     "reason": "total_out_of_range",
     "detail": "整期漏损总量超出可行范围：……整期漏损只能在 [1000, 18000]（模数 1000）内取与 ΣD 模 1000 同余的值，收到 0",
     "feasible_min_total": 1000,
     "feasible_max_total": 18000,
     "expected_remainder": null,
     "total_wraps": 0
   }
   ```

冲突优先级：先逐表判单表无解（列出全部无解段），再逐段判漏损非负，最后才做整期同余与超界校验。请求校验错误（各表读数条数不一致、同位置时刻不同、读数越界、表内时间不递增、缺时区、含亚秒、分表数为 0、负速率、`total_loss` 为负或非整数、模数 < 1 等）返回 `422`。

## 判定规则

对每段相邻读数 `(r1, t1) -> (r2, t2)`，真实增量为 `delta = (r2 - r1) + k * modulus`，其中 `k >= 0` 为整圈回绕次数。约束：

1. 非负增量：`delta >= 0`
2. 速率上限：`delta <= max_rate_per_second * (t2 - t1)`

可行 `k` 构成连续整数区间 `[k_min, k_max]`：

- `k_max < k_min` → 无解（`no_solution`）
- `k_max == k_min` → 唯一解，取该 `k` 计算用量
- `k_max > k_min` → 多解（`ambiguous`），不猜测圈数

### 账单总量对账

设账单总用量为 `B`。各段增量望远镜相消，总量恒等式为：

```
B = Σ delta_i = (r_last - r_first) + modulus * K
```

其中 `K = Σ k_i` 为整条序列的回绕次数总和。因此：

1. `B - (r_last - r_first)` 必须为 `modulus` 的非负整数倍，否则账单总量与模数不相容（`total_incompatible_modulus`）；
2. `K` 必须落在 `[Σ k_min, Σ k_max]` 内，否则超出可行总量（`total_out_of_range`，可行总量区间随之给出）。

固定 `K` 后，由「其余各段圈数之和 = `K - k_i`」的区间和直接反推每段仍可行的圈数范围（**整数区间运算，不枚举组合**）：

```
lo_i' = max(k_min_i, K - Σ_{j≠i} k_max_j)
hi_i' = min(k_max_i, K - Σ_{j≠i} k_min_j)
```

`lo_i' == hi_i'` 的段圈数唯一、确定用量；其余段返回 `[lo_i', hi_i']` 及对应用量范围，不做猜测。

### 停水时段账单复核

停水时段全部按**左闭右开** `[start, end)` 处理。预处理两步：

1. **裁剪到读数账期**：每个停水时段与 `[t_first, t_last)` 求交（`max(start, t_first)`、`min(end, t_last)`），完全在账期外或裁剪后为空者丢弃；
2. **合并重叠或相接**：按开始时刻排序，当前时段 `start <=` 已合并区间的右端点即并入（故 `[a,b)` 与 `[b,c)` 相接合并为 `[a,c)`）。

对每段相邻读数 `(r1, t1) -> (r2, t2)`，从 `[t1, t2)` 中扣除落在其内的停水时段，剩余若干连续供水片段，第 `j` 片段时长 `s_j` 秒、容量

```
c_j = floor(max_rate_per_second × s_j)
```

**各片段分别取整后求和**作为该段整数用量容量 `C = Σ c_j`——不能跨停水时段合并取整：`Σ floor(速率 × s_j) <= floor(速率 × Σ s_j)`，停水切断了连续供水，各片段不足一单位的取整余量无法互相补足。例如速率 `0.5/秒` 时两个 3s 片段容量为 `1 + 1 = 2`，而同样 6 个供水秒若连续则容量为 `floor(3) = 3`。

与每日子段同理，非负整数增量 `delta = (r2 - r1) + k × modulus` 能以非负整数分配到各供水片段（`0 <= x_j <= c_j`、`Σ x_j = delta`）当且仅当 `delta <= C`，故可行圈数为连续整数区间：

```
k_min = ceil(max(0, r1 - r2) / modulus)
k_max = floor((C - (r2 - r1)) / modulus)
```

`k_max < k_min` 即**单段无解**（`no_solution`）。全部段可行后，账单总用量的联立收紧与「账单总量对账」完全相同（同一整数区间公式，**不枚举圈数组合**）：账单与首尾读数差模 `modulus` 不同余即**账单同余冲突**（`total_incompatible_modulus`；停水不影响同余）；总回绕次数超出 `[Σ k_min, Σ k_max]` 即**总量超界**（`total_out_of_range`，可行盒的上下界按停水收缩后的各段容量计算）。

整段停水（无供水片段）时 `C = 0`：平读数（最小非负增量为 0）唯一对应用量 0，任何回绕读数（最小增量为正）均无解。左闭右开边界下，与读数端点相接的停水不会重复扣减，各供水片段秒数之和恰为 `supply_seconds`。

### 换表账单复核（两表模数可不同）

旧表、新表两段独立，模数 `M1`、`M2` 可以不同。两段真实用量为

```
u1 = d1 + k1·M1 （d1 = 旧表终读 − 旧表初读）
u2 = d2 + k2·M2 （d2 = 新表终读 − 新表初读）
```

`k1, k2` 各自落在由非负增量与速率上限求出的整数区间 `[lo1, hi1]`、`[lo2, hi2]` 内（两段分别求解，互不影响）。账单总量 `B` 要求

```
u1 + u2 = B  =>  M1·k1 + M2·k2 = N，其中 N = B − d1 − d2
```

这是二元一次丢番图方程，按以下方式**精确联立，不枚举圈数组合**：

1. 方程有整数解当且仅当 `g = gcd(M1, M2)` 整除 `N`；否则账单与两表模数不相容（`total_incompatible_modulus`），相容账单须满足 `B ≡ d1 + d2 (mod g)`。
2. 由扩展欧几里得算法取一组特解 `(k10, k20)`，全部整数解为单参数族：

   ```
   k1 = k10 + (M2/g)·t，k2 = k20 − (M1/g)·t，t ∈ Z
   ```

3. 两段圈数区间各给出 `t` 的两个不等式，取交得到连续整数区间 `[t_min, t_max]`：

   ```
   t ≥ ceil((lo1 − k10) / (M2/g))，t ≤ floor((hi1 − k10) / (M2/g))
   t ≥ ceil((k20 − hi2) / (M1/g))，t ≤ floor((k20 − lo2) / (M1/g))
   ```

   `t_min > t_max` 即联立超界（`total_out_of_range`）——注意这与「用量盒 `[lo1·M1+d1+lo2·M2+d2, hi1·M1+d1+hi2·M2+d2]`」并不等价：盒内但不被 `g` 相容的格点支撑的总量仍会无解，接口 `detail` 对两种子情形分别说明。
4. `t_min == t_max` 时两段圈数同时唯一（`unique = true`）；否则 `k1` 按步长 `M2/g`、`k2` 按步长 `M1/g` 取等差数列，端点即各段精确用量上下界。由于每个可行 `t` 都严格满足 `u1 + u2 = B`，两段范围此消彼长：`u1 下界 + u2 上界 = u1 上界 + u2 下界 = B`。

全程仅用整除、`ceil/floor` 与一次扩展欧几里得，无浮点（速率上限仍由 `Fraction` 精确计算），圈数区间再大也与枚举量无关。`M1 == M2` 时 `g = M`、步长均为 1，自然退化为统一模数的总量对账规则。

### 每日用量上下界

对读数区间 `(r1, t1) -> (r2, t2)`，按 UTC 午夜切成子段，第 `j` 子段时长 `s_j` 秒、容量

```
c_j = floor(max_rate_per_second × s_j)
```

区间真实增量仍为 `delta = (r2 - r1) + k × modulus`，其中 `k >= 0` 为整数。记 `C = Σ c_j`，则增量能以非负整数分配到各子段（`0 <= x_j <= c_j`，`Σ x_j = delta`）当且仅当 `delta <= C`：容量均为整数，`[0, C]` 内任意整数总量都可逐子段填满。故可行圈数为连续整数区间：

```
k_min = ceil(max(0, r1 - r2) / modulus)
k_max = floor((C - (r2 - r1)) / modulus)
```

`k_max < k_min` 即无可行分配（`no_feasible_allocation`）。注意切日分别取整后 `C` 可能小于 `floor(速率 × 整段秒数)`，因此整段速率判定可行的区间仍可能在此冲突。

对固定子段 `j`，记其余子段容量之和为 `C_{-j} = C - c_j`，给定可行 `k` 时其边际范围为

```
max(0, delta - C_{-j}) <= x_j <= min(c_j, delta)
```

界随 `delta`（即随 `k`）单调增，故子段的精确下界在 `k_min` 处取得、精确上界在 `k_max` 处取得，且每个端点都确实存在完整分配达到：

```
x_j 下界 = max(0, (r2-r1) + k_min×M - C_{-j})
x_j 上界 = min(c_j,    (r2-r1) + k_max×M)
```

同一天内多个独立读数区间的子段界直接求和，即得该日 `min_usage` / `max_usage`。各读数区间互不耦合，故某日的日界可由各区间独立选取分配而达到；但同一区间内不同子段（分属不同日）的极值一般互斥，所以**每日边界可分别达到，不保证各日上界（或下界）在同一分配下同时成立**，响应的 `boundary_note` 对此明确注明。

### 漏采读数推断

漏采时刻把账期 `[t_start, t_end]` 切成左 `s_L` 秒、右 `s_R` 秒两段，整数容量分别为

```
C_L = floor(max_rate_per_second × s_L)
C_R = floor(max_rate_per_second × s_R)
```

账单总量 `B` 须满足 `B = (r_end − r_start) + K × modulus`（`K >= 0` 为总回绕次数）：

1. `B − (r_end − r_start)` 不被 `modulus` 整除 → 账单与模数不相容（`total_incompatible_modulus`）；
2. 同余且 `B >= 0` 时 `K` 自动非负（`0 <= B ≡ diff (mod M)` 蕴含 `K >= K_min`），无需另行校验；再要求 `B <= C_L + C_R`，否则两侧容量不足（`insufficient_capacity`）。

左侧用量 `x` 与右侧用量 `B − x` 须分别落在 `[0, C_L]`、`[0, C_R]` 内，故左侧可行用量闭区间为

```
x ∈ [max(0, B − C_R), min(C_L, B)]
```

容量均为整数，区间内每个整数 `x` 都可由某个左右侧非负整数分配达到。候选漏采读数为 `(r_start + x) mod modulus`：`x` 连续取值时候选在模数环上形成连续弧，候选数为 `min(x_max − x_min + 1, modulus)`；弧不跨零点时为单个闭区间，跨零点时拆为 `[a, modulus−1]` 与 `[0, b]` 两段（精确、互不重叠），候选数不少于模数时覆盖全部剩余类、返回全域 `[0, modulus−1]`。候选数为 1 时 `unique = true`。全程仅整数运算（速率上限由 `Fraction` 精确取整），不枚举候选。

### 最小统一速率上限

段 `i` 用量 `u_i = diff_i + k_i × modulus`（`k_i >= 0` 整数，`diff_i` 为段内读数差，`s_i` 为段历时秒数），约束为 `Σ u_i = B`（账单）且所有段 `u_i / s_i <= R`，求最小的统一速率门槛 `R*`：

1. **同余校验**与账单总量对账一致：`B ≡ (r_last − r_first) (mod modulus)`，否则 `total_incompatible_modulus`；同余且 `B >= 0` 时总回绕次数 `K = (B − Σdiff)/modulus` 自动非负。
2. **可行总量只有下界**：记 `base_i = diff_i + k_min_i × modulus` 为满足非负增量的最小段用量，待分配额外圈数 `T = K − Σ k_min_i`。`T < 0` 即账单低于可行最小总量 `Σ base_i`（`total_out_of_range`）；速率不设上限，故可行账单总量为 `[Σ base_i, +∞)`。
3. **R\* 的精确刻画**：速率 `R` 可行当且仅当

   ```
   R >= max_i base_i / s_i   且   Σ_i floor((R × s_i − base_i) / modulus) >= T
   ```

   左项计数恰为「不超过 `R` 的断点 `(base_i + t×modulus)/s_i`（`t >= 1`）」的个数，故

   ```
   R* = max( max_i base_i/s_i, 第 T 小的断点值 )
   ```

   第 `T` 小断点用**精确二分**求得：任意两个不同断点 `x/s_i`、`y/s_j` 之差 `= |x·s_j − y·s_i| / (s_i·s_j) >= 1/s_max²`，故以 `Fraction` 中点、整数计数二分至区间宽度小于 `1/s_max²` 后，`(lo, hi]` 内恰剩一个断点值，取各段「严格大于 `lo` 的最小断点」的最小值即得。迭代次数为 `O(log(值域 × s_max²))`，与断点总数无关——**不用浮点近似，也不枚举全部圈数组合**。`T = 0` 时无圈可分，`R* = max base_i/s_i`，各段圈数即 `k_min_i`（全部唯一）。
4. **段范围收紧**：固定 `R*` 后各段额外圈数上限 `cap_i = floor((R* × s_i − base_i) / modulus)`，在 `t_i ∈ [0, cap_i]`、`Σ t_i = T` 下由整数区间运算给出每段可行圈数范围（与账单总量对账同一收紧公式）：

   ```
   lo_i = max(0, T − Σ_{j≠i} cap_j)，hi_i = min(cap_i, T)
   ```

   平移回 `k_i = k_min_i + t_i`；`lo_i == hi_i` 的段唯一确定用量，其余只给范围，不猜测。

### 双表同段交叉核验

两块表在同一时段（起止时刻分别相同）计量同一真实用量 `u`。各表读数差 `d1`、`d2` 与模数 `M1`、`M2` 满足

```
u = d1 + k1·M1 = d2 + k2·M2 （k1, k2 为非负整数圈数）
```

1. **同余联立**：`u ≡ d1 (mod M1)` 且 `u ≡ d2 (mod M2)`。由中国剩余定理，存在共同用量当且仅当 `d1 ≡ d2 (mod g)`（`g = gcd(M1, M2)`）；否则两表读数差同余不相容（`incompatible_modulus`）。相容时全部共同用量构成单一同余类 `u ≡ u0 (mod L)`，`L = lcm(M1, M2)`，`u0` 由扩展欧几里得直接构造。
2. **范围求交**：各表在非负增量与速率上限下的可行用量为闭区间 `U_i = [d_i + k_min_i·M_i, d_i + k_max_i·M_i]`。记 `lo = max(U1_lo, U2_lo)`、`hi = min(U1_hi, U2_hi)`，共同候选为同余类落在 `[lo, hi]` 中的项：

   ```
   u_min = u0 + L·ceil((lo − u0)/L)
   u_max = u0 + L·floor((hi − u0)/L)
   ```

   `u_min > u_max` 即范围无交集（`range_disjoint`）——涵盖区间本身不交（`lo > hi`）与交集内无同余点两种情形（`detail` 分别说明），与同余不相容是**不同的冲突原因**。
3. **候选数与唯一性**：候选为等差数列 `u_min, u_min + L, …, u_max`，候选数 `(u_max − u_min)/L + 1` 由端点直接算得（**不逐个枚举回绕圈数**）；候选数为 1 时 `unique = true`。每个候选 `u` 唯一对应两表圈数 `k1 = (u − d1)/M1`、`k2 = (u − d2)/M2`。

全程仅用整除、`ceil/floor` 与一次扩展欧几里得，无浮点（速率上限仍由 `Fraction` 精确计算），候选数再大也与枚举量无关。`M1 == M2` 时 `L = M`，自然退化为统一模数的同余联立。

### 分时单价账单金额区间

先与「账单总量对账」完全相同地逐段求可行圈数区间并做总量联立（单段无解、账单同余不相容、总量超界三类冲突在此阶段给出，原因一致）。联立可行时，账单隐含的总回绕次数 `K` 固定，各段圈数收紧为 `k_i ∈ [lo_i, hi_i]` 且 `Σ k_i = K`。记段 `i` 的分时单价为非负有限十进制数 `p_i`（以 `num_i / 10**scale_i` 精确表示），段用量 `u_i = diff_i + k_i·M`，则应收金额

```
A = Σ p_i·u_i
  = Σ p_i·diff_i + M·Σ p_i·(k_i − lo_i)
```

第一项与圈数分配无关；剩余圈数 `T = K − Σ lo_i`（非负整数，总量对账保证 `T <= Σ (hi_i − lo_i)`）在线性目标下的最优分配由贪心直接给出，**不枚举圈数组合**：

1. **最低金额**：段按单价从低到高排序（单价以分数交叉相乘比较，不用浮点），依次向该段填入至多 `hi_i − lo_i` 个圈，直到 `T` 个圈全部用完；
2. **最高金额**：段按单价从高到低排序，同样贪心填充；
3. 单价相同的段按段索引升序填充，方案确定（同价段之间如何分配不影响金额）。

各段金额 `p_i·u_i` 按十进制分子做整数运算（`num_i·u_i`，定标 `scale_i`）；总金额取各段小数位最大值 `scale = max scale_i`，把各段分子对齐后整数求和，再格式化为十进制字符串。**全程无浮点、无组合枚举**，段数与可行圈数区间再大也不影响计算量；两个极值方案的各段用量之和都严格等于账单总量。

### 异常采样清理

把 `n` 条按时序排列的读数视为顶点 `0, 1, …, n-1`，当且仅当读数 `i`、`j`（`i < j`）可相邻保留（与「逐段复核」完全相同的时间差、非负增量与回绕模数判定）时，连一条有向边 `i → j`。边只从低索引指向高索引，故该图为有向无环图。一条保留序列（首尾必须是 `0` 与 `n-1`）即图中一条 `0 → n-1` 路径：

```
删除内部读数数 = n − 1 − 路径边数
```

故**删除最少 ⟺ 保留最多 ⟺ 路径边数最多**，即在有向无环图上求最长路径，按拓扑序（索引顺序）一遍动态规划即可，**不枚举保留子序列**：

```
dist[0] = 0
dist[j] = max { dist[i] + 1 | i < j 且 i → j 有边 }
```

`dist[n-1]` 不存在（首读数无法到达末读数）即无解状态。最优路径不唯一时，逆序再求一遍 `tail[i]`（`i → n-1` 的最多边数），记最优边数 `D = dist[n-1]`，从首读数出发贪心重构：每一步在当前位置 `cur` 的后继中取最小的 `q` 满足

```
dist[q] = dist[cur] + 1  且  dist[q] + tail[q] = D
```

即该步既要走出最长路的一步，又要保证剩余部分仍是最优的。最长路上的点必存在这样的后继，故重构不会中断；每步取最小索引，归纳可得完整序列为所有最优解中**保留索引序列字典序最小**者（序列等长，逐位比较，等价于尽早保留较小的索引）。逐对可行性判定与两遍 DP 均为 `O(n²)`，与读数可能涉及的回绕次数区间大小无关；速率上限仍由 `Fraction` 精确取整，无浮点边界误差。

### 总分表漏损复核

一块总表（下标 0）与 `m >= 1` 块分表共用同一模数 `M` 与同一组时刻，各表在段 `i` 的真实用量为

```
u_{t,i} = d_{t,i} + k_{t,i}·M
```

其中 `d_{t,i}` 为该表该段读数差，`k_{t,i}` 为落在非负增量与该表速率上限所夹连续整数区间 `[kmin_{t,i}, kmax_{t,i}]` 内的非负整圈数（逐表复用 `solve_segment` 求得，任一表段 `kmax < kmin` 即单表无解）。第 `i` 段漏损为**总表用量减去各分表用量之和**：

```
l_i = u_{0,i} − Σ_{t>=1} u_{t,i}
    = D_i + w_i·M
D_i = d_{0,i} − Σ_{t>=1} d_{t,i}
w_i = k_{0,i} − Σ_{t>=1} k_{t,i}
```

各表圈数在同一时段相互独立地取各自连续整数区间，故 `w_i` 的可行集是这些区间和的**连续差值区间**：

```
lo_i^0 = kmin_{0,i} − Σ_{t>=1} kmax_{t,i}
hi_i^0 = kmax_{0,i} − Σ_{t>=1} kmin_{t,i}
```

（总表取 + 区间、分表取 − 区间；`w_i` 允许为负，不要求总表圈数不少于分表。）漏损不得为负，即 `D_i + w_i·M >= 0`，故进一步要求 `w_i >= ceil(−D_i / M)`：与 `[lo_i^0, hi_i^0]` 无交（`hi_i^0 < ceil(−D_i/M)`）即该段漏损无法非负（`loss_segment_negative`），与单表无解、总量类冲突均不同。记收紧后的区间为 `[lo_i, hi_i]`，则该段可行漏损为连续整数区间 `[D_i + lo_i·M, D_i + hi_i·M]`，端点均可达到。

整期漏损总量 `L` 要求

```
L = Σ l_i = Σ D_i + M · Σ w_i = Σ D_i + M · W
```

`L − ΣD_i` 不被 `M` 整除即**总量同余冲突**（`total_incompatible_modulus`）；固定 `W = (L − ΣD_i)/M` 后要求 `Σ lo_i <= W <= Σ hi_i`，否则**总量超界**（`total_out_of_range`，可行整期漏损区间即各段漏损界之和）。`W` 与 `w_i` 均允许负值，故非负性只由每段漏损约束承担，不另加圈数差非负条件。

固定 `W` 后各段圈数差由与「账单总量对账」**完全相同的整数区间收紧公式**给出（区间可含负值，公式不变）：

```
lo_i' = max(lo_i, W − Σ_{j≠i} hi_j)
hi_i' = min(hi_i, W − Σ_{j≠i} lo_j)
```

`lo_i' == hi_i'` 的段漏损唯一、给出确定值，其余段只给非负漏损上下界。由于各段 `w_i` 相互独立，任何满足 `w_i ∈ [lo_i', hi_i']`、`Σw_i = W` 的整数组合都可由各表圈数独立取值实现（总表取 `k_0`、分表取 `k_t` 使差值为指定 `w_i` 即可），因此段漏损端点均确实可达，且交叉端点相等：段 `i` 漏损下界与其余段漏损上界之和恰为 `L`。全程仅整数区间运算与一次整除，**不枚举任何回绕组合**，计算量只取决于表数与段数，与圈数区间大小无关。

## 项目结构

```
app/
  main.py   # FastAPI 应用、请求/响应模型与校验
  core.py   # 回绕次数判定、总量对账、停水裁剪合并与供水片段容量、换表丢番图联立、跨日子段界、漏采读数候选区间、最小统一速率门槛、双表同余联立、分时单价金额贪心极值、异常采样清理（DAG 最长路径 + 保留索引字典序选定）与总分表漏损复核（同模数圈数区间连续差值 + 整期总量整数收紧）（Fraction/整数精确计算）
tests/
  test_api.py
Dockerfile
docker-compose.yml
requirements.txt        # 运行时依赖
requirements-dev.txt    # 测试依赖
```

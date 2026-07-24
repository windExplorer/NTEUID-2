# NTE-Drive-Calculator 评分系统分析 & 与本项目（NTEUID）对比

> 分析对象：`NTE-Drive-Calculator`（仓库 `https://github.com/hxwd94666/NTE-Drive-Calculator.git`），已克隆至 `NTE-Drive-Calculator/`
> 对比对象：本项目 `NTEUID` 的角色养成度评分（`NTEUID/nte_role/score.py` + `NTEUID/resource/scoring/*`）

---

## 一、新仓库评分系统总览

新仓库是「异环（NTE）驱动/芯片配装计算器」，它的“评分”实际上是**两套相互独立、目的不同的子系统**，这与本项目把评分定位为“养成度（契合度）”有本质区别：

| 子系统 | 代码位置 | 用途 |
| --- | --- | --- |
| A. 装备词条评分（Drive/Tape Score） | `src/optimizer/scoring.py`（`ScoringEngine`） | 给**单件**装备按某角色的 `weights` 打一个**绝对质量分**，用于仓库排序、配装择优 |
| B. 直伤毕业率 / 边际收益（Graduation & Direct Damage） | `src/features/role/graduation_model.py`、`src/features/role/damage_model.py` | 以“满配金色 20 区全板”的直伤为基准，算角色**毕业率**与每条属性的**边际收益** |

---

## 二、子系统 A：装备词条评分

### 2.1 驱动（Drive）评分

```python
# src/optimizer/scoring.py
max_weight = 取该角色 weights 中「非主词条专用」权重里最大的 4 个之和
actual_weight = Σ(该驱动每个副词条经别名解析后的权重)
quality_coef = {Gold:1.0, Purple:0.8, Blue:0.6}[品质]
score = (10.0 / max_weight) * actual_weight * drive.area * quality_coef
```

要点：
- **权重来自 `config/roles.json` 的 `weights`**（相对权重，通常 0~1），不是本项目那种“除数”。
- `max_weight` = 理论最优 4 条副词条的权重和（`_get_max_theoretical_weight`），所以分数本质是 **“该驱动实际加权词条 / 理论最优加权词条” × 区格系数 × 品质系数**，区间约 0~100。
- `drive.area` = 驱动占的区格数（2/3/4），越大分越高 → 与本项目按槽位给不同上限（`max.pie[grid]`）思路一致。
- **品质系数**（金/紫/蓝）直接乘进分里；本项目评分**不考虑品质**。

### 2.2 磁带（Tape）评分

```python
main_score = main_weight * 50.0 * quality_coef        # 主词条固定高分
sub_score  = (10.0 / max_weight) * sub_weight * 10.0 * quality_coef
score = main_score + sub_score
```

磁带主词条用 `roles.json` 的 `main_weights` 单独加权。

### 2.3 等级标签（Grade Tag）

```python
ratio = score / (area * 10.0)
D(0) < C(0.2) < B(0.3) < A(0.4) < S(0.5) < SS(0.6) < SSS(0.7) < ACE(0.8)
```
共 **8 档**，阈值为固定的百分比（见 `src/domain/grade_limits.py`）。

---

## 三、子系统 B：直伤毕业率与边际收益

### 3.1 直伤粗算公式（`damage_model.py`）

```python
attack = attack_base * (1 + attack_pct/100) + attack_flat
bonus  = 1 + (ability_damage + damage_bonus) / 100
crit   = 1 + min(crit_rate/100, cap) * crit_damage/100
direct_damage = attack * bonus * crit
```

这是一个**粗略单值直伤代理**（不含防御/抗性/技能倍率/真实乘区），用于毕业率与边际收益排序，比本项目的 `compute_segment` 真实乘区模型简单得多。

### 3.2 毕业基准（`graduation_model.py`）

构造一个**全金、满 20 区（FULL_DRIVE_AREA=20）驱动板 + 理想磁带**的理论角色：
- 驱动副词条 = 各属性 `gold_base_values`（来自 `stats.json`）× 20 区；
- 驱动子词条取按 `weights` 加权最高的 4 条；
- 磁带主词条遍历所有正权重主词条，用真实直伤公式挑出**伤害最高**的那个；
- 额外形态（extra_shape）加成按蓝图求解器给出的个数计入。

最后 `benchmark = calc_direct_damage(该理想角色属性)`。
**毕业率 = 玩家实际直伤 / benchmark**。

关键点：毕业率针对的是**“直伤数值”本身**，而本项目没有“毕业率”概念，只有“养成度契合度”。

### 3.3 边际收益（`calc_direct_marginal_benefits`）

对 7 类属性（攻击白值 / 攻% / 攻击力 / 异能伤害% / 伤害增加% / 暴击率% / 暴击伤害%），各加一个单位（`benefit_one` 里定的步长，如攻% +1.25%、爆伤 +2.0%），算直伤提升百分比并排序，用来提示“下一件装备该堆什么”。

---

## 四、配置数据对照

### 4.1 新仓库 `config/roles.json`（角色方案，以「真红」为例）

```json
{
  "weights": {
    "暴击率%": 1.0, "暴击伤害%": 1.0, "攻击力": 0.35,
    "攻击力%": 0.65, "倾陷强度": 0.25, "伤害增加%": 0.75
  },
  "main_weights": { "暴击率%": 1.0, "暴击伤害%": 1.0, "攻击力%": 0.4, "倾陷强度": 0.25, "光属性异能伤害增强%": 1.0 },
  "extra_shape_label": "Type-3",
  "extra_shape_buffs": { "暴击伤害%": 16.0 }
}
```

### 4.2 新仓库 `config/stats.json`（词条数值库）

- `gold_base_values`：单条金色副词条的满值（暴击率% 1.0、暴击伤害% 2.0、攻击力% 1.25、攻击力 8.0、环合/倾陷强度 6.0…）—— 用于毕业基准。
- `tape_main_stat_values` / `tape_stat_values`：磁带主/副词条满值。
- `main_only_keywords`：主词条专用属性（各属性异能伤害增强、治疗加成…），从副词条权重计算中排除。
- `stat_alias_mapping` / `benefit_alias_mapping`：大量别名归一（爆伤/爆击/大攻击…），容错 OCR 识别。

---

## 五、两套系统与本项目（NTEUID）评分的对比

| 维度 | NTEUID（本项目） | NTE-Drive-Calculator |
| --- | --- | --- |
| **评分目的** | 养成度 / 契合度：当前装备是否贴合该角色方案 | (A) 单件装备绝对质量，用于配装择优；(B) 直伤毕业率 |
| **评分对象** | 整套装备（核心 + 4 驱动）汇总为 1 个分，外加每件评级 | 每件装备独立打分；另外对整角色算毕业率 |
| **权重语义** | `attributes.json.score` 是**除数**：数值越大=该属性每点越“便宜”（分越少） | `roles.json.weights` 是**相对权重**：越大=越有价值；分 = 实际加权 / 理论最优加权 |
| **属性命名** | 原始 gsuid 属性 id（`atkup`/`atkadd`/`critbase`/`damageupincantationbase`…） | 人类可读名（`攻击力%`/`暴击率%`/`光属性异能伤害增强%`…）+ 别名归一 |
| **计入哪些词条** | 核心的 `%` 主词条（在 `core_main_attr_list`）+ 已解锁推荐副词条（在 `recommend_attr_list`，且 index < lev//5） | 驱动/磁带**全部**副词条按权重计入；主词条专用属性被 `main_only_keywords` 排除出副词条评分 |
| **品质系数** | 不区分金/紫/蓝 | 乘 `quality_coef`（金 1.0 / 紫 0.8 / 蓝 0.6） |
| **槽位/区格** | 按 `max.pie[grid]` 给不同槽位不同上限 | 乘 `drive.area`（区格数） |
| **总分公式** | `ceil(raw / refer_score * 100)`（`refer_score` 为参考分母） | 各件独立：`(10/max_weight)*actual_weight*area*quality` |
| **评级档位** | 3 档：S(≥0.8) / A(≥0.6) / B（见 `grades.json`） | 8 档：D/C/B/A/S/SS/SSS/ACE（0/0.2/0.3/0.4/0.5/0.6/0.7/0.8，见 `grade_limits.py`） |
| **是否含伤害模型** | 是（`utils/damage/`，真实乘区、多段、来源限定增益） | 仅粗略直伤代理（`attack*bonus*crit`），用于毕业率与边际收益，不含防御/抗性/真实倍率 |

### 核心差异一句话总结

- **NTEUID**：评分 = “你的装备在本角色方案里**契合到什么程度**”（相对参考方案的养成度百分比）。
- **NTE-Drive-Calculator**：评分 = “单件装备**相对理论最优配置的成色**”（绝对质量分）+ “整角色**相对满配毕业的直伤比例**”（毕业率）。

两者权重口径**相反**：本项目用“除数”使价值高的属性得分更低，新仓库用“相对权重”使价值高的属性得分更高；且新仓库额外把**品质**和**区格大小**直接折进分数。

---

## 六、可借鉴点（供后续参考）

1. **别名归一 + OCR 容错**：新仓库的 `stat_alias_mapping`（爆伤/爆击/大攻击…）对从截图/面板解析词条很稳健，本项目若也要做面板识别可复用该表。
2. **毕业率视角**：本项目只有养成度契合，缺少“距离满配还差多少”的直观指标；可参考 `graduation_model.py` 用真实 `compute_segment` 算 `玩家直伤 / 满配直伤`。
3. **边际收益提示**：`calc_direct_marginal_benefits` 的“下一件该堆什么”思路，可叠加到本项目的真实伤害模型上，给出更可信的配装建议。
4. **多档评级（8 档）**：本项目仅 S/A/B 三档，可参考其更细的梯度。

> 注意：两个系统的权重数值**不能直接互换**——语义与校准方式不同（除数 vs 相对权重），接入时需要重新标定。

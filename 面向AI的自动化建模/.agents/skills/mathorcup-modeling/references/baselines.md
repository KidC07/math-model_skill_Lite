# 基线模型与方法库

用于给当前子问题建立可核验的比较起点。沿用旧版的基线方法和必要检查，按当前问题选择，不用模型名称给整题分类。题目专属参数、阈值、领域解释和最终方案写在项目中。

## 先验收基线，再比较改进

基线正确包括三个层面：回答的确是当前问题；实现与数学定义一致；当前输入上的结果通过必要核验。熟悉的模型、历史测试通过或求解器返回成功，均不能替代这三个层面。

先说明目标、输入输出、必要约束、单位、信息可见时点和评价口径，再形成简单可复现的基线。用可手算的小规模情形、边界情况或独立实现验证程序；在真实输入上重算核心指标、约束和相关守恒关系。记录实际验证内容与结果位置即可，不新增固定表格流程。

基线不必最先进或达到最优，但必须满足作为该对照的适用条件。可行方案与松弛下界分别标识；错误、数据泄漏或未满足硬约束的结果不能当作已验收基线。未达到题目最低性能要求的弱对照，也不能称为可交付解。

基线未通过时先修正问题，正式改进对比从已验收版本出发。改进保持相同输入、可用信息和评价条件，复查新增逻辑并保留基线结果。有限测试只证明所覆盖的行为，具体题目的正确性仍需上述核验。

## 按数学结构读取

| 当前子问题 | 可复用的起点与候选方法 | 详细参考 |
|---|---|---|
| 连续目标回归或时间序列预测 | 均值、OLS、朴素预测、移动均值；再按证据考虑季节性、正则化或更复杂模型 | [回归与预测](model-guides/forecasting.md) |
| 有真实类别标签 | 多数类/类别先验对照、逻辑回归；随机森林、SVM、KNN 作为结构合适时的候选 | [分类](model-guides/classification.md) |
| 无标签的分群结构 | K-means、层次聚类、DBSCAN | [聚类](model-guides/clustering.md) |
| 多指标评分与排序 | 可解释的权重和汇总对照；AHP、熵权、TOPSIS、模糊评价、DEA、灰色关联 | [综合评价](model-guides/evaluation.md) |
| 决策变量、目标与硬约束 | 可行规则、LP/MILP、网络算法；模型结构与规模支持时再扩展 | [优化](model-guides/optimization.md) |
| 守恒、状态演化或局部交互 | 守恒/平衡关系、差分、ODE/PDE、元胞自动机 | [机理](model-guides/mechanistic.md) |

这些是可组合的方法参考，不是各类题目的标准答案。只加载与真实候选路线有关的文件。

## 已提供的可运行实现

[baseline_models.py](../scripts/baseline_models.py) 承接旧库的五个基线，仅使用基础环境已有的 NumPy、SciPy；其余方法是参考指南，没有冒充已经实现或验证。

| 函数 | 输入与数学口径 | 输出与边界 |
|---|---|---|
| `run_regression_baselines(X_train, y_train, X_test, y_test, output_dir=None)` | `X` 为样本×特征，`y` 为一维实数；均值和含截距 OLS 只在训练集拟合 | 返回预测、MAE/RMSE/R²、OLS 系数与秩；测试目标为常数或只有一行时 R² 为 `None`；调用者负责数据切分与防泄漏 |
| `run_time_series_baselines(train_series, test_series, *, protocol, window=3, output_dir=None)` | 连续等间隔序列；必须显式选 `fixed_origin` 或 `rolling_one_step`；`window` 不超过训练历史长度 | 固定起点模式仅使用训练末尾，测试长度就是预测期；滚动一步模式预测后才揭示当前观测，供下一步使用。返回朴素值和尾部均值预测及指标，两种口径不能混比 |
| `solve_facility_allocation_milp(cost_matrix, demand_vec, capacity_vec, fixed_costs, output_dir=None, *, time_limit=60, atol=1e-7, rtol=1e-8)` | 成本矩阵为设施×客户；运输量连续、需求可拆分、设施开设为 0/1；需求严格满足、总流量受开设容量限制 | 返回开设状态、完整流量、独立复算的目标/约束残差与求解界；不含时间窗、单源分配、禁运边等附加规则。未取得符合验收条件的求解状态时抛出错误，不返回伪成功 |

设施选址只是可复用的一个优化结构，不是其他优化任务的默认模型。`atol/rtol` 是数值检查参数，要按单位、尺度和项目精度要求确定，不能替代物理约束。

函数默认只返回结果；明确提供 `output_dir` 才写 JSON，并拒绝覆盖同名文件。输入包含空值、非有限数或错误维度时拒绝继续。模块不自动清洗、切分或安装依赖。调用时在真实项目中导入；若改造后复制到项目，保留来源及许可说明。

## 来源与迁移修正

方法参考来自本地旧版 `cumcm-team-workflow/references/model-guides/`，已重写为按需阅读的通用指南。代码结构来源为 `cumcm-skills/skills/cumcm-solver/assets/` 的两份模板，许可见 [第三方说明](../../../../THIRD_PARTY_NOTICES.txt)。

本次修正整数目标导致均值预测截断的问题；移除未生效的 `horizon` 参数，改为明确预测口径；使用现有 NumPy/SciPy 完成 OLS 与 MILP；补充输入校验、独立复算和数值测试。实际依赖与算法接口核对了 [NumPy 最小二乘](https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html)、[数组类型规则](https://numpy.org/doc/stable/reference/generated/numpy.full_like.html)和 [SciPy MILP](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html)。

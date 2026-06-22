# 碧蓝档案配队推荐器 MVP

这是一个面向新手和 xp 党玩家的《碧蓝档案》推图配队推荐 Web App。用户选择一个或多个想围绕配队的核心角色后，系统会根据角色定位、技能标签、攻击类型、EX 费用和技能协同关系，为这个核心组合推荐适合的队友，并用中文解释推荐原因。

第一版使用本地 JSON 数据和规则打分，方便开发、测试和展示。当前 `data/characters.json` 的完整角色名录来自 GameKee《碧蓝档案》学生图鉴https://www.gamekee.com/ba/ ，站位、攻击类型、护甲类型、EX 费用和技能摘要来自 SchaleDB 的结构化资料。

## 项目结构

```text
ba-team-recommender/
├── app.py
├── recommender.py
├── requirements.txt
├── README.md
├── scripts/
│   ├── crawl_bilibili_push_guides.py
│   └── update_from_gamekee.py
└── data/
    ├── bilibili_push_guides.json
    └── characters.json
```

## 安装依赖

建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行项目

在项目目录中执行：

```bash
streamlit run app.py
```

启动后，浏览器会打开本地页面，通常是：

```text
http://localhost:8501
```

## 部署到公网

当前 `http://127.0.0.1:8501/` 或 `http://localhost:8501` 只在本机可访问。要让其他玩家也能使用，可以把项目部署到 Streamlit Community Cloud 或 Hugging Face Spaces。

最快方式是使用 Streamlit Community Cloud：把本项目推到 GitHub 仓库，在 `https://share.streamlit.io/` 创建 App，并选择 `app.py` 作为入口文件。部署成功后会得到一个 `https://xxx.streamlit.app/` 形式的公网链接。

详细步骤见 [DEPLOY.md](DEPLOY.md)。

## 数据字段说明

`data/characters.json` 中每个角色包含：

- `name`：角色名称
- `role`：角色定位，例如 `main_dps`、`sub_dps`、`support`、`healer`、`tank`
- `position`：`striker` 或 `special`
- `battle_position`：游戏内战斗站位，例如 `front`、`middle`、`back`
- `attack_type`：攻击类型
- `armor_type`：护甲类型
- `ex_cost`：EX 技能费用
- `skills`：技能摘要
- `tags`：结构化技能标签，例如 `atk_buff`、`crit_buff`、`defense_down`、`cost_recovery`
- `ratings`：GameKee 角色评测里的综合评分；部分角色暂无评测页时会显示暂无评分

推荐算法会读取 `skills` 里的 EX、普通、被动和子技能文本，粗略判断输出核心更偏 `EX 爆发型`、`普攻/小技能持续输出型` 还是 `混合输出型`。这个判断会显示在核心角色信息面板里。

页面会把推荐结果分成两组：

- 前排上场（Striker）：占用 4 个上场学生位。
- 后排支援（Special）：占用 2 个支援学生位。

页面侧栏支持 `中文 / English` 切换。英文模式会翻译界面、定位标签、队伍职责、推荐理由和 Box 提示；角色名称和技能摘要暂时沿用本地 JSON 中的中文数据，后续可以再从 SchaleDB 英文数据补充英文角色名与技能文本。

每个推荐卡片还会展示战斗站位，帮助区分“角色在队伍槽位中属于 Striker/Special”和“角色在战场上站前排/中排/后排”。
推荐卡片中有两个分数：`适配分` 是本 App 根据技能联动算出的配队分，`综合评分` 是 GameKee 角色评测里的角色评分。
推荐区顶部会先做“队伍职责检查”：默认新手队伍骨架包含坦克、主 C、副 C、辅助、治疗。玩家已经选择的角色会先占位，系统会优先推荐能补齐缺口的角色。例如已选择主 C 时，会优先补坦克、副 C、辅助和治疗；如果已选择坦克，则会优先补主 C、副 C、辅助和治疗。
这里的副 C 按“半辅输出”处理：它不是单纯第二个输出，而是优先推荐能给主 C 提供攻击、暴击、防御降低、费用循环等对口增益，并且自己也能补输出、破防或清杂的角色。

## 推荐规则示例

当前版本的推荐逻辑位于 `recommender.py`，主要规则包括：

- 主输出搭配攻击提升或暴击提升会加分。
- 推荐逻辑会区分“给我方队友的增益”和“只给自身的强化”，避免把自我减费、自我攻击提升误判成辅助能力。
- EX 爆发型主 C 会优先搭配给队友的费用降低、费用恢复、短窗口攻击/暴击增益、EX 伤害强化、对应属性特效增伤和防御降低。
- 普攻/小技能持续输出型主 C 会优先搭配给队友的攻击速度提升、长时间攻击增益、持续暴击率/暴击伤害增益、对应属性特效增伤和防御降低。
- 有自损、低血量倒计时或退场风险的输出角色，会更优先推荐治疗和护盾来保证推图稳定性。
- 高费用角色搭配费用降低或费用恢复会加分。
- 较脆角色搭配治疗或护盾会加分。
- 爆发输出搭配防御降低会加分。
- 非辅助角色定位重复会轻微扣分，避免队伍功能重叠。
- 当玩家选择多个核心角色时，候选队友会分别和每个核心角色打分，再汇总成组合适配分。
- 推荐排序会优先补齐队伍职责缺口，再按技能适配分展示更多候选队友；副 C 缺口会额外参考半辅输出适配度。

每条推荐都会返回分数和自然语言理由，这也是这个 MVP 的核心价值：不只告诉玩家“选谁”，还解释“为什么这样选”。

## B 站推图资料研究

`data/bilibili_push_guides.json` 保存了少量 B 站推图配队资料候选，用于帮助调整推图泛用规则。这里不会直接收录总力战、凹分轴或排名作业，因为这些内容更偏极限 Boss 场景，和本项目当前的普通推图目标不同。

可以运行下面的脚本继续采集候选资料：

```bash
python scripts/crawl_bilibili_push_guides.py
```

B 站搜索接口有时会触发验证码。如果遇到这种情况，可以先手动找到视频或专栏链接，再用 `--seed-url` 传给脚本：

```bash
python scripts/crawl_bilibili_push_guides.py \
  --seed-url https://www.bilibili.com/read/cv25472431
```

脚本会按关键词把资料粗分为：

- `push_map`：主线、普通图、开荒、萌新、低练、清杂等推图内容。
- `raid_score_chasing`：总力战、大决战、凹分、作业、排名、刀数等高难轴内容。
- `mixed_or_unknown`：信号不够明确，需要人工复核。

## 我的 Box 模式

页面侧栏提供“我的 Box”区域，可以手动选择自己拥有的角色。开启“只推荐我拥有的角色”后，系统会：

- 只从玩家 Box 内推荐可用队友。
- 显示理想推荐中缺少哪些关键角色。
- 给出 Box 内替代角色和替代理由。
- 支持导出 `my_box.json`，也支持重新导入。

导出的 JSON 格式示例：

```json
{
  "owned_names": ["日鞠", "小玉", "芹娜"]
}
```

## 更新角色资料

如果需要重新同步 GameKee 上的实装学生列表，并用 SchaleDB 补齐结构化角色资料，可以运行：

```bash
python scripts/update_from_gamekee.py
```

脚本会请求 GameKee 图鉴接口，过滤模板、测试、占位符条目，再用 SchaleDB 的学生数据补齐以下字段：

- Striker / Special 队伍位
- 前排 / 中排 / 后排战斗站位
- 攻击类型、护甲类型、EX 费用
- EX / 普通 / 被动 / 辅助技能摘要
- 治疗、护盾、费用恢复、攻击增益、防御降低等推荐标签

已经人工补充过的角色标签会被保留，并与自动推断标签合并。

## 后续扩展方向

- 增加敌人类型、地图环境、普通图关卡类型等筛选条件。
- 如果之后要支持总力战，应做成单独模式，不和普通推图推荐权重混用。
- 为角色加入地形适性、武器类型、星级培养成本等字段。
- 增加角色头像和技能图标展示。
- 把规则拆成可配置 JSON，让非程序用户也能调整推荐权重。
